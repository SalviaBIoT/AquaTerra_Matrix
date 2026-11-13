"""Reglas de balance hídrico y decisión de riego.

En v3.x la humedad de la parcela es un valor declarado/simulado; desde v5.0 será
la lectura real (filtrada con EMA y calibrada seco/agua en el firmware) del sensor
capacitivo asociado a la parcela vía ``estacion_id``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

# Umbral crítico heredado de v3.2 (monitor_ui pintaba en rojo si humedad < 40 %).
UMBRAL_CRITICO_PCT = 40.0

# SIMULACIÓN heredada de v3.2: tras regar, la humedad "sube" a 95 %.
# Se mantiene explícita y nombrada para reemplazarla por la lectura real del
# sensor en v5.0 (ver PRP-002). No representa ningún modelo físico.
HUMEDAD_POST_RIEGO_SIMULADA_PCT = 95.0


class EstadoHumedad(StrEnum):
    CRITICO = "critico"
    ADECUADO = "adecuado"


def clasificar_humedad(humedad_pct: float, umbral_critico: float = UMBRAL_CRITICO_PCT) -> EstadoHumedad:
    return EstadoHumedad.CRITICO if humedad_pct < umbral_critico else EstadoHumedad.ADECUADO


@dataclass(frozen=True, slots=True)
class DecisionRiego:
    regar: bool
    humedad_actual_pct: float
    umbral_pct: float
    motivo: str


def decidir_riego(humedad_actual_pct: float, umbral_pct: float) -> DecisionRiego:
    """Regla de disparo por umbral (control on/off), idéntica a v3.2."""
    if humedad_actual_pct < umbral_pct:
        return DecisionRiego(
            True, humedad_actual_pct, umbral_pct,
            f"Humedad {humedad_actual_pct:.0f} % < umbral {umbral_pct:.0f} %: déficit hídrico.",
        )
    return DecisionRiego(
        False, humedad_actual_pct, umbral_pct,
        f"Humedad {humedad_actual_pct:.0f} % ≥ umbral {umbral_pct:.0f} %: no se requiere riego.",
    )
