"""Validadores de dominio reutilizables (resuelve DT-03).

En v3.2 ``_accion_guardar()`` validaba y ``_accion_actualizar()`` no, por lo que
un área no numérica explotaba como ``ValueError`` dentro de ``data_manager.py``.
Ahora creación y actualización pasan por la MISMA función, y se acumulan todos
los errores para mostrarlos de una sola vez al usuario.
"""

from __future__ import annotations

from typing import Any

from aquaterra.core.domain.entidades import CULTIVOS_SOPORTADOS, DatosParcela, TipoSuelo
from aquaterra.core.domain.errores import ErrorValidacion

LONGITUD_MAX_NOMBRE = 60
AREA_MAX_M2 = 10_000_000.0      # 1 000 ha: cota superior de sanidad para una parcela
LITROS_MIN = 1.0
LITROS_MAX = 5_000.0             # Mismo rango que el Spinbox de v3.2


def _a_float(valor: Any) -> float | None:
    if isinstance(valor, bool):
        return None
    try:
        # Acepta coma decimal (teclado es-CO): "12,5" -> 12.5
        return float(str(valor).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


def validar_datos_parcela(
    *,
    nombre: Any,
    cultivo: Any,
    area: Any,
    humedad: Any,
    suelo: Any,
    riego_auto: Any,
    estacion_id: int | None = None,
) -> DatosParcela:
    """Valida y normaliza los datos de una parcela.

    Raises:
        ErrorValidacion: con la lista completa de problemas encontrados.
    """
    problemas: list[str] = []

    nombre_limpio = " ".join(str(nombre or "").split())
    if not nombre_limpio:
        problemas.append("El nombre de la parcela es obligatorio.")
    elif len(nombre_limpio) > LONGITUD_MAX_NOMBRE:
        problemas.append(f"El nombre no puede superar {LONGITUD_MAX_NOMBRE} caracteres.")

    cultivo_limpio = str(cultivo or "").strip()
    if cultivo_limpio not in CULTIVOS_SOPORTADOS:
        problemas.append(f"Cultivo no soportado: '{cultivo_limpio}'.")

    area_m2 = _a_float(area)
    if area_m2 is None:
        problemas.append("El área debe ser numérica (m²).")
    elif not (0 < area_m2 <= AREA_MAX_M2):
        problemas.append(f"El área debe estar entre 0 y {AREA_MAX_M2:,.0f} m².")

    humedad_pct = _a_float(humedad)
    if humedad_pct is None:
        problemas.append("La humedad debe ser numérica (%).")
    elif not (0 <= humedad_pct <= 100):
        problemas.append("La humedad volumétrica relativa debe estar entre 0 y 100 %.")

    try:
        tipo_suelo = TipoSuelo(str(suelo))
    except ValueError:
        tipo_suelo = None
        problemas.append(f"Tipo de suelo inválido: '{suelo}'.")

    if problemas:
        raise ErrorValidacion(problemas)

    return DatosParcela(
        nombre=nombre_limpio,
        cultivo=cultivo_limpio,
        area_m2=round(area_m2, 2),           # type: ignore[arg-type]
        humedad_pct=round(humedad_pct, 1),   # type: ignore[arg-type]
        tipo_suelo=tipo_suelo,               # type: ignore[arg-type]
        riego_auto=bool(riego_auto),
        estacion_id=estacion_id,
    )


def validar_litros(litros: Any) -> float:
    valor = _a_float(litros)
    if valor is None or not (LITROS_MIN <= valor <= LITROS_MAX):
        raise ErrorValidacion(
            f"La cantidad de agua debe estar entre {LITROS_MIN:.0f} y {LITROS_MAX:,.0f} L."
        )
    return valor


def validar_umbral_humedad(umbral: Any) -> float:
    valor = _a_float(umbral)
    if valor is None or not (0 <= valor <= 100):
        raise ErrorValidacion("El umbral de humedad debe estar entre 0 y 100 %.")
    return valor
