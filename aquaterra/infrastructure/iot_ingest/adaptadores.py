"""Adaptadores de ingesta para las 4 familias de estaciones del Ecosistema TerraBit.

Soporta los contratos reales de los firmwares C++17 y la nube Ubidots:

1. **TerraBit Nodo INTI — MicroSD CSV (``/data.csv``)**
   Generado por ``Estacion_TerraBit_Inti/src/storage.cpp``::

       Uptime,HumedadA,HumedadB,TempAire,HumAire,Presion,TempRaiz,Voltaje,VPD,SessionID
       2026/11/12 14:05:00,42.50,39.80,24.10,68.00,852.30,21.40,4.12,0.96,1

   Admite además columnas opcionales de verificación hidromecánica de bomba/válvula
   (``VibracionRMS``, ``VibracionFreq``, ``CorrienteBomba``, ``CaudalLPM``, ``AperturaValvula``).

2. **InBeersa (Abejas Angelitas) — MicroSD / LittleFS JSONL (``/data.json``)**
   Generado por ``Estacion_InBeersa/src/comms.cpp`` y ``storage.cpp``::

       {"colmena":"Colmena_01","Fecha":"2026-11-12","Hora":"14:05:00","TempI":28.4,"HumedadI":76.2,"VPD":0.92,"PIR":1,"Lluvia":0}

3. **Sigatoka — MicroSD CSV (``/MUNDONUEVO.csv``) / Buffer Flash (``/buffer_sigatoka.json``)**
   Generado por ``Estacion_Sigatoka/lib/StorageManager/StorageManager.cpp``::

       Fecha,Hora,Lluvia_mm_min,Velocidad_ms,Direccion,Temperatura_C,Humedad_pct,Humectacion_Foliar_pct,Duracion_Humectacion_min
       2026-11-12,14:05:00,0.30,1.12,NE,26.40,88.50,78.0,45

4. **Conservación & Páramos (Polylepis / Turberas) — CSV Estándar**
   Soporta ``nivel_freatico_cm``, ``humedad_turba_a``, ``humedad_turba_b``,
   ``radiacion_solar_wm2``, ``temp_suelo_paramo`` y microclima estándar.

5. **Ubidots Industrial — Payload MQTT / REST (``/v1.6/devices/<label>``)**
   Soporta objetos con ``{"value": x, "timestamp": ms}`` y escalares directos.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from aquaterra.core import tiempo
from aquaterra.core.agronomia.psicrometria import vpd_kpa
from aquaterra.core.domain import EventoEstacion, LecturaSensor

# Guardia de sanidad temporal (Riesgo 6): todo epoch anterior a 2024-01-01T00:00:00Z
# indica pila RTC DS3231/DS1307 agotada sin sincronización NTP.
EPOCH_MINIMO_VALIDO = 1_704_067_200

_UMBRAL_HOJA_HUMECTADA_PCT = 70.0

_ROSA_VIENTOS_GRADOS: dict[str, float] = {
    "N": 0.0,
    "NE": 45.0,
    "E": 90.0,
    "SE": 135.0,
    "S": 180.0,
    "SW": 225.0,
    "W": 270.0,
    "NW": 315.0,
}

# Mapeo de columnas de /data.csv (Nodo INTI) -> (variable, unidad, min_fisico, max_fisico)
_ESQUEMA_NODO_INTI: dict[str, tuple[str, str, float, float]] = {
    "HumedadA": ("suelo_a", "%", 0.0, 100.0),
    "HumedadB": ("suelo_b", "%", 0.0, 100.0),
    "TempAire": ("temp_aire", "°C", -20.0, 65.0),
    "HumAire": ("hum_aire", "%", 0.0, 100.0),
    "Presion": ("presion", "hPa", 300.0, 1100.0),
    "TempRaiz": ("temp_raiz", "°C", -10.0, 60.0),
    "Voltaje": ("voltaje", "V", 0.0, 15.0),
    "VPD": ("vpd", "kPa", 0.0, 10.0),
    "VibracionRMS": ("vibracion_bomba_rms", "g", 0.0, 16.0),
    "VibracionFreq": ("vibracion_freq_hz", "Hz", 0.0, 500.0),
    "CorrienteBomba": ("corriente_bomba_a", "A", 0.0, 30.0),
    "CaudalLPM": ("caudal_lpm", "L/min", 0.0, 200.0),
    "AperturaValvula": ("apertura_valvula_pct", "%", 0.0, 100.0),
}

# Mapeo de claves de /data.json y struct TelemetriaInBeersa -> (variable, unidad, min_fisico, max_fisico)
_ESQUEMA_INBEERSA: dict[str, tuple[str, str, float, float]] = {
    "TempI": ("temperatura_interna", "°C", -10.0, 60.0),
    "tempInterna": ("temperatura_interna", "°C", -10.0, 60.0),
    "HumedadI": ("humedad_interna", "%", 0.0, 100.0),
    "humInterna": ("humedad_interna", "%", 0.0, 100.0),
    "VPD": ("vpd_nido", "kPa", 0.0, 10.0),
    "vpdInterno": ("vpd_nido", "kPa", 0.0, 10.0),
    "PIR": ("actividad_pir", "evento", 0.0, 1.0),
    "pirDetectado": ("actividad_pir", "evento", 0.0, 1.0),
    "eventosPIRTotal": ("eventos_pir_total", "conteo", 0.0, 1_000_000.0),
    "Lluvia": ("lluvia_evento", "evento", 0.0, 1.0),
    "llovio": ("lluvia_evento", "evento", 0.0, 1.0),
    "TempE": ("temperatura_externa", "°C", -20.0, 65.0),
    "tempExterna": ("temperatura_externa", "°C", -20.0, 65.0),
    "HumedadE": ("humedad_externa", "%", 0.0, 100.0),
    "humExterna": ("humedad_externa", "%", 0.0, 100.0),
    "deltaTemp": ("delta_temp", "°C", -30.0, 40.0),
    "MQ135": ("calidad_aire_adc", "adc", 0.0, 4095.0),
    "cAire": ("calidad_aire_adc", "adc", 0.0, 4095.0),
    "uptimeSeg": ("uptime_seg", "s", 0.0, 1_000_000_000.0),
}

_CABECERA_SIGATOKA: tuple[str, ...] = (
    "Fecha",
    "Hora",
    "Lluvia_mm_min",
    "Velocidad_ms",
    "Direccion",
    "Temperatura_C",
    "Humedad_pct",
    "Humectacion_Foliar_pct",
    "Duracion_Humectacion_min",
)

_ESQUEMA_SIGATOKA_NUMERICAS: dict[str, tuple[str, str, float, float]] = {
    "Lluvia_mm_min": ("lluvia_mm_min", "mm/min", 0.0, 50.0),
    "Velocidad_ms": ("velocidad_viento_ms", "m/s", 0.0, 60.0),
    "Temperatura_C": ("temp_aire", "°C", -20.0, 65.0),
    "Humedad_pct": ("hum_aire", "%", 0.0, 100.0),
    "Humectacion_Foliar_pct": ("foliar_humedad_pct", "%", 0.0, 100.0),
    "Duracion_Humectacion_min": ("duracion_humeda_min", "min", 0.0, 1_000_000.0),
}

_ESQUEMA_CONSERVACION: dict[str, tuple[str, str, float, float]] = {
    "nivel_freatico_cm": ("nivel_freatico_cm", "cm", -200.0, 100.0),
    "humedad_turba_a": ("humedad_turba_a", "%", 0.0, 100.0),
    "humedad_turba_b": ("humedad_turba_b", "%", 0.0, 100.0),
    "radiacion_solar_wm2": ("radiacion_solar_wm2", "W/m²", 0.0, 1500.0),
    "temp_suelo_paramo": ("temp_suelo_paramo", "°C", -15.0, 40.0),
    "temp_aire": ("temp_aire", "°C", -20.0, 65.0),
    "hum_aire": ("hum_aire", "%", 0.0, 100.0),
    "presion": ("presion", "hPa", 300.0, 1100.0),
    "vpd": ("vpd", "kPa", 0.0, 10.0),
    "voltaje": ("voltaje", "V", 0.0, 15.0),
}

# Unidades canónicas y cotas físicas para variables recibidas desde Ubidots / MQTT
_UNIDADES_UBIDOTS: dict[str, tuple[str, float, float]] = {
    "suelo_a": ("%", 0.0, 100.0),
    "suelo_b": ("%", 0.0, 100.0),
    "temp_aire": ("°C", -20.0, 65.0),
    "hum_aire": ("%", 0.0, 100.0),
    "presion": ("hPa", 300.0, 1100.0),
    "temp_raiz": ("°C", -10.0, 60.0),
    "voltaje": ("V", 0.0, 15.0),
    "vpd": ("kPa", 0.0, 10.0),
    "vibracion_bomba_rms": ("g", 0.0, 16.0),
    "vibracion_freq_hz": ("Hz", 0.0, 500.0),
    "corriente_bomba_a": ("A", 0.0, 30.0),
    "caudal_lpm": ("L/min", 0.0, 200.0),
    "apertura_valvula_pct": ("%", 0.0, 100.0),
    "temperatura_interna": ("°C", -10.0, 60.0),
    "humedad_interna": ("%", 0.0, 100.0),
    "temperatura_externa": ("°C", -20.0, 65.0),
    "humedad_externa": ("%", 0.0, 100.0),
    "delta_temp": ("°C", -30.0, 40.0),
    "vpd_nido": ("kPa", 0.0, 10.0),
    "calidad_aire_adc": ("adc", 0.0, 4095.0),
    "actividad_pir": ("evento", 0.0, 1.0),
    "eventos_pir_total": ("conteo", 0.0, 1_000_000.0),
    "lluvia_evento": ("evento", 0.0, 1.0),
    "lluvia_mm_min": ("mm/min", 0.0, 50.0),
    "velocidad_viento_ms": ("m/s", 0.0, 60.0),
    "direccion_viento_grados": ("°", 0.0, 360.0),
    "foliar_humedad_pct": ("%", 0.0, 100.0),
    "hoja_humectada": ("estado", 0.0, 1.0),
    "duracion_humeda_min": ("min", 0.0, 1_000_000.0),
    "nivel_freatico_cm": ("cm", -200.0, 100.0),
    "humedad_turba_a": ("%", 0.0, 100.0),
    "humedad_turba_b": ("%", 0.0, 100.0),
    "radiacion_solar_wm2": ("W/m²", 0.0, 1500.0),
    "temp_suelo_paramo": ("°C", -15.0, 40.0),
}


def _leer_texto(contenido_o_ruta: str | Path) -> str:
    return contenido_o_ruta.read_text(encoding="utf-8") if isinstance(contenido_o_ruta, Path) else contenido_o_ruta


def _calidad_con_tiempo(valor: float, minimo: float, maximo: float, ts_epoch: int) -> int:
    """0 = válido, 2 = fuera de rango físico o timestamp RTC anterior a 2024-01-01."""
    if ts_epoch < EPOCH_MINIMO_VALIDO:
        return 2
    return 0 if (minimo <= valor <= maximo) else 2


def _parsear_fecha_hora_estacion(texto_fecha_hora: str) -> datetime:
    """Acepta ``YYYY/MM/DD HH:MM:SS``, ``YYYY-MM-DD HH:MM:SS`` o ``DD/MM/YYYY HH:MM:SS``."""
    limpio = " ".join(texto_fecha_hora.strip().split())
    fecha_parte, hora_parte = limpio.split(" ", 1)
    fecha_norm = fecha_parte.replace("/", "-")
    primer_bloque = fecha_norm.split("-", 1)[0]
    if len(primer_bloque) == 4:
        momento = datetime.strptime(f"{fecha_norm} {hora_parte}", "%Y-%m-%d %H:%M:%S")
    else:
        momento = datetime.strptime(f"{fecha_norm} {hora_parte}", "%d-%m-%Y %H:%M:%S")
    return momento.replace(tzinfo=tiempo.ZONA_COLOMBIA)


def _vpd_si_valido(temp_c: float | None, hum_pct: float | None) -> float | None:
    if temp_c is None or hum_pct is None:
        return None
    if not (-20.0 <= temp_c <= 65.0 and 0.0 <= hum_pct <= 100.0):
        return None
    return vpd_kpa(temp_c, hum_pct)


def parsear_csv_nodo_inti(
    contenido_o_ruta: str | Path,
    *,
    estacion_id: int,
) -> list[LecturaSensor]:
    """Convierte el ``/data.csv`` de una estación TerraBit Nodo INTI en ``LecturaSensor``."""
    texto = _leer_texto(contenido_o_ruta)

    lecturas: list[LecturaSensor] = []
    lector = csv.DictReader(io.StringIO(texto.strip()))
    for fila in lector:
        uptime = (fila.get("Uptime") or "").strip()
        if not uptime or uptime == "RTC_OFF":
            continue
        momento = _parsear_fecha_hora_estacion(uptime)
        ts_epoch = tiempo.a_epoch(momento)
        ts_iso = tiempo.a_iso(momento)

        valores_fila: dict[str, float] = {}
        for columna, (variable, unidad, minimo, maximo) in _ESQUEMA_NODO_INTI.items():
            bruto = fila.get(columna)
            if bruto is None or str(bruto).strip() == "":
                continue
            valor = float(bruto)
            valores_fila[variable] = valor
            lecturas.append(
                LecturaSensor(
                    estacion_id=estacion_id,
                    variable=variable,
                    valor=valor,
                    unidad=unidad,
                    ts_epoch=ts_epoch,
                    ts_iso=ts_iso,
                    fuente="sd_csv",
                    calidad=_calidad_con_tiempo(valor, minimo, maximo, ts_epoch),
                )
            )

        if "vpd" not in valores_fila:
            vpd_calc = _vpd_si_valido(valores_fila.get("temp_aire"), valores_fila.get("hum_aire"))
            if vpd_calc is not None:
                lecturas.append(
                    LecturaSensor(
                        estacion_id=estacion_id,
                        variable="vpd",
                        valor=vpd_calc,
                        unidad="kPa",
                        ts_epoch=ts_epoch,
                        ts_iso=ts_iso,
                        fuente="sd_csv",
                        calidad=_calidad_con_tiempo(vpd_calc, 0.0, 10.0, ts_epoch),
                    )
                )
    return lecturas


def parsear_jsonl_inbeersa(
    contenido_o_ruta: str | Path,
    *,
    estacion_id: int,
) -> list[LecturaSensor]:
    """Convierte el ``/data.json`` (JSON Lines) de InBeersa en ``LecturaSensor``."""
    texto = _leer_texto(contenido_o_ruta)

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

        valores_fila: dict[str, float] = {}
        for clave, (variable, unidad, minimo, maximo) in _ESQUEMA_INBEERSA.items():
            if clave not in objeto or objeto[clave] is None or variable in valores_fila:
                continue
            valor = float(objeto[clave])
            valores_fila[variable] = valor
            lecturas.append(
                LecturaSensor(
                    estacion_id=estacion_id,
                    variable=variable,
                    valor=valor,
                    unidad=unidad,
                    ts_epoch=ts_epoch,
                    ts_iso=ts_iso,
                    fuente="sd_jsonl",
                    calidad=_calidad_con_tiempo(valor, minimo, maximo, ts_epoch),
                )
            )

        if "delta_temp" not in valores_fila:
            temp_i = valores_fila.get("temperatura_interna")
            temp_e = valores_fila.get("temperatura_externa")
            if temp_i is not None and temp_e is not None and -10.0 <= temp_i <= 60.0 and -20.0 <= temp_e <= 65.0:
                delta_t = round(temp_i - temp_e, 2)
                lecturas.append(
                    LecturaSensor(
                        estacion_id=estacion_id,
                        variable="delta_temp",
                        valor=delta_t,
                        unidad="°C",
                        ts_epoch=ts_epoch,
                        ts_iso=ts_iso,
                        fuente="sd_jsonl",
                        calidad=_calidad_con_tiempo(delta_t, -30.0, 40.0, ts_epoch),
                    )
                )
    return lecturas


def parsear_csv_sigatoka(
    contenido_o_ruta: str | Path,
    *,
    estacion_id: int,
) -> tuple[list[LecturaSensor], list[EventoEstacion]]:
    """Convierte ``/MUNDONUEVO.csv`` (con cabecera) o ``/buffer_sigatoka.json`` (sin cabecera).

    Devuelve una tupla ``(lecturas_numericas, eventos_estacion)`` donde los eventos
    registran la etiqueta cardinal de dirección del viento (``N``, ``NE``, ...).
    """
    texto = _leer_texto(contenido_o_ruta)
    lineas = [ln.strip() for ln in texto.splitlines() if ln.strip()]
    if not lineas:
        return [], []

    tiene_cabecera = lineas[0].lower().startswith("fecha,")
    cuerpo = "\n".join(lineas)
    if tiene_cabecera:
        lector = csv.DictReader(io.StringIO(cuerpo))
    else:
        lector = csv.DictReader(io.StringIO(cuerpo), fieldnames=_CABECERA_SIGATOKA)

    lecturas: list[LecturaSensor] = []
    eventos: list[EventoEstacion] = []
    for fila in lector:
        fecha = (fila.get("Fecha") or "").strip()
        hora = (fila.get("Hora") or "").strip()
        if not fecha or not hora or "RTC_OFF" in fecha:
            continue
        momento = _parsear_fecha_hora_estacion(f"{fecha} {hora}")
        ts_epoch = tiempo.a_epoch(momento)
        ts_iso = tiempo.a_iso(momento)

        valores_fila: dict[str, float] = {}
        for columna, (variable, unidad, minimo, maximo) in _ESQUEMA_SIGATOKA_NUMERICAS.items():
            bruto = fila.get(columna)
            if bruto is None or str(bruto).strip() == "":
                continue
            valor = float(bruto)
            valores_fila[variable] = valor
            lecturas.append(
                LecturaSensor(
                    estacion_id=estacion_id,
                    variable=variable,
                    valor=valor,
                    unidad=unidad,
                    ts_epoch=ts_epoch,
                    ts_iso=ts_iso,
                    fuente="sd_csv",
                    calidad=_calidad_con_tiempo(valor, minimo, maximo, ts_epoch),
                )
            )

        if "foliar_humedad_pct" in valores_fila:
            hoja_mojada = 1.0 if valores_fila["foliar_humedad_pct"] >= _UMBRAL_HOJA_HUMECTADA_PCT else 0.0
            lecturas.append(
                LecturaSensor(
                    estacion_id=estacion_id,
                    variable="hoja_humectada",
                    valor=hoja_mojada,
                    unidad="estado",
                    ts_epoch=ts_epoch,
                    ts_iso=ts_iso,
                    fuente="sd_csv",
                    calidad=_calidad_con_tiempo(hoja_mojada, 0.0, 1.0, ts_epoch),
                )
            )

        direccion = (fila.get("Direccion") or "").strip().upper()
        if direccion in _ROSA_VIENTOS_GRADOS:
            grados = _ROSA_VIENTOS_GRADOS[direccion]
            lecturas.append(
                LecturaSensor(
                    estacion_id=estacion_id,
                    variable="direccion_viento_grados",
                    valor=grados,
                    unidad="°",
                    ts_epoch=ts_epoch,
                    ts_iso=ts_iso,
                    fuente="sd_csv",
                    calidad=_calidad_con_tiempo(grados, 0.0, 360.0, ts_epoch),
                )
            )
            eventos.append(
                EventoEstacion(
                    estacion_id=estacion_id,
                    tipo_evento="direccion_viento",
                    ts_epoch=ts_epoch,
                    ts_iso=ts_iso,
                    valor_texto=direccion,
                )
            )

        vpd_calc = _vpd_si_valido(valores_fila.get("temp_aire"), valores_fila.get("hum_aire"))
        if vpd_calc is not None:
            lecturas.append(
                LecturaSensor(
                    estacion_id=estacion_id,
                    variable="vpd",
                    valor=vpd_calc,
                    unidad="kPa",
                    ts_epoch=ts_epoch,
                    ts_iso=ts_iso,
                    fuente="sd_csv",
                    calidad=_calidad_con_tiempo(vpd_calc, 0.0, 10.0, ts_epoch),
                )
            )

    return lecturas, eventos


def parsear_csv_conservacion(
    contenido_o_ruta: str | Path,
    *,
    estacion_id: int,
) -> list[LecturaSensor]:
    """Convierte registros CSV de estaciones de páramo y turberas (*Polylepis*)."""
    texto = _leer_texto(contenido_o_ruta).strip()
    if not texto:
        return []

    lecturas: list[LecturaSensor] = []
    lector = csv.DictReader(io.StringIO(texto))
    for fila in lector:
        uptime = (fila.get("Uptime") or fila.get("uptime") or "").strip()
        if uptime and uptime != "RTC_OFF":
            marca_tiempo = uptime
        else:
            fecha = (fila.get("Fecha") or fila.get("fecha") or "").strip()
            hora = (fila.get("Hora") or fila.get("hora") or "").strip()
            if not fecha or not hora or "RTC_OFF" in fecha:
                continue
            marca_tiempo = f"{fecha} {hora}"

        momento = _parsear_fecha_hora_estacion(marca_tiempo)
        ts_epoch = tiempo.a_epoch(momento)
        ts_iso = tiempo.a_iso(momento)

        valores_fila: dict[str, float] = {}
        for columna, (variable, unidad, minimo, maximo) in _ESQUEMA_CONSERVACION.items():
            bruto = fila.get(columna)
            if bruto is None or str(bruto).strip() == "":
                continue
            valor = float(bruto)
            valores_fila[variable] = valor
            lecturas.append(
                LecturaSensor(
                    estacion_id=estacion_id,
                    variable=variable,
                    valor=valor,
                    unidad=unidad,
                    ts_epoch=ts_epoch,
                    ts_iso=ts_iso,
                    fuente="sd_csv",
                    calidad=_calidad_con_tiempo(valor, minimo, maximo, ts_epoch),
                )
            )

        if "vpd" not in valores_fila:
            vpd_calc = _vpd_si_valido(valores_fila.get("temp_aire"), valores_fila.get("hum_aire"))
            if vpd_calc is not None:
                lecturas.append(
                    LecturaSensor(
                        estacion_id=estacion_id,
                        variable="vpd",
                        valor=vpd_calc,
                        unidad="kPa",
                        ts_epoch=ts_epoch,
                        ts_iso=ts_iso,
                        fuente="sd_csv",
                        calidad=_calidad_con_tiempo(vpd_calc, 0.0, 10.0, ts_epoch),
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
                calidad=_calidad_con_tiempo(valor, minimo, maximo, ts_epoch),
            )
        )
    return lecturas
