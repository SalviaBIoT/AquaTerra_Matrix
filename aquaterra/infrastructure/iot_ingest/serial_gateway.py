"""Receptor USB-Serial para Gateway de Radiofrecuencia (`nRF24L01+ PA+LNA` 2.4 GHz / `LoRa`).

En la arquitectura física de campo de TerraBit:
- Los nodos remotos transmiten un `struct` binario compacto (<= 32 bytes en el
  caso del transceptor `nRF24L01+ PA+LNA` a 2.4 GHz, o hasta 255 bytes en LoRa).
- El ESP32 Receptor (Gateway) conectado por USB al PC recibe el paquete por SPI
  y lo vuelca como una línea de texto por el puerto serie (`115200 baud`).

Este módulo soporta 3 dialectos de línea serial para facilitar el prototipado C++17:
1. **TerraBit Frame v1 (JSONL):**
   `{"v":1,"id":"terrabit-nodointi","ts":1763090000,"m":{"suelo_a":77.29,"temp_aire":18.94,"hum_aire":94.94}}`
2. **Trama Compacta Pipe/Key-Value (`NRF24|...` — cero librerías JSON en el receptor):**
   `NRF24|inbeersa-nodo01|temperatura_interna=23.4,humedad_interna=85.4,vpd_nido=0.42,actividad_pir=0`
3. **JSON Plano estilo Ubidots:**
   `{"device":"terrabit-nodointi","suelo-a":77.29,"suelo-b":97.09}`
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from aquaterra.core import tiempo
from aquaterra.core.agronomia.psicrometria import vpd_kpa
from aquaterra.core.domain import LecturaSensor
from aquaterra.infrastructure.iot_ingest.adaptadores import parsear_payload_ubidots


@dataclass(frozen=True, slots=True)
class TramaGatewayDecodificada:
    """Resultado de decodificar una línea recibida desde el ESP32 Gateway por USB-Serial."""

    device_label: str
    ts_epoch: int
    metricas: dict[str, float]
    protocolo: str  # "terrabit_v1" | "nrf24_kv" | "json_plano"


def decodificar_linea_gateway(
    linea: str,
    *,
    ts_epoch_defecto: int | None = None,
) -> TramaGatewayDecodificada | None:
    """Decodifica una línea de telemetría serial de `nRF24L01+ PA+LNA` o `LoRa`."""
    limpia = linea.strip()
    if not limpia or limpia.startswith("#") or limpia.startswith("//"):
        return None

    ahora_ep = ts_epoch_defecto if ts_epoch_defecto is not None else tiempo.a_epoch(tiempo.ahora())

    # Dialecto 2: Trama compacta sin JSON -> NRF24|<device_label>|<k=v,k=v>
    if limpia.upper().startswith(("NRF24|", "LORA|", "RADIO|")):
        partes = limpia.split("|")
        if len(partes) < 3:
            raise ValueError(f"Trama pipe incompleta: {limpia!r}")
        device_label = partes[1].strip()
        bloque_kv = partes[2].strip()
        ts_ep = ahora_ep
        if len(partes) >= 4 and partes[3].strip().isdigit():
            ts_ep = int(partes[3].strip())

        metricas: dict[str, float] = {}
        for par in bloque_kv.split(","):
            if "=" not in par:
                continue
            k, v = par.split("=", 1)
            clave = k.strip().lower().replace("-", "_")
            if clave in ("ts", "timestamp", "epoch"):
                ts_ep = int(float(v.strip()))
            else:
                metricas[clave] = float(v.strip())

        _enriquecer_variables_derivadas(metricas)
        return TramaGatewayDecodificada(
            device_label=device_label,
            ts_epoch=ts_ep,
            metricas=metricas,
            protocolo="nrf24_kv",
        )

    # Dialectos 1 y 3: JSON
    if not limpia.startswith("{"):
        return None

    datos: dict[str, Any] = json.loads(limpia)
    if not isinstance(datos, dict):
        raise ValueError("La trama JSON del Gateway no es un objeto.")

    device_label = str(
        datos.get("id") or datos.get("device") or datos.get("estacion") or datos.get("colmena") or ""
    ).strip()
    if not device_label:
        raise ValueError("La trama JSON del Gateway no incluye identificador ('id' o 'device').")

    ts_raw = datos.get("ts") or datos.get("timestamp")
    if isinstance(ts_raw, (int, float)) and ts_raw > 0:
        ts_ep = int(ts_raw // 1000) if ts_raw > 100_000_000_000 else int(ts_raw)
    else:
        ts_ep = ahora_ep

    # Dialecto 1: TerraBit Frame Protocol v1 con diccionario anidado `"m": {...}`
    if isinstance(datos.get("m"), dict):
        metricas_v1: dict[str, float] = {}
        for k, v in datos["m"].items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                metricas_v1[str(k).strip().lower().replace("-", "_")] = float(v)
        if isinstance(datos.get("bat"), (int, float)) and "voltaje" not in metricas_v1:
            metricas_v1["voltaje"] = float(datos["bat"])
        _enriquecer_variables_derivadas(metricas_v1)
        return TramaGatewayDecodificada(
            device_label=device_label,
            ts_epoch=ts_ep,
            metricas=metricas_v1,
            protocolo="terrabit_v1",
        )

    # Dialecto 3: JSON plano estilo Ubidots
    claves_meta = {"id", "device", "estacion", "colmena", "ts", "timestamp", "v", "ev"}
    metricas_planas: dict[str, float] = {}
    for k, v in datos.items():
        if k in claves_meta:
            continue
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            metricas_planas[str(k).strip().lower().replace("-", "_")] = float(v)

    _enriquecer_variables_derivadas(metricas_planas)
    return TramaGatewayDecodificada(
        device_label=device_label,
        ts_epoch=ts_ep,
        metricas=metricas_planas,
        protocolo="json_plano",
    )


def _enriquecer_variables_derivadas(metricas: dict[str, float]) -> None:
    """Calcula VPD o delta_temp en el servidor para ahorrar bytes en el paquete de 32B del nRF24L01+."""
    if "vpd" not in metricas and "temp_aire" in metricas and "hum_aire" in metricas:
        t_a = metricas["temp_aire"]
        h_a = metricas["hum_aire"]
        if -20.0 <= t_a <= 65.0 and 0.0 <= h_a <= 100.0:
            metricas["vpd"] = vpd_kpa(t_a, h_a)

    if (
        "vpd_nido" not in metricas
        and "temperatura_interna" in metricas
        and "humedad_interna" in metricas
    ):
        t_i = metricas["temperatura_interna"]
        h_i = metricas["humedad_interna"]
        if -10.0 <= t_i <= 60.0 and 0.0 <= h_i <= 100.0:
            metricas["vpd_nido"] = vpd_kpa(t_i, h_i)

    if (
        "delta_temp" not in metricas
        and "temperatura_interna" in metricas
        and "temperatura_externa" in metricas
    ):
        metricas["delta_temp"] = round(
            metricas["temperatura_interna"] - metricas["temperatura_externa"], 2
        )


def convertir_trama_a_lecturas(
    trama: TramaGatewayDecodificada,
    *,
    estacion_id: int,
) -> list[LecturaSensor]:
    """Convierte una `TramaGatewayDecodificada` en entidades `LecturaSensor` listas para SQLite."""
    return parsear_payload_ubidots(
        trama.metricas,
        estacion_id=estacion_id,
        ts_epoch_defecto=trama.ts_epoch,
        fuente="lora",  # Canal de radiofrecuencia local (nRF24L01+ 2.4 GHz / LoRa 915 MHz)
    )
