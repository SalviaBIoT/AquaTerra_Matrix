"""Síntesis determinista de Pulso 24h por familia de estación (Dominio Puro — Cero I/O).

Implementa el motor experto local (Nivel 3 garantizado del Riesgo 1 de la Brújula Maestra)
para que toda estación disponga de indicadores científicos y diagnóstico ejecutivo
incluso en operación 100 % offline en páramo o finca.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from aquaterra.core.analitica.series import (
    TendenciaVariable,
    clasificar_tendencia,
    promedio_vectorial_grados,
    tasa_cambio_por_hora,
    tiempo_hasta_umbral_horas,
)
from aquaterra.core.domain import Estacion, EventoEstacion, TipoEstacion

MUESTRAS_ESPERADAS_24H = 288  # Cadencia nominal de 5 minutos (12 * 24 = 288 muestras/día)


class NivelSeveridadPulso(StrEnum):
    OPTIMO = "optimo"
    ATENCION = "atencion"
    CRITICO = "critico"
    SIN_DATOS = "sin_datos"


@dataclass(frozen=True, slots=True)
class ResumenVariable24h:
    variable: str
    unidad: str | None
    ultimo_valor: float
    ultimo_ts_epoch: int
    media_24h: float
    min_24h: float
    max_24h: float
    tendencia: TendenciaVariable
    tasa_hora: float | None
    muestras: int
    completitud_pct: float


@dataclass(frozen=True, slots=True)
class IndicadoresPulsoInti:
    tasa_secado_suelo_a_pct_h: float | None
    diferencial_horizontes_ab_pct: float | None
    horas_estres_vpd: float
    horas_riesgo_fungico_vpd: float
    horas_hasta_estres_suelo_a: float | None
    voltaje_bateria_v: float | None


@dataclass(frozen=True, slots=True)
class IndicadoresPulsoInBeersa:
    delta_temp_medio_c: float | None
    desviacion_termica_nido_c: float | None
    en_rango_homeostasis: bool | None
    tasa_actividad_pir_por_hora: float
    conteo_audios_bioacusticos: int


@dataclass(frozen=True, slots=True)
class IndicadoresPulsoSigatoka:
    horas_humectacion_foliar_24h: float
    duracion_humectacion_continua_min: float
    alerta_infeccion_fungica: bool
    rumbo_viento_dominante_grados: float | None
    precipitacion_acumulada_mm: float


@dataclass(frozen=True, slots=True)
class IndicadoresPulsoConservacion:
    variacion_nivel_freatico_cm: float | None
    humedad_turba_media_pct: float | None
    irradiancia_max_wm2: float | None
    balance_bateria_v: float | None


@dataclass(frozen=True, slots=True)
class ResumenPulso24h:
    estacion_id: int
    codigo_estacion: str
    nombre_estacion: str
    tipo_estacion: TipoEstacion
    desde_epoch: int
    hasta_epoch: int
    severidad: NivelSeveridadPulso
    completitud_global_pct: float
    variables: dict[str, ResumenVariable24h]
    alertas_detectadas: tuple[str, ...]
    diagnostico_determinista: str
    inti: IndicadoresPulsoInti | None = None
    inbeersa: IndicadoresPulsoInBeersa | None = None
    sigatoka: IndicadoresPulsoSigatoka | None = None
    conservacion: IndicadoresPulsoConservacion | None = None


def _horas_cumpliendo_condicion(
    serie: Sequence[tuple[int, float]],
    predicado: Callable[[float], bool],
    *,
    paso_nominal_seg: int = 300,
) -> float:
    """Integra el tiempo (en horas) en que ``predicado(valor)`` fue verdadero."""
    if not serie:
        return 0.0
    ordenada = sorted(serie, key=lambda p: p[0])
    if len(ordenada) == 1:
        return round(paso_nominal_seg / 3600.0, 2) if predicado(ordenada[0][1]) else 0.0

    segundos_acumulados = 0.0
    for idx, (ts, valor) in enumerate(ordenada):
        if not predicado(valor):
            continue
        if idx + 1 < len(ordenada):
            dt = min(max(ordenada[idx + 1][0] - ts, 0), 1_800)
            if dt == 0:
                dt = paso_nominal_seg
        else:
            dt = min(max(ts - ordenada[idx - 1][0], paso_nominal_seg), 1_800)
        segundos_acumulados += dt
    return round(segundos_acumulados / 3600.0, 2)


def _desviacion_estandar(valores: Sequence[float]) -> float | None:
    if len(valores) < 2:
        return 0.0 if len(valores) == 1 else None
    media = sum(valores) / len(valores)
    varianza = sum((v - media) ** 2 for v in valores) / len(valores)
    return round(math.sqrt(varianza), 3)


def _evaluar_inti(
    variables: Mapping[str, ResumenVariable24h],
    series: Mapping[str, Sequence[tuple[int, float]]],
    *,
    umbral_estres_suelo_pct: float = 30.0,
) -> tuple[IndicadoresPulsoInti, list[str], NivelSeveridadPulso]:
    alertas: list[str] = []
    severidad = NivelSeveridadPulso.OPTIMO

    suelo_a = variables.get("suelo_a")
    suelo_b = variables.get("suelo_b")
    voltaje = variables.get("voltaje")
    serie_vpd = series.get("vpd", ())

    tasa_secado = suelo_a.tasa_hora if suelo_a else None
    dif_ab = round(suelo_a.ultimo_valor - suelo_b.ultimo_valor, 2) if (suelo_a and suelo_b) else None
    horas_estres = _horas_cumpliendo_condicion(serie_vpd, lambda v: v > 1.6)
    horas_fungico = _horas_cumpliendo_condicion(serie_vpd, lambda v: v < 0.4)
    horas_crit = (
        tiempo_hasta_umbral_horas(suelo_a.ultimo_valor, tasa_secado, umbral_estres_suelo_pct)
        if suelo_a
        else None
    )
    volt_actual = voltaje.ultimo_valor if voltaje else None

    if suelo_a:
        if suelo_a.ultimo_valor <= umbral_estres_suelo_pct:
            severidad = NivelSeveridadPulso.CRITICO
            alertas.append(
                f"Déficit hídrico en Horizonte A ({suelo_a.ultimo_valor:.1f}% <= {umbral_estres_suelo_pct:.1f}%)."
            )
        elif horas_crit is not None and horas_crit <= 12.0:
            severidad = max(severidad, NivelSeveridadPulso.ATENCION, key=_orden_severidad)
            alertas.append(f"Secado activo: Horizonte A tocará umbral crítico en ~{horas_crit:.1f} h.")

    if volt_actual is not None and volt_actual < 3.4:
        severidad = NivelSeveridadPulso.CRITICO
        alertas.append(f"Batería crítica en nodo ({volt_actual:.2f} V < 3.40 V).")

    if horas_estres >= 4.0:
        severidad = max(severidad, NivelSeveridadPulso.ATENCION, key=_orden_severidad)
        alertas.append(f"Demanda evaporativa alta: {horas_estres:.1f} h con VPD > 1.6 kPa.")

    return (
        IndicadoresPulsoInti(
            tasa_secado_suelo_a_pct_h=tasa_secado,
            diferencial_horizontes_ab_pct=dif_ab,
            horas_estres_vpd=horas_estres,
            horas_riesgo_fungico_vpd=horas_fungico,
            horas_hasta_estres_suelo_a=horas_crit,
            voltaje_bateria_v=volt_actual,
        ),
        alertas,
        severidad,
    )


def _evaluar_inbeersa(
    variables: Mapping[str, ResumenVariable24h],
    series: Mapping[str, Sequence[tuple[int, float]]],
    eventos: Sequence[EventoEstacion],
    *,
    ventana_horas: float,
) -> tuple[IndicadoresPulsoInBeersa, list[str], NivelSeveridadPulso]:
    alertas: list[str] = []
    severidad = NivelSeveridadPulso.OPTIMO

    temp_int = variables.get("temperatura_interna")
    temp_ext = variables.get("temperatura_externa")
    delta_t = variables.get("delta_temp")
    calidad_aire = variables.get("calidad_aire_adc")

    if delta_t is not None:
        delta_medio: float | None = delta_t.media_24h
    elif temp_int is not None and temp_ext is not None:
        delta_medio = round(temp_int.media_24h - temp_ext.media_24h, 2)
    else:
        delta_medio = None

    vals_int = [v for _, v in series.get("temperatura_interna", ())]
    desv_termica = _desviacion_estandar(vals_int)
    en_homeostasis = (28.0 <= temp_int.media_24h <= 32.0) if temp_int else None

    serie_pir = series.get("actividad_pir", ())
    eventos_pir = sum(1 for _, v in serie_pir if v >= 0.5)
    tasa_pir_h = round(eventos_pir / max(ventana_horas, 1.0), 2)

    audios = sum(
        1
        for ev in eventos
        if "audio" in ev.tipo_evento.lower() or (ev.archivo_ruta and ev.archivo_ruta.lower().endswith(".wav"))
    )

    if temp_int is not None and not en_homeostasis:
        severidad = NivelSeveridadPulso.CRITICO
        alertas.append(
            f"Nido fuera de homeostasis térmica ({temp_int.media_24h:.1f} °C; rango óptimo 28.0–32.0 °C)."
        )
    elif desv_termica is not None and desv_termica > 2.0:
        severidad = max(severidad, NivelSeveridadPulso.ATENCION, key=_orden_severidad)
        alertas.append(f"Oscilación térmica interna elevada (σ = {desv_termica:.2f} °C).")

    if calidad_aire is not None and calidad_aire.max_24h > 1800.0:
        severidad = max(severidad, NivelSeveridadPulso.ATENCION, key=_orden_severidad)
        alertas.append(f"Pico de gases/VOCs en colmena (MQ-135 = {calidad_aire.max_24h:.0f} ADC).")

    return (
        IndicadoresPulsoInBeersa(
            delta_temp_medio_c=delta_medio,
            desviacion_termica_nido_c=desv_termica,
            en_rango_homeostasis=en_homeostasis,
            tasa_actividad_pir_por_hora=tasa_pir_h,
            conteo_audios_bioacusticos=audios,
        ),
        alertas,
        severidad,
    )


def _evaluar_sigatoka(
    variables: Mapping[str, ResumenVariable24h],
    series: Mapping[str, Sequence[tuple[int, float]]],
) -> tuple[IndicadoresPulsoSigatoka, list[str], NivelSeveridadPulso]:
    alertas: list[str] = []
    severidad = NivelSeveridadPulso.OPTIMO

    if "hoja_humectada" in series:
        horas_hum = _horas_cumpliendo_condicion(series["hoja_humectada"], lambda v: v >= 0.5)
    elif "foliar_humedad_pct" in series:
        horas_hum = _horas_cumpliendo_condicion(series["foliar_humedad_pct"], lambda v: v >= 70.0)
    else:
        horas_hum = 0.0

    dur_var = variables.get("duracion_humeda_min")
    duracion_continua_min = dur_var.max_24h if dur_var else round(horas_hum * 60.0, 1)

    temp_aire = variables.get("temp_aire")
    hum_aire = variables.get("hum_aire")
    clima_favorable_hongo = (
        (temp_aire is None or 20.0 <= temp_aire.media_24h <= 32.0)
        and (hum_aire is None or hum_aire.media_24h >= 80.0)
    )
    alerta_infeccion = (duracion_continua_min >= 360.0 or horas_hum >= 6.0) and clima_favorable_hongo

    grados_viento = [v for _, v in series.get("direccion_viento_grados", ())]
    rumbo_dom = promedio_vectorial_grados(grados_viento)

    # Si lluvia_mm_min se muestrea cada 5 min, cada muestra aporta valor * 5 min;
    # si solo hay pocas muestras puntuales, usamos la integración por intervalo en minutos.
    serie_lluvia = sorted(series.get("lluvia_mm_min", ()), key=lambda p: p[0])
    lluvia_mm = 0.0
    for idx, (ts, mm_min) in enumerate(serie_lluvia):
        if mm_min <= 0:
            continue
        minutos = (
            min(max((serie_lluvia[idx + 1][0] - ts) / 60.0, 1.0), 30.0)
            if idx + 1 < len(serie_lluvia)
            else 5.0
        )
        lluvia_mm += mm_min * minutos
    lluvia_mm = round(lluvia_mm, 2)

    if alerta_infeccion:
        severidad = NivelSeveridadPulso.CRITICO
        alertas.append(
            f"Ventana crítica de infección por Sigatoka ({duracion_continua_min:.0f} min de hoja mojada)."
        )
    elif duracion_continua_min >= 180.0 or horas_hum >= 3.0:
        severidad = max(severidad, NivelSeveridadPulso.ATENCION, key=_orden_severidad)
        alertas.append(f"Humectación foliar prolongada ({horas_hum:.1f} h acumuladas).")

    return (
        IndicadoresPulsoSigatoka(
            horas_humectacion_foliar_24h=horas_hum,
            duracion_humectacion_continua_min=duracion_continua_min,
            alerta_infeccion_fungica=alerta_infeccion,
            rumbo_viento_dominante_grados=rumbo_dom,
            precipitacion_acumulada_mm=lluvia_mm,
        ),
        alertas,
        severidad,
    )


def _evaluar_conservacion(
    variables: Mapping[str, ResumenVariable24h],
    series: Mapping[str, Sequence[tuple[int, float]]],
) -> tuple[IndicadoresPulsoConservacion, list[str], NivelSeveridadPulso]:
    alertas: list[str] = []
    severidad = NivelSeveridadPulso.OPTIMO

    serie_freatico = series.get("nivel_freatico_cm", ())
    var_freatico = (
        round(serie_freatico[-1][1] - serie_freatico[0][1], 2) if len(serie_freatico) >= 2 else None
    )

    turbas = [
        variables[k].media_24h
        for k in ("humedad_turba_a", "humedad_turba_b")
        if k in variables
    ]
    hum_turba_media = round(sum(turbas) / len(turbas), 2) if turbas else None

    rad = variables.get("radiacion_solar_wm2")
    irradiancia_max = rad.max_24h if rad else None

    serie_volt = series.get("voltaje", ())
    balance_bat = round(serie_volt[-1][1] - serie_volt[0][1], 3) if len(serie_volt) >= 2 else None

    if var_freatico is not None and var_freatico <= -5.0:
        severidad = max(severidad, NivelSeveridadPulso.ATENCION, key=_orden_severidad)
        alertas.append(f"Descenso de nivel freático en turbera ({var_freatico:.1f} cm en 24h).")

    if hum_turba_media is not None and hum_turba_media < 60.0:
        severidad = NivelSeveridadPulso.CRITICO
        alertas.append(f"Desecación de colchón de Sphagnum (humedad media {hum_turba_media:.1f}% < 60%).")

    return (
        IndicadoresPulsoConservacion(
            variacion_nivel_freatico_cm=var_freatico,
            humedad_turba_media_pct=hum_turba_media,
            irradiancia_max_wm2=irradiancia_max,
            balance_bateria_v=balance_bat,
        ),
        alertas,
        severidad,
    )


def _orden_severidad(nivel: NivelSeveridadPulso) -> int:
    orden = {
        NivelSeveridadPulso.SIN_DATOS: 0,
        NivelSeveridadPulso.OPTIMO: 1,
        NivelSeveridadPulso.ATENCION: 2,
        NivelSeveridadPulso.CRITICO: 3,
    }
    return orden[nivel]


def construir_resumen_pulso_24h(
    estacion: Estacion,
    series_por_variable: Mapping[str, Sequence[tuple[int, float]]],
    *,
    desde_epoch: int,
    hasta_epoch: int,
    unidades_por_variable: Mapping[str, str | None] | None = None,
    eventos: Sequence[EventoEstacion] = (),
    muestras_esperadas: int = MUESTRAS_ESPERADAS_24H,
) -> ResumenPulso24h:
    """Construye el ``ResumenPulso24h`` determinista adaptado al ``TipoEstacion``."""
    unidades = unidades_por_variable or {}
    resumen_vars: dict[str, ResumenVariable24h] = {}

    for variable, puntos in sorted(series_por_variable.items()):
        if not puntos:
            continue
        ordenados = sorted(puntos, key=lambda p: p[0])
        valores = [float(v) for _, v in ordenados]
        n = len(valores)
        tasa = tasa_cambio_por_hora(ordenados)
        tendencia = clasificar_tendencia(tasa)
        completitud = min(100.0, round((n / max(muestras_esperadas, 1)) * 100.0, 1))

        resumen_vars[variable] = ResumenVariable24h(
            variable=variable,
            unidad=unidades.get(variable),
            ultimo_valor=round(valores[-1], 3),
            ultimo_ts_epoch=ordenados[-1][0],
            media_24h=round(sum(valores) / n, 3),
            min_24h=round(min(valores), 3),
            max_24h=round(max(valores), 3),
            tendencia=tendencia,
            tasa_hora=tasa,
            muestras=n,
            completitud_pct=completitud,
        )

    if not resumen_vars:
        return ResumenPulso24h(
            estacion_id=estacion.id,
            codigo_estacion=estacion.codigo,
            nombre_estacion=estacion.nombre,
            tipo_estacion=estacion.tipo,
            desde_epoch=desde_epoch,
            hasta_epoch=hasta_epoch,
            severidad=NivelSeveridadPulso.SIN_DATOS,
            completitud_global_pct=0.0,
            variables={},
            alertas_detectadas=("Sin telemetría registrada en la ventana consultada.",),
            diagnostico_determinista=(
                f"[{estacion.nombre}] Sin lecturas válidas en el periodo. "
                "Verifique enlace RF/Ubidots o importe datos desde MicroSD."
            ),
        )

    completitud_global = round(
        sum(rv.completitud_pct for rv in resumen_vars.values()) / len(resumen_vars),
        1,
    )
    ventana_horas = max((hasta_epoch - desde_epoch) / 3600.0, 1.0)

    inti_ind: IndicadoresPulsoInti | None = None
    inbeersa_ind: IndicadoresPulsoInBeersa | None = None
    sigatoka_ind: IndicadoresPulsoSigatoka | None = None
    conservacion_ind: IndicadoresPulsoConservacion | None = None
    alertas: list[str] = []
    severidad = NivelSeveridadPulso.OPTIMO

    if estacion.tipo is TipoEstacion.TERRABIT_INTI:
        inti_ind, alertas, severidad = _evaluar_inti(resumen_vars, series_por_variable)
    elif estacion.tipo is TipoEstacion.INBEERSA:
        inbeersa_ind, alertas, severidad = _evaluar_inbeersa(
            resumen_vars, series_por_variable, eventos, ventana_horas=ventana_horas
        )
    elif estacion.tipo is TipoEstacion.SIGATOKA:
        sigatoka_ind, alertas, severidad = _evaluar_sigatoka(resumen_vars, series_por_variable)
    elif estacion.tipo is TipoEstacion.CONSERVACION:
        conservacion_ind, alertas, severidad = _evaluar_conservacion(resumen_vars, series_por_variable)

    if alert_txt := "; ".join(alertas):
        diagnostico = (
            f"[{estacion.nombre} · {severidad.value.upper()}] "
            f"Completitud {completitud_global:.1f}% ({len(resumen_vars)} variables activas). "
            f"Hallazgos: {alert_txt}"
        )
    else:
        diagnostico = (
            f"[{estacion.nombre} · ÓPTIMO] "
            f"Operación nominal con completitud del {completitud_global:.1f}% "
            f"en {len(resumen_vars)} variables monitoreadas."
        )

    return ResumenPulso24h(
        estacion_id=estacion.id,
        codigo_estacion=estacion.codigo,
        nombre_estacion=estacion.nombre,
        tipo_estacion=estacion.tipo,
        desde_epoch=desde_epoch,
        hasta_epoch=hasta_epoch,
        severidad=severidad,
        completitud_global_pct=completitud_global,
        variables=resumen_vars,
        alertas_detectadas=tuple(alertas),
        diagnostico_determinista=diagnostico,
        inti=inti_ind,
        inbeersa=inbeersa_ind,
        sigatoka=sigatoka_ind,
        conservacion=conservacion_ind,
    )
