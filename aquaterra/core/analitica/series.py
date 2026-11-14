r"""Motor analítico de series temporales agro-ecológicas (Dominio Puro — Cero I/O).

Incluye:
- Ventanas móviles en memoria ($O(N)$ con cola deslizante) compatibles con las
  Window Functions nativas de SQLite3.
- Tasa de cambio horaria por regresión lineal de mínimos cuadrados ($\Delta y / \Delta t$,
  usada para tasa de secado edáfico $\Delta\theta / \Delta t$ en $\%/\text{h}$).
- Estimación de tiempo restante hasta estrés hídrico ($t_{\text{crit}}$ en horas).
- Correlación bivariada de Pearson ($r$) con alineación temporal tolerante a jitter.
- Promedio vectorial circular para dirección de viento
  ($\operatorname{atan2}(\overline{\sin\theta}, \overline{\cos\theta})$).
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from aquaterra.core import tiempo

VENTANAS_MOVILES_SEG: dict[str, int] = {
    "5m": 300,
    "15m": 900,
    "30m": 1_800,
    "1h": 3_600,
    "6h": 21_600,
    "24h": 86_400,
    "7d": 604_800,
}


def resolver_ventana_seg(ventana: str | int) -> int:
    """Convierte una etiqueta (``'5m'``, ``'15m'``, ``'30m'``, ``'1h'``, ``'6h'``, ``'24h'``, ``'7d'``) a segundos."""
    if isinstance(ventana, int):
        if ventana <= 0:
            raise ValueError(f"La ventana móvil debe ser > 0 segundos (recibido: {ventana}).")
        return ventana
    clave = ventana.strip().lower()
    if clave not in VENTANAS_MOVILES_SEG:
        validas = ", ".join(VENTANAS_MOVILES_SEG)
        raise ValueError(f"Ventana móvil '{ventana}' no reconocida. Use una de: {validas}.")
    return VENTANAS_MOVILES_SEG[clave]


class TendenciaVariable(StrEnum):
    ASCENDENTE = "ascendente"
    DESCENDENTE = "descendente"
    ESTABLE = "estable"

    @property
    def simbolo(self) -> str:
        if self is TendenciaVariable.ASCENDENTE:
            return "↑"
        if self is TendenciaVariable.DESCENDENTE:
            return "↓"
        return "→"


@dataclass(frozen=True, slots=True)
class PuntoVentanaMovil:
    ts_epoch: int
    ts_iso: str
    valor: float
    media_movil: float
    min_movil: float
    max_movil: float


@dataclass(frozen=True, slots=True)
class ResultadoCorrelacionBivariada:
    variable_x: str
    variable_y: str
    pares_alineados: int
    pearson_r: float | None
    pendiente_y_sobre_x: float | None
    interpretacion: str


def calcular_ventana_movil_memoria(
    puntos: Sequence[tuple[int, float]],
    ventana: str | int = "1h",
) -> list[PuntoVentanaMovil]:
    """Calcula media, mínimo y máximo móvil sobre ``[ts - ventana_seg, ts]`` en memoria."""
    ventana_seg = resolver_ventana_seg(ventana)
    if not puntos:
        return []

    ordenados = sorted(puntos, key=lambda par: par[0])
    ventana_activa: deque[tuple[int, float]] = deque()
    resultado: list[PuntoVentanaMovil] = []

    for ts_epoch, valor in ordenados:
        ventana_activa.append((ts_epoch, float(valor)))
        cota_inferior = ts_epoch - ventana_seg
        while ventana_activa and ventana_activa[0][0] < cota_inferior:
            ventana_activa.popleft()

        valores = [v for _, v in ventana_activa]
        media = sum(valores) / len(valores)
        resultado.append(
            PuntoVentanaMovil(
                ts_epoch=ts_epoch,
                ts_iso=tiempo.a_iso(tiempo.desde_epoch(ts_epoch)),
                valor=round(float(valor), 4),
                media_movil=round(media, 4),
                min_movil=round(min(valores), 4),
                max_movil=round(max(valores), 4),
            )
        )
    return resultado


def tasa_cambio_por_hora(puntos: Sequence[tuple[int, float]]) -> float | None:
    """Pendiente por mínimos cuadrados ordinarios (OLS) expresada en ``unidad / hora``.

    En humedad de suelo (``suelo_a``), un valor negativo p. ej. ``-0.45`` significa que el
    sustrato pierde ``0.45 %`` de humedad volumétrica por cada hora transcurrida.
    Devuelve ``None`` si hay menos de 2 muestras o si el intervalo temporal es nulo.
    """
    if len(puntos) < 2:
        return None

    t0 = puntos[0][0]
    horas = [(ts - t0) / 3600.0 for ts, _ in puntos]
    valores = [float(v) for _, v in puntos]

    n = len(puntos)
    media_t = sum(horas) / n
    media_v = sum(valores) / n

    var_t = sum((t - media_t) ** 2 for t in horas)
    if var_t <= 1e-12:
        return None

    cov_tv = sum((t - media_t) * (v - media_v) for t, v in zip(horas, valores, strict=True))
    return round(cov_tv / var_t, 4)


def clasificar_tendencia(
    tasa_por_hora: float | None,
    *,
    umbral_estable_por_hora: float = 0.02,
) -> TendenciaVariable:
    if tasa_por_hora is None or abs(tasa_por_hora) <= umbral_estable_por_hora:
        return TendenciaVariable.ESTABLE
    return TendenciaVariable.ASCENDENTE if tasa_por_hora > 0 else TendenciaVariable.DESCENDENTE


def tiempo_hasta_umbral_horas(
    valor_actual: float,
    tasa_por_hora: float | None,
    umbral_critico: float,
) -> float | None:
    """Estima las horas restantes ($t_{\\text{crit}}$) para descender hasta ``umbral_critico``.

    - Si ``valor_actual <= umbral_critico``, devuelve ``0.0`` (ya está en estrés).
    - Si la variable no está descendiendo (``tasa_por_hora is None`` o ``>= -1e-6``),
      devuelve ``None`` (no hay convergencia hacia estrés hídrico bajo la tendencia actual).
    """
    if valor_actual <= umbral_critico:
        return 0.0
    if tasa_por_hora is None or tasa_por_hora >= -1e-6:
        return None
    horas = (valor_actual - umbral_critico) / abs(tasa_por_hora)
    return round(horas, 2)


def correlacion_bivariada(
    serie_x: Sequence[tuple[int, float]],
    serie_y: Sequence[tuple[int, float]],
    *,
    variable_x: str = "x",
    variable_y: str = "y",
    tolerancia_seg: int = 300,
) -> ResultadoCorrelacionBivariada:
    """Empareja dos series temporales dentro de ``tolerancia_seg`` y calcula Pearson $r$."""
    if not serie_x or not serie_y:
        return ResultadoCorrelacionBivariada(
            variable_x=variable_x,
            variable_y=variable_y,
            pares_alineados=0,
            pearson_r=None,
            pendiente_y_sobre_x=None,
            interpretacion="datos_insuficientes",
        )

    ord_x = sorted(serie_x, key=lambda p: p[0])
    ord_y = sorted(serie_y, key=lambda p: p[0])

    pares_x: list[float] = []
    pares_y: list[float] = []
    j = 0
    n_y = len(ord_y)

    for ts_x, val_x in ord_x:
        while j + 1 < n_y and abs(ord_y[j + 1][0] - ts_x) <= abs(ord_y[j][0] - ts_x):
            j += 1
        if abs(ord_y[j][0] - ts_x) <= tolerancia_seg:
            pares_x.append(float(val_x))
            pares_y.append(float(ord_y[j][1]))

    n = len(pares_x)
    if n < 3:
        return ResultadoCorrelacionBivariada(
            variable_x=variable_x,
            variable_y=variable_y,
            pares_alineados=n,
            pearson_r=None,
            pendiente_y_sobre_x=None,
            interpretacion="datos_insuficientes",
        )

    media_x = sum(pares_x) / n
    media_y = sum(pares_y) / n
    s_xx = sum((x - media_x) ** 2 for x in pares_x)
    s_yy = sum((y - media_y) ** 2 for y in pares_y)
    if s_xx <= 1e-12 or s_yy <= 1e-12:
        return ResultadoCorrelacionBivariada(
            variable_x=variable_x,
            variable_y=variable_y,
            pares_alineados=n,
            pearson_r=0.0,
            pendiente_y_sobre_x=0.0,
            interpretacion="varianza_nula",
        )

    s_xy = sum((x - media_x) * (y - media_y) for x, y in zip(pares_x, pares_y, strict=True))
    r = max(-1.0, min(1.0, s_xy / math.sqrt(s_xx * s_yy)))
    pendiente = s_xy / s_xx

    abs_r = abs(r)
    if abs_r >= 0.7:
        interp = "fuerte_positiva" if r > 0 else "fuerte_negativa"
    elif abs_r >= 0.4:
        interp = "moderada_positiva" if r > 0 else "moderada_negativa"
    else:
        interp = "debil_o_nula"

    return ResultadoCorrelacionBivariada(
        variable_x=variable_x,
        variable_y=variable_y,
        pares_alineados=n,
        pearson_r=round(r, 4),
        pendiente_y_sobre_x=round(pendiente, 4),
        interpretacion=interp,
    )


def promedio_vectorial_grados(grados: Sequence[float]) -> float | None:
    r"""Promedio circular acimutal ($0..360^\circ$) mediante $\operatorname{atan2}$.

    Resuelve la discontinuidad norte ($350^\circ$ y $10^\circ$ promedian $0^\circ$, no $180^\circ$).
    """
    if not grados:
        return None
    radianes = [math.radians(g % 360.0) for g in grados]
    media_sin = sum(math.sin(r) for r in radianes) / len(radianes)
    media_cos = sum(math.cos(r) for r in radianes) / len(radianes)
    if abs(media_sin) <= 1e-9 and abs(media_cos) <= 1e-9:
        return None
    angulo = math.degrees(math.atan2(media_sin, media_cos)) % 360.0
    return 0.0 if abs(angulo - 360.0) < 1e-6 or abs(angulo) < 1e-6 else round(angulo, 2)
