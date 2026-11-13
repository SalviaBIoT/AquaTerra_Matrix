"""Adaptadores de ingesta para las estaciones reales del Ecosistema TerraBit.

Soporta los tres contratos de datos que producen los firmwares C++17 actuales:

1. **TerraBit Nodo INTI — MicroSD CSV (``/data.csv``)**
   Generado por ``Estacion_TerraBit_Inti/src/storage.cpp``::

       Uptime,HumedadA,HumedadB,TempAire,HumAire,Presion,TempRaiz,Voltaje,VPD,SessionID
       2026/11/12 14:05:00,42.50,39.80,24.10,68.00,852.30,21.40,4.12,0.96,1

2. **InBeersa (Abejas Angelitas) — MicroSD / LittleFS JSONL (``/data.json``)**
   Generado por ``Estacion_InBeersa/src/comms.cpp`` y ``storage.cpp``::

       {"colmena":"Colmena_01","Fecha":"2026-11-12","Hora":"14:05:00","TempI":28.4,"HumedadI":76.2,"VPD":0.92,"PIR":1,"Lluvia":0}

3. **Ubidots Industrial — Payload MQTT / REST (``/v1.6/devices/<label>``)**
   Soporta tanto objetos con ``{"value": x, "timestamp": ms}`` (cola FIFO RTC SRAM
   de Nodo INTI) como valores escalares ``{"temperatura_interna": 28.4}`` (InBeersa).
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from aquaterra.core import tiempo
from aquaterra.core.domain import LecturaSensor

# Mapeo de columnas de /data.csv (Nodo INTI) -> (nombre_variable_canonico, unidad, min_fisico, max_fisico)
_ESQUEMA_NODO_INTI: dict[str, tuple[str, str, float, float]] = {
    "HumedadA": ("suelo_a", "%", 0.0, 100.0),
    "HumedadB": ("suelo_b", "%", 0.0, 100.0),
    "TempAire": ("temp_aire", "°C", -20.0, 65.0),
    "HumAire": ("hum_aire", "%", 0.0, 100.0),
    "Presion": ("presion", "hPa", 300.0, 1100.0),
    "TempRaiz": ("temp_raiz", "°C", -10.0, 60.0),
    "Voltaje": ("voltaje", "V", 0.0, 15.0),
    "VPD": ("vpd", "kPa", 0.0, 10.0),
}

# Mapeo de claves de /data.json (InBeersa) -> (nombre_variable_canonico, unidad, min_fisico, max_fisico)
_ESQUEMA_INBEERSA: dict[str, tuple[str, str, float, float]] = {
    "TempI": ("temperatura_interna", "°C", -10.0, 60.0),
    "HumedadI": ("humedad_interna", "%", 0.0, 100.0),
    "VPD": ("vpd_nido", "kPa", 0.0, 10.0),
    "PIR": ("actividad_pir", "evento", 0.0, 1.0),
    "Lluvia": ("lluvia_evento", "evento", 0.0, 1.0),
    "TempE": ("temperatura_externa", "°C", -20.0, 65.0),
    "HumedadE": ("humedad_externa", "%", 0.0, 100.0),
    "MQ135": ("calidad_aire_adc", "adc", 0.0, 4095.0),
}

# Unidades canónicas para variables recibidas desde Ubidots (con guion o guion bajo)
_UNIDADES_UBIDOTS: dict[str, tuple[str, float, float]] = {
    "suelo_a": ("%", 0.0, 100.0),
    "suelo_b": ("%", 0.0, 100.0),
    "temp_aire": ("°C", -20.0, 65.0),
    "hum_aire": ("%", 0.0, 100.0),
    "presion": ("hPa", 300.0, 1100.0),
    "temp_raiz": ("°C", -10.0, 60.0),
    "voltaje": ("V", 0.0, 15.0),
    "vpd": ("kPa", 0.0, 10.0),
    "temperatura_interna": ("°C", -10.0, 60.0),
    "humedad_interna": ("%", 0.0, 100.0),
    "vpd_nido": ("kPa", 0.0, 10.0),
    "actividad_pir": ("evento", 0.0, 1.0),
    "lluvia_evento": ("evento", 0.0, 1.0),
}


def _calidad(valor: float, minimo: float, maximo: float) -> int:
    """0 = válido, 2 = fuera de rango físico (p. ej. DHT22 reportando -200.0 °C)."""
    return 0 if (minimo <= valor <= maximo) else 2


def _parsear_fecha_hora_estacion(texto_fecha_hora: str) -> datetime:
    """Acepta ``YYYY/MM/DD HH:MM:SS`` (Nodo INTI) o ``YYYY-MM-DD HH:MM:SS`` (InBeersa)."""
    limpio = texto_fecha_hora.strip().replace("/", "-")
    momento = datetime.strptime(limpio, "%Y-%m-%d %H:%M:%S")
    return momento.replace(tzinfo=tiempo.ZONA_COLOMBIA)


def parsear_csv_nodo_inti(
    contenido_o_ruta: str | Path,
    *,
    estacion_id: int,
) -> list[LecturaSensor]:
    """Convierte el ``/data.csv`` de una estación TerraBit Nodo INTI en ``LecturaSensor``."""
    texto = contenido_o_ruta.read_text(encoding="utf-8") if isinstance(contenido_o_ruta, Path) else contenido_o_ruta

    lecturas: list[LecturaSensor] = []
    lector = csv.DictReader(io.StringIO(texto.strip()))
    for fila in lector:
        uptime = (fila.get("Uptime") or "").strip()
        if not uptime or uptime == "RTC_OFF":
            continue
        momento = _parsear_fecha_hora_estacion(uptime)
        ts_epoch = tiempo.a_epoch(momento)
        ts_iso = tiempo.a_iso(momento)

        for columna, (variable, unidad, minimo, maximo) in _ESQUEMA_NODO_INTI.items():
            bruto = fila.get(columna)
            if bruto is None or str(bruto).strip() == "":
                continue
            valor = float(bruto)
            lecturas.append(
                LecturaSensor(
                    estacion_id=estacion_id,
                    variable=variable,
                    valor=valor,
                    unidad=unidad,
                    ts_epoch=ts_epoch,
                    ts_iso=ts_iso,
                    fuente="sd_csv",
                    calidad=_calidad(valor, minimo, maximo),
                )
            )
    return lecturas


def parsear_jsonl_inbeersa(
    contenido_o_ruta: str | Path,
    *,
    estacion_id: int,
) -> list[LecturaSensor]:
    """Convierte el ``/data.json`` (JSON Lines) de InBeersa en ``LecturaSensor``."""
    texto = contenido_o_ruta.read_text(encoding="utf-8") if isinstance(contenido_o_ruta, Path) else contenido_o_ruta

    lecturas: list[LecturaSensor] = []
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        objeto: dict[str, Any] = json.loads(linea)
        fecha = str(objeto.get("Fecha") or objeto.get("fecha") or "").strip()
        hora = str(objeto.get("Hora") or objeto.get("hora") or "").strip()
        if not fecha or not hora or "RTC_OFF" in fecha:
            continue
        momento = _parsear_fecha_hora_estacion(f"{fecha} {hora}")
        ts_epoch = tiempo.a_epoch(momento)
        ts_iso = tiempo.a_iso(momento)

        for clave, (variable, unidad, minimo, maximo) in _ESQUEMA_INBEERSA.items():
            if clave not in objeto or objeto[clave] is None:
                continue
            valor = float(objeto[clave])
            lecturas.append(
                LecturaSensor(
                    estacion_id=estacion_id,
                    variable=variable,
                    valor=valor,
                    unidad=unidad,
                    ts_epoch=ts_epoch,
                    ts_iso=ts_iso,
                    fuente="sd_jsonl",
                    calidad=_calidad(valor, minimo, maximo),
                )
            )
    return lecturas


def parsear_payload_ubidots(
    payload: str | bytes | dict[str, Any],
    *,
    estacion_id: int,
    ts_epoch_defecto: int | None = None,
    fuente: str = "ubidots",
) -> list[LecturaSensor]:
    """Convierte un JSON de Ubidots (o de MQTT local con el mismo contrato) en ``LecturaSensor``.

    Acepta:
    - Formato extendido (Nodo INTI): ``{"suelo-a": {"value": 42.5, "timestamp": 1762981200000}}``
    - Formato compacto (InBeersa):   ``{"temperatura_interna": 28.4, "vpd_nido": 0.92}``
    """
    datos: dict[str, Any] = json.loads(payload) if isinstance(payload, (str, bytes)) else dict(payload)
    epoch_base = ts_epoch_defecto if ts_epoch_defecto is not None else tiempo.a_epoch(tiempo.ahora())

    lecturas: list[LecturaSensor] = []
    for clave_bruta, contenido in datos.items():
        variable = clave_bruta.strip().lower().replace("-", "_")
        if variable == "id_sesion":
            continue

        if isinstance(contenido, dict):
            if "value" not in contenido:
                continue
            valor = float(contenido["value"])
            ts_ms = contenido.get("timestamp")
            # Ubidots usa milisegundos; si es > 10^11 es ms, si no es segundos.
            ts_epoch = int(ts_ms // 1000) if ts_ms and ts_ms > 100_000_000_000 else int(ts_ms or epoch_base)
        elif isinstance(contenido, (int, float)):
            valor = float(contenido)
            ts_epoch = epoch_base
        else:
            continue

        unidad, minimo, maximo = _UNIDADES_UBIDOTS.get(variable, (None, -1e9, 1e9))
        ts_iso = tiempo.a_iso(tiempo.desde_epoch(ts_epoch))
        lecturas.append(
            LecturaSensor(
                estacion_id=estacion_id,
                variable=variable,
                valor=valor,
                unidad=unidad,
                ts_epoch=ts_epoch,
                ts_iso=ts_iso,
                fuente=fuente,
                calidad=_calidad(valor, minimo, maximo),
            )
        )
    return lecturas
