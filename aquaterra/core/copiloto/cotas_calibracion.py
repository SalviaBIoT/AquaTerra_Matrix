"""Cotas físicas y agronómicas duras para recalibración de sensores y umbrales.

Resuelve el Riesgo Crítico 3 de la Arquitectura Maestra (alucinación de IA en la
pestaña de Soporte y Calibración): ningún ajuste propuesto por un modelo externo
(Gemini / Ollama) o por un operador puede superar las cotas absolutas ni el paso
máximo permitido por iteración (`delta_max_por_paso`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CotaParametro:
    """Definición metrológica y agronómica de un parámetro calibrable."""

    clave: str
    minimo: float
    maximo: float
    delta_max_por_paso: float
    valor_por_defecto: float
    unidad: str
    descripcion: str


CATALOGO_COTAS_CALIBRACION: dict[str, CotaParametro] = {
    "umbral_humedad_pct": CotaParametro(
        clave="umbral_humedad_pct",
        minimo=15.0,
        maximo=85.0,
        delta_max_por_paso=10.0,
        valor_por_defecto=45.0,
        unidad="%",
        descripcion="Umbral crítico de humedad volumétrica de suelo para disparo de riego.",
    ),
    "capacidad_campo_pct": CotaParametro(
        clave="capacidad_campo_pct",
        minimo=35.0,
        maximo=95.0,
        delta_max_por_paso=10.0,
        valor_por_defecto=70.0,
        unidad="%",
        descripcion="Capacidad de campo estimada del horizonte radicular.",
    ),
    "lamina_max_l_m2": CotaParametro(
        clave="lamina_max_l_m2",
        minimo=1.0,
        maximo=25.0,
        delta_max_por_paso=5.0,
        valor_por_defecto=8.0,
        unidad="L/m2",
        descripcion="Lámina máxima de riego por evento individual antes de bloqueo anti-inundación.",
    ),
    "adc_seco": CotaParametro(
        clave="adc_seco",
        minimo=1800.0,
        maximo=4095.0,
        delta_max_por_paso=350.0,
        valor_por_defecto=3200.0,
        unidad="cuentas_adc",
        descripcion="Lectura ADC (12 bits ESP32) del sensor capacitivo en aire/suelo seco (0 %).",
    ),
    "adc_agua": CotaParametro(
        clave="adc_agua",
        minimo=600.0,
        maximo=2600.0,
        delta_max_por_paso=350.0,
        valor_por_defecto=1450.0,
        unidad="cuentas_adc",
        descripcion="Lectura ADC (12 bits ESP32) del sensor capacitivo sumergido en agua (100 %).",
    ),
    "ema_alpha": CotaParametro(
        clave="ema_alpha",
        minimo=0.05,
        maximo=0.50,
        delta_max_por_paso=0.15,
        valor_por_defecto=0.20,
        unidad="adimensional",
        descripcion="Factor de suavizado del filtro de media móvil exponencial (EMA) del ADC.",
    ),
    "vpd_alerta_kpa": CotaParametro(
        clave="vpd_alerta_kpa",
        minimo=0.8,
        maximo=3.0,
        delta_max_por_paso=0.5,
        valor_por_defecto=1.6,
        unidad="kPa",
        descripcion="Umbral de Déficit de Presión de Vapor (VPD) para alerta de estrés estomático.",
    ),
    "temp_nido_min_c": CotaParametro(
        clave="temp_nido_min_c",
        minimo=26.0,
        maximo=34.0,
        delta_max_por_paso=2.0,
        valor_por_defecto=29.0,
        unidad="°C",
        descripcion="Temperatura mínima de seguridad del nido de cría en colmenas InBeersa (Melipona).",
    ),
    "umbral_mojado_foliar_pct": CotaParametro(
        clave="umbral_mojado_foliar_pct",
        minimo=55.0,
        maximo=90.0,
        delta_max_por_paso=10.0,
        valor_por_defecto=70.0,
        unidad="%",
        descripcion="Umbral de humectación foliar para contabilizar horas de riesgo de Sigatoka.",
    ),
}


PARAMETROS_CALIBRACION_POR_DEFECTO: dict[str, float] = {
    clave: cota.valor_por_defecto for clave, cota in CATALOGO_COTAS_CALIBRACION.items()
}


@dataclass(frozen=True, slots=True)
class RecorteParametro:
    """Detalle trazable cuando un ajuste propuesto fue acotado por los guardarraíles."""

    clave: str
    valor_original: float
    valor_acotado: float
    motivo: str


@dataclass(frozen=True, slots=True)
class ResultadoAuditoriaCalibracion:
    """Resultado de pasar los ajustes propuestos por el filtro determinista de seguridad."""

    ajustes_seguros: dict[str, float]
    recortes_aplicados: tuple[RecorteParametro, ...]
    claves_rechazadas: tuple[str, ...]
    advertencias_seguridad: tuple[str, ...]

    @property
    def tuvo_intervencion_guardarrailes(self) -> bool:
        return bool(self.recortes_aplicados or self.claves_rechazadas)


def auditar_y_acotar_ajustes(
    propuestos: dict[str, Any] | None,
    parametros_actuales: dict[str, Any] | None = None,
) -> ResultadoAuditoriaCalibracion:
    """Valida, recorta y asegura cualquier diccionario de ajustes de calibración.

    Reglas deterministas aplicadas:
    1. Rechaza cualquier clave que no exista en `CATALOGO_COTAS_CALIBRACION` o cuyo
       valor no sea numérico finito.
    2. Limita el cambio máximo por iteración a `[-delta_max_por_paso, +delta_max_por_paso]`
       respecto al valor actual (o al valor por defecto si no existía).
    3. Recorta el resultado dentro del rango físico absoluto `[minimo, maximo]`.
    4. Verifica invariantes cruzadas:
       - `umbral_humedad_pct` debe quedar al menos 5 puntos por debajo de `capacidad_campo_pct`.
       - `adc_agua` debe quedar al menos 400 cuentas por debajo de `adc_seco`.
    """
    if not propuestos:
        return ResultadoAuditoriaCalibracion(
            ajustes_seguros={},
            recortes_aplicados=(),
            claves_rechazadas=(),
            advertencias_seguridad=(),
        )

    base: dict[str, float] = dict(PARAMETROS_CALIBRACION_POR_DEFECTO)
    if parametros_actuales:
        for k, v in parametros_actuales.items():
            if k in CATALOGO_COTAS_CALIBRACION and isinstance(v, (int, float)) and not isinstance(v, bool):
                base[k] = float(v)

    ajustes_seguros: dict[str, float] = {}
    recortes: list[RecorteParametro] = []
    rechazadas: list[str] = []
    advertencias: list[str] = []

    for clave, valor_bruto in propuestos.items():
        if clave not in CATALOGO_COTAS_CALIBRACION:
            rechazadas.append(clave)
            advertencias.append(f"Parámetro desconocido rechazado por guardarraíl: '{clave}'.")
            continue

        if isinstance(valor_bruto, bool) or not isinstance(valor_bruto, (int, float)):
            try:
                valor_num = float(str(valor_bruto).strip())
            except (ValueError, TypeError):
                rechazadas.append(clave)
                advertencias.append(f"Valor no numérico rechazado para '{clave}': {valor_bruto!r}.")
                continue
        else:
            valor_num = float(valor_bruto)

        cota = CATALOGO_COTAS_CALIBRACION[clave]
        actual = base.get(clave, cota.valor_por_defecto)
        valor_trabajo = valor_num
        motivos_recorte: list[str] = []

        # 1. Control de salto máximo por iteración (evita cambios bruscos de calibración)
        delta = valor_trabajo - actual
        if abs(delta) > cota.delta_max_por_paso + 1e-9:
            signo = 1.0 if delta > 0 else -1.0
            valor_trabajo = actual + signo * cota.delta_max_por_paso
            motivos_recorte.append(
                f"cambio por paso limitado a ±{cota.delta_max_por_paso} {cota.unidad} desde {actual}"
            )

        # 2. Control de cotas físicas absolutas [minimo, maximo]
        if valor_trabajo < cota.minimo:
            valor_trabajo = cota.minimo
            motivos_recorte.append(f"acotado al mínimo físico ({cota.minimo} {cota.unidad})")
        elif valor_trabajo > cota.maximo:
            valor_trabajo = cota.maximo
            motivos_recorte.append(f"acotado al máximo físico ({cota.maximo} {cota.unidad})")

        decimales = 3 if cota.unidad == "adimensional" else 2
        valor_final = round(valor_trabajo, decimales)
        ajustes_seguros[clave] = valor_final

        if motivos_recorte:
            motivo_str = "; ".join(motivos_recorte)
            recortes.append(
                RecorteParametro(
                    clave=clave,
                    valor_original=round(valor_num, 3),
                    valor_acotado=valor_final,
                    motivo=motivo_str,
                )
            )
            advertencias.append(
                f"Guardarraíl en '{clave}': propuesto {valor_num} -> ajustado a {valor_final} ({motivo_str})."
            )

    # 3. Verificación de invariantes cruzadas entre parámetros acoplados
    estado_simulado = {**base, **ajustes_seguros}

    umbral_h = estado_simulado["umbral_humedad_pct"]
    cap_campo = estado_simulado["capacidad_campo_pct"]
    if umbral_h > cap_campo - 5.0:
        nuevo_umbral = round(max(CATALOGO_COTAS_CALIBRACION["umbral_humedad_pct"].minimo, cap_campo - 5.0), 2)
        if "umbral_humedad_pct" in ajustes_seguros:
            orig = ajustes_seguros["umbral_humedad_pct"]
            ajustes_seguros["umbral_humedad_pct"] = nuevo_umbral
            recortes.append(
                RecorteParametro(
                    clave="umbral_humedad_pct",
                    valor_original=orig,
                    valor_acotado=nuevo_umbral,
                    motivo=f"debe ser <= capacidad_campo_pct ({cap_campo}%) - 5%",
                )
            )
            advertencias.append(
                f"Invariante agronómica: 'umbral_humedad_pct' ajustado a {nuevo_umbral}% "
                f"para mantener margen de 5% bajo capacidad de campo ({cap_campo}%)."
            )

    adc_agua = estado_simulado["adc_agua"]
    adc_seco = estado_simulado["adc_seco"]
    if adc_agua > adc_seco - 400.0 and "adc_agua" in ajustes_seguros:
        orig_agua = ajustes_seguros["adc_agua"]
        nuevo_agua = round(
            max(CATALOGO_COTAS_CALIBRACION["adc_agua"].minimo, adc_seco - 400.0), 2
        )
        ajustes_seguros["adc_agua"] = nuevo_agua
        recortes.append(
            RecorteParametro(
                clave="adc_agua",
                valor_original=orig_agua,
                valor_acotado=nuevo_agua,
                motivo=f"debe ser <= adc_seco ({adc_seco}) - 400 cuentas",
            )
        )
        advertencias.append(
            f"Invariante ADC capacitivo: 'adc_agua' ajustado a {nuevo_agua} "
            f"para mantener separación mínima de 400 cuentas respecto a 'adc_seco' ({adc_seco})."
        )

    return ResultadoAuditoriaCalibracion(
        ajustes_seguros=ajustes_seguros,
        recortes_aplicados=tuple(recortes),
        claves_rechazadas=tuple(rechazadas),
        advertencias_seguridad=tuple(advertencias),
    )
