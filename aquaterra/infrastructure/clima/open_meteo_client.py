"""Cliente meteorológico Open-Meteo (100 % gratuito, sin API Key) para caché predictivo offline.

Alimenta la tabla `pronostico_clima_cache` en SQLite para que el `SafetyInterlockEngine`
(Candado 1: Lluvia Inminente) y el `generar_recomendacion_proactiva` de la Fase B3
operen con datos reales de precipitación esperada, probabilidad de lluvia y
evapotranspiración de referencia FAO-56 ($ET_0$).

Coordenadas base por defecto: Campus Universidad Tecnológica de Pereira (UTP), Colombia
(`4.7905° N, -75.6904° O`).
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from aquaterra.core import tiempo
from aquaterra.core.domain import Estacion, PuntoPronosticoClima

LATITUD_UTP_PEREIRA = 4.7905
LONGITUD_UTP_PEREIRA = -75.6904
ALTITUD_UTP_PEREIRA_M = 1450.0

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


@dataclass(frozen=True, slots=True)
class ResultadoSyncClima:
    """Resumen de actualización del caché meteorológico de una estación."""

    estacion_id: int
    latitud: float
    longitud: float
    puntos_descargados: int
    puntos_guardados: int


def parsear_respuesta_open_meteo(
    datos: dict[str, Any],
    *,
    estacion_id: int,
) -> list[PuntoPronosticoClima]:
    """Convierte el bloque `hourly` de Open-Meteo en entidades `PuntoPronosticoClima`."""
    hourly = datos.get("hourly")
    if not isinstance(hourly, dict):
        return []

    tiempos = hourly.get("time") or []
    temps = hourly.get("temperature_2m") or []
    hums = hourly.get("relative_humidity_2m") or []
    probs = hourly.get("precipitation_probability") or []
    lluvias = hourly.get("precipitation") or []
    vientos = hourly.get("wind_speed_10m") or []
    et0s = hourly.get("et0_fao_evapotranspiration") or []

    puntos: list[PuntoPronosticoClima] = []
    for idx, t_str in enumerate(tiempos):
        if not isinstance(t_str, str):
            continue
        # Open-Meteo devuelve ISO local sin segundos, p. ej. "2026-11-13T23:00"
        dt_local = datetime.fromisoformat(t_str).replace(tzinfo=tiempo.ZONA_COLOMBIA)
        ts_epoch = tiempo.a_epoch(dt_local)
        ts_iso = tiempo.a_iso(dt_local)

        def _val(lista: list[Any], pos: int) -> float | None:
            if pos < len(lista) and lista[pos] is not None:
                return round(float(lista[pos]), 2)
            return None

        # Open-Meteo entrega wind_speed_10m en km/h por defecto; si se pide m/s con wind_speed_unit=ms ya viene en m/s
        puntos.append(
            PuntoPronosticoClima(
                estacion_id=estacion_id,
                ts_objetivo_epoch=ts_epoch,
                ts_objetivo_iso=ts_iso,
                temp_c=_val(temps, idx),
                hum_relativa_pct=_val(hums, idx),
                lluvia_prob_pct=_val(probs, idx),
                lluvia_mm=_val(lluvias, idx),
                viento_ms=_val(vientos, idx),
                et0_mm=_val(et0s, idx),
            )
        )
    return puntos


class ClienteOpenMeteo:
    """Conector HTTP hacia Open-Meteo API."""

    def __init__(
        self,
        *,
        base_url: str = OPEN_METEO_FORECAST_URL,
        timeout_segundos: float = 12.0,
    ) -> None:
        self._base_url = base_url
        self._timeout = timeout_segundos

    def descargar_pronostico_estacion(
        self,
        estacion: Estacion,
        *,
        dias: int = 3,
    ) -> tuple[float, float, list[PuntoPronosticoClima]]:
        """Descarga pronóstico horario para las coordenadas de la estación (o UTP Pereira por defecto)."""
        lat = estacion.latitud if estacion.latitud is not None else LATITUD_UTP_PEREIRA
        lon = estacion.longitud if estacion.longitud is not None else LONGITUD_UTP_PEREIRA

        params = {
            "latitude": f"{lat:.4f}",
            "longitude": f"{lon:.4f}",
            "hourly": (
                "temperature_2m,relative_humidity_2m,precipitation_probability,"
                "precipitation,wind_speed_10m,et0_fao_evapotranspiration"
            ),
            "wind_speed_unit": "ms",
            "timezone": "America/Bogota",
            "forecast_days": str(max(1, min(7, dias))),
        }
        url = f"{self._base_url}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "SalviaBIoT/6.0"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            datos = json.loads(resp.read().decode("utf-8"))

        puntos = parsear_respuesta_open_meteo(datos, estacion_id=estacion.id)
        return lat, lon, puntos
