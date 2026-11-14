"""Pruebas de ingesta IoT para las 4 familias de estaciones (Nodo INTI, InBeersa, Sigatoka, Conservación) y Ubidots."""

import pytest

from aquaterra.core.domain import TipoEstacion
from aquaterra.infrastructure.db.repositorios import (
    RepositorioEstaciones,
    RepositorioEventosEstacion,
    RepositorioLecturas,
)
from aquaterra.infrastructure.iot_ingest import (
    EPOCH_MINIMO_VALIDO,
    parsear_csv_conservacion,
    parsear_csv_nodo_inti,
    parsear_csv_sigatoka,
    parsear_jsonl_inbeersa,
    parsear_payload_ubidots,
)

CSV_INTI = """Uptime,HumedadA,HumedadB,TempAire,HumAire,Presion,TempRaiz,Voltaje,VPD,SessionID
2026/11/12 14:05:00,42.50,39.80,24.10,68.00,852.30,21.40,4.12,0.96,1
2026/11/12 14:10:00,42.10,39.60,24.50,66.50,852.10,21.50,4.11,1.03,1
RTC_OFF,0,0,0,0,0,0,0,0,1
"""

CSV_INTI_CON_ACTUADORES_Y_SIN_VPD = (
    "Uptime,HumedadA,HumedadB,TempAire,HumAire,"
    "VibracionRMS,VibracionFreq,CorrienteBomba,CaudalLPM,AperturaValvula\n"
    "2026-11-13 08:00:00,45.0,40.0,25.0,60.0,0.22,60.0,3.1,11.4,75.0\n"
)

JSONL_INBEERSA = (
    '{"colmena":"Colmena_01","Fecha":"2026-11-12","Hora":"14:05:00",'
    '"TempI":28.4,"HumedadI":76.2,"VPD":0.92,"PIR":1,"Lluvia":0}\n'
    '{"colmena":"Colmena_01","Fecha":"2026-11-12","Hora":"14:10:00",'
    '"TempI":-200.0,"HumedadI":75.0,"VPD":0.90,"PIR":0,"Lluvia":0}\n'
)

JSONL_INBEERSA_STRUCT_FIRMWARE = (
    '{"fecha":"2026-11-13","hora":"09:15:00","tempInterna":31.2,"humInterna":72.0,'
    '"tempExterna":23.7,"humExterna":80.0,"pirDetectado":1,"eventosPIRTotal":14,'
    '"llovio":0,"cAire":640,"uptimeSeg":3600}\n'
)

CSV_SIGATOKA_CON_CABECERA = (
    "Fecha,Hora,Lluvia_mm_min,Velocidad_ms,Direccion,"
    "Temperatura_C,Humedad_pct,Humectacion_Foliar_pct,Duracion_Humectacion_min\n"
    "2026-11-12,14:05:00,0.30,1.12,NE,26.40,88.50,78.0,45\n"
)

BUFFER_SIGATOKA_SIN_CABECERA = """2026-11-12,14:10:00,0.00,0.85,SW,25.80,82.00,62.0,0
"""

CSV_CONSERVACION_PARAMO = (
    "Uptime,nivel_freatico_cm,humedad_turba_a,humedad_turba_b,"
    "radiacion_solar_wm2,temp_suelo_paramo,temp_aire,hum_aire\n"
    "2026-11-13 11:00:00,-12.5,89.4,92.1,640.0,6.8,9.2,86.0\n"
)

CSV_RTC_NO_INICIALIZADO = """Uptime,HumedadA,TempAire,HumAire
2000/01/01 00:05:00,50.0,22.0,70.0
2026/11/13 10:00:00,51.0,22.5,69.0
"""

PAYLOAD_UBIDOTS_INTI = (
    '{"suelo-a":{"value":42.50,"timestamp":1794510300000},'
    '"vpd":{"value":0.96,"timestamp":1794510300000},'
    '"id-sesion":{"value":1,"timestamp":1794510300000}}'
)


def test_ingesta_csv_nodo_inti_y_deduplicacion_con_ubidots(db):
    with db:
        est = RepositorioEstaciones(db).crear("inti-01", "TerraBit Nodo INTI #1", TipoEstacion.TERRABIT_INTI)

    lecturas_sd = parsear_csv_nodo_inti(CSV_INTI, estacion_id=est.id)
    # 2 filas válidas × 8 variables físicas = 16 lecturas (la fila RTC_OFF se ignora)
    assert len(lecturas_sd) == 16

    repo = RepositorioLecturas(db)
    with db:
        insertadas = repo.insertar_lote(lecturas_sd)
    assert insertadas == 16

    # Ahora llega el MISMO instante (2026-11-12 14:05:00-05:00 -> epoch 1794510300) desde Ubidots:
    lecturas_ubi = parsear_payload_ubidots(PAYLOAD_UBIDOTS_INTI, estacion_id=est.id)
    assert len(lecturas_ubi) == 2
    with db:
        nuevas = repo.insertar_lote(lecturas_ubi)
    assert nuevas == 0  # Deduplicadas por UNIQUE(estacion_id, variable, ts_epoch)


def test_ingesta_jsonl_inbeersa_filtra_anomalia_dht_menos_200(db):
    with db:
        est = RepositorioEstaciones(db).crear("inbeersa-01", "InBeersa Meliponario", TipoEstacion.INBEERSA)

    lecturas = parsear_jsonl_inbeersa(JSONL_INBEERSA, estacion_id=est.id)
    repo = RepositorioLecturas(db)
    with db:
        repo.insertar_lote(lecturas)

    # La lectura de -200.0 °C quedó marcada con calidad=2, por lo que serie() la excluye:
    serie_temp = repo.serie(est.id, "temperatura_interna")
    assert len(serie_temp) == 1
    assert serie_temp[0][1] == 28.4


def test_ingesta_sigatoka_con_y_sin_cabecera_y_eventos_viento(db):
    with db:
        est = RepositorioEstaciones(db).crear("sig-01", "Estación Mundo Nuevo", TipoEstacion.SIGATOKA)

    lect_csv, ev_csv = parsear_csv_sigatoka(CSV_SIGATOKA_CON_CABECERA, estacion_id=est.id)
    lect_buf, ev_buf = parsear_csv_sigatoka(BUFFER_SIGATOKA_SIN_CABECERA, estacion_id=est.id)

    mapa_csv = {lec.variable: lec.valor for lec in lect_csv}
    mapa_buf = {lec.variable: lec.valor for lec in lect_buf}

    assert mapa_csv["foliar_humedad_pct"] == pytest.approx(78.0)
    assert mapa_csv["hoja_humectada"] == 1.0  # >= 70 %
    assert mapa_csv["direccion_viento_grados"] == 45.0  # NE
    assert "vpd" in mapa_csv

    assert mapa_buf["hoja_humectada"] == 0.0  # 62 % < 70 %
    assert mapa_buf["direccion_viento_grados"] == 225.0  # SW

    repo_lec = RepositorioLecturas(db)
    repo_ev = RepositorioEventosEstacion(db)
    with db:
        repo_lec.insertar_lote([*lect_csv, *lect_buf])
        insertados = repo_ev.insertar_lote([*ev_csv, *ev_buf])

    assert insertados == 2
    eventos = repo_ev.listar(est.id, tipo_evento="direccion_viento")
    assert [e.valor_texto for e in eventos] == ["NE", "SW"]


def test_guardia_temporal_marca_rtc_sin_sincronizar_como_calidad_2(db):
    with db:
        est = RepositorioEstaciones(db).crear("inti-rtc", "Nodo INTI RTC", TipoEstacion.TERRABIT_INTI)

    lecturas = parsear_csv_nodo_inti(CSV_RTC_NO_INICIALIZADO, estacion_id=est.id)
    anteriores = [lec for lec in lecturas if lec.ts_epoch < EPOCH_MINIMO_VALIDO]
    validas = [lec for lec in lecturas if lec.ts_epoch >= EPOCH_MINIMO_VALIDO]

    assert len(anteriores) > 0
    assert all(lec.calidad == 2 for lec in anteriores)
    assert all(lec.calidad == 0 for lec in validas)

    repo = RepositorioLecturas(db)
    with db:
        repo.insertar_lote(lecturas)

    # serie() solo devuelve calidad = 0, filtrando automáticamente lecturas de año 2000
    assert len(repo.serie(est.id, "suelo_a")) == 1
    assert repo.serie(est.id, "suelo_a")[0][1] == pytest.approx(51.0)


def test_inbeersa_struct_calcula_delta_temp_automatico(db):
    with db:
        est = RepositorioEstaciones(db).crear("inbeersa-02", "InBeersa Struct", TipoEstacion.INBEERSA)

    lecturas = parsear_jsonl_inbeersa(JSONL_INBEERSA_STRUCT_FIRMWARE, estacion_id=est.id)
    mapa = {lec.variable: lec.valor for lec in lecturas}

    assert mapa["temperatura_interna"] == pytest.approx(31.2)
    assert mapa["temperatura_externa"] == pytest.approx(23.7)
    assert mapa["delta_temp"] == pytest.approx(7.5)
    assert mapa["calidad_aire_adc"] == pytest.approx(640.0)


def test_nodo_inti_con_actuadores_y_calculo_automatico_vpd(db):
    with db:
        est = RepositorioEstaciones(db).crear("inti-act", "Nodo INTI Bomba", TipoEstacion.TERRABIT_INTI)

    lecturas = parsear_csv_nodo_inti(CSV_INTI_CON_ACTUADORES_Y_SIN_VPD, estacion_id=est.id)
    mapa = {lec.variable: lec.valor for lec in lecturas}

    assert mapa["vibracion_bomba_rms"] == pytest.approx(0.22)
    assert mapa["vibracion_freq_hz"] == pytest.approx(60.0)
    assert mapa["corriente_bomba_a"] == pytest.approx(3.1)
    assert mapa["caudal_lpm"] == pytest.approx(11.4)
    assert mapa["apertura_valvula_pct"] == pytest.approx(75.0)
    # Temp=25 °C (es ≈ 3.167 kPa), Hum=60 % -> VPD ≈ 1.267 kPa
    assert 1.2 <= mapa["vpd"] <= 1.35


def test_ingesta_conservacion_paramo_y_calculo_vpd(db):
    with db:
        est = RepositorioEstaciones(db).crear("paramo-01", "Turbera Polylepis", TipoEstacion.CONSERVACION)

    lecturas = parsear_csv_conservacion(CSV_CONSERVACION_PARAMO, estacion_id=est.id)
    mapa = {lec.variable: lec.valor for lec in lecturas}

    assert mapa["nivel_freatico_cm"] == pytest.approx(-12.5)
    assert mapa["humedad_turba_a"] == pytest.approx(89.4)
    assert mapa["humedad_turba_b"] == pytest.approx(92.1)
    assert mapa["radiacion_solar_wm2"] == pytest.approx(640.0)
    assert mapa["temp_suelo_paramo"] == pytest.approx(6.8)
    assert mapa["vpd"] > 0.0

