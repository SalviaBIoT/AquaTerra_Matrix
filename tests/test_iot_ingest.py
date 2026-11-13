"""Pruebas de ingesta IoT para estaciones reales: Nodo INTI, InBeersa y Ubidots."""

from aquaterra.core.domain import TipoEstacion
from aquaterra.infrastructure.db.repositorios import RepositorioEstaciones, RepositorioLecturas
from aquaterra.infrastructure.iot_ingest import (
    parsear_csv_nodo_inti,
    parsear_jsonl_inbeersa,
    parsear_payload_ubidots,
)

CSV_INTI = """Uptime,HumedadA,HumedadB,TempAire,HumAire,Presion,TempRaiz,Voltaje,VPD,SessionID
2026/11/12 14:05:00,42.50,39.80,24.10,68.00,852.30,21.40,4.12,0.96,1
2026/11/12 14:10:00,42.10,39.60,24.50,66.50,852.10,21.50,4.11,1.03,1
RTC_OFF,0,0,0,0,0,0,0,0,1
"""

JSONL_INBEERSA = """
{"colmena":"Colmena_01","Fecha":"2026-11-12","Hora":"14:05:00","TempI":28.4,"HumedadI":76.2,"VPD":0.92,"PIR":1,"Lluvia":0}
{"colmena":"Colmena_01","Fecha":"2026-11-12","Hora":"14:10:00","TempI":-200.0,"HumedadI":75.0,"VPD":0.90,"PIR":0,"Lluvia":0}
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
