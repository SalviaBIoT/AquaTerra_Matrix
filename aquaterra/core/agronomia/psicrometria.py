"""Psicrometría aplicada: Déficit de Presión de Vapor (VPD).

El VPD cuantifica la "sed" de la atmósfera: la diferencia entre el vapor que el
aire PODRÍA contener a saturación y el que realmente contiene. Gobierna la
transpiración estomática y es la variable clave de las estaciones TerraBit:

    e_s(T) = 0.6108 · exp( 17.27 · T / (T + 237.3) )        [kPa]  (Tetens / FAO-56 ec. 11)
    e_a    = e_s(T) · HR / 100                               [kPa]
    VPD    = e_s − e_a = e_s · (1 − HR/100)                  [kPa]

Referencia: Allen et al. (1998), FAO Irrigation and Drainage Paper 56.

Este módulo replica en Python el cálculo que ya ejecuta el firmware del Nodo INTI,
para poder recalcular/validar el VPD de datos históricos o de estaciones que solo
reportan temperatura y humedad relativa (InBeersa, Sigatoka).
"""

from __future__ import annotations

import math
from enum import StrEnum


class ZonaVPD(StrEnum):
    RIESGO_FUNGICO = "riesgo_fungico"      # < 0.4 kPa: hoja mojada, Sigatoka/Botrytis
    PROPAGACION = "propagacion"            # 0.4–0.8 kPa: plántulas y esquejes
    OPTIMA = "optima"                      # 0.8–1.2 kPa: crecimiento vegetativo
    FLORACION = "floracion"                # 1.2–1.6 kPa: floración / estrés leve
    ESTRES_HIDRICO = "estres_hidrico"      # > 1.6 kPa: cierre estomático


def presion_saturacion_kpa(temp_c: float) -> float:
    """Presión de vapor a saturación e_s(T) por la ecuación de Tetens (kPa)."""
    if not -50.0 <= temp_c <= 70.0:
        raise ValueError(f"Temperatura fuera de rango físico de la ecuación: {temp_c} °C")
    return 0.6108 * math.exp((17.27 * temp_c) / (temp_c + 237.3))


def vpd_kpa(temp_c: float, humedad_relativa_pct: float) -> float:
    """Déficit de Presión de Vapor del aire (kPa), redondeado a 3 decimales."""
    if not 0.0 <= humedad_relativa_pct <= 100.0:
        raise ValueError(f"Humedad relativa fuera de rango: {humedad_relativa_pct} %")
    e_s = presion_saturacion_kpa(temp_c)
    return round(e_s * (1.0 - humedad_relativa_pct / 100.0), 3)


def clasificar_vpd(vpd: float) -> ZonaVPD:
    """Clasificación agronómica general del VPD (umbrales de invernadero estándar)."""
    if vpd < 0.4:
        return ZonaVPD.RIESGO_FUNGICO
    if vpd < 0.8:
        return ZonaVPD.PROPAGACION
    if vpd <= 1.2:
        return ZonaVPD.OPTIMA
    if vpd <= 1.6:
        return ZonaVPD.FLORACION
    return ZonaVPD.ESTRES_HIDRICO
