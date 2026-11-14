"""Cliente HTTP incremental para Ubidots Industrial REST API (`v1.6` / `v2.0`).

Permite que `AquaTerra Matrix` actúe como historiador maestro local de las
estaciones ESP32 que transmiten por WiFi/SIM a Ubidots (`terrabit-nodointi`,
`inbeersa-nodo01`, etc.):
1. Consulta en SQLite la marca de agua `RepositorioLecturas.ultimo_epoch(estacion_id)`.
2. Descarga únicamente los valores nuevos posteriores a esa marca (`?start=<ms>`).
3. Normaliza nombres con guiones (`suelo-a` -> `suelo_a`, `temp-raiz` -> `temp_raiz`)
   y filtra centinelas (`voltaje = -1` -> `calidad = 2`) mediante `parsear_payload_ubidots`.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from aquaterra.core.domain import Estacion, LecturaSensor, TipoEstacion
from aquaterra.infrastructure.iot_ingest.adaptadores import parsear_payload_ubidots

log = logging.getLogger(__name__)

UBIDOTS_BASE_URL_V16 = "https://industrial.api.ubidots.com/api/v1.6"

# Variables conocidas por familia de estación en Ubidots (según despliegue real TerraBit)
VARIABLES_UBIDOTS_POR_TIPO: dict[TipoEstacion, tuple[str, ...]] = {
    TipoEstacion.TERRABIT_INTI: (
        "suelo-a",
        "suelo-b",
        "temp-aire",
        "hum-aire",
        "temp-raiz",
        "presion",
        "vpd",
        "voltaje",
    ),
    TipoEstacion.INBEERSA: (
        "temperatura_interna",
        "humedad_interna",
        "vpd_nido",
        "actividad_pir",
        "lluvia_evento",
        "temperatura_externa",
        "humedad_externa",
        "delta_temp",
    ),
    TipoEstacion.SIGATOKA: (
        "lluvia_mm_min",
        "velocidad_viento_ms",
        "temp_aire",
        "hum_aire",
        "foliar_humedad_pct",
        "duracion_humeda_min",
    ),
    TipoEstacion.CONSERVACION: (
        "nivel_freatico_cm",
        "humedad_turba_a",
        "humedad_turba_b",
        "radiacion_solar_wm2",
        "temp_suelo_paramo",
        "temp_aire",
        "hum_aire",
    ),
}


@dataclass(frozen=True, slots=True)
class ResultadoSyncUbidots:
    """Resumen de una corrida de sincronización incremental desde Ubidots."""

    estacion_id: int
    device_label: str
    variables_consultadas: int
    lecturas_descargadas: int
    lecturas_nuevas_insertadas: int
    desde_epoch: int | None
    errores_variables: tuple[str, ...] = ()


class ClienteUbidotsREST:
    """Conector HTTP sin dependencias externas hacia Ubidots Industrial API."""

    def __init__(
        self,
        *,
        token: str | None = None,
        base_url: str = UBIDOTS_BASE_URL_V16,
        timeout_segundos: float = 15.0,
    ) -> None:
        self._token = (
            token
            or os.environ.get("UBIDOTS_TOKEN")
            or os.environ.get("AQUATERRA_UBIDOTS_TOKEN")
            or ""
        ).strip()
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_segundos

    @property
    def tiene_token(self) -> bool:
        return bool(self._token)

    def _get_json(self, ruta: str, params: dict[str, str | int] | None = None) -> dict:
        if not self._token:
            raise RuntimeError(
                "No se ha configurado UBIDOTS_TOKEN en las variables de entorno."
            )
        url = f"{self._base_url}/{ruta.lstrip('/')}"
        if params:
            query = urllib.parse.urlencode(params)
            url = f"{url}?{query}"

        req = urllib.request.Request(
            url,
            headers={
                "X-Auth-Token": self._token,
                "Accept": "application/json",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def obtener_valores_variable(
        self,
        device_label: str,
        variable_label: str,
        *,
        desde_epoch: int | None = None,
        page_size: int = 100,
    ) -> list[dict]:
        """Descarga la serie histórica reciente de una variable de un dispositivo Ubidots."""
        params: dict[str, str | int] = {"page_size": page_size}
        if desde_epoch is not None and desde_epoch > 0:
            # Ubidots espera el filtro `start` en milisegundos UTC
            params["start"] = (int(desde_epoch) + 1) * 1000

        ruta = f"devices/{urllib.parse.quote(device_label)}/{urllib.parse.quote(variable_label)}/values"
        datos = self._get_json(ruta, params=params)
        resultados = datos.get("results")
        return list(resultados) if isinstance(resultados, list) else []

    def descargar_lecturas_estacion(
        self,
        estacion: Estacion,
        *,
        desde_epoch: int | None = None,
        page_size: int = 100,
        variables_override: tuple[str, ...] | None = None,
    ) -> tuple[list[LecturaSensor], tuple[str, ...]]:
        """Descarga y convierte en `LecturaSensor` todas las variables activas de la estación."""
        device_label = estacion.codigo.strip()
        variables = variables_override or VARIABLES_UBIDOTS_POR_TIPO.get(
            estacion.tipo, VARIABLES_UBIDOTS_POR_TIPO[TipoEstacion.TERRABIT_INTI]
        )

        lecturas_totales: list[LecturaSensor] = []
        errores: list[str] = []

        for var_label in variables:
            try:
                puntos = self.obtener_valores_variable(
                    device_label,
                    var_label,
                    desde_epoch=desde_epoch,
                    page_size=page_size,
                )
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    # Variable opcional que aún no existe en ese dispositivo Ubidots
                    continue
                errores.append(f"{var_label}: HTTP {exc.code}")
                continue
            except Exception as exc:
                errores.append(f"{var_label}: {exc}")
                continue

            for punto in puntos:
                if "value" not in punto or "timestamp" not in punto:
                    continue
                payload_unitario = {
                    var_label: {
                        "value": punto["value"],
                        "timestamp": punto["timestamp"],
                    }
                }
                lecturas_totales.extend(
                    parsear_payload_ubidots(
                        payload_unitario,
                        estacion_id=estacion.id,
                        fuente="ubidots",
                    )
                )

        return lecturas_totales, tuple(errores)
