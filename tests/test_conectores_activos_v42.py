"""Pruebas del Sprint v4.2: Conectores Ubidots, Open-Meteo, Gateway nRF24L01+, Búsqueda y Notificaciones."""

from __future__ import annotations

from pathlib import Path

import pytest

from aquaterra.application.contenedor import construir_contenedor
from aquaterra.config import Configuracion
from aquaterra.core.domain import DatosParcela, EventoEstacion, TipoSuelo
from aquaterra.infrastructure.clima import (
    LATITUD_UTP_PEREIRA,
    LONGITUD_UTP_PEREIRA,
    parsear_respuesta_open_meteo,
)
from aquaterra.infrastructure.db.repositorios import (
    RepositorioEventosEstacion,
    RepositorioLecturas,
    RepositorioParcelas,
    RepositorioPronosticoClima,
)
from aquaterra.infrastructure.ia import ConfiguracionIA
from aquaterra.infrastructure.iot_ingest.serial_gateway import decodificar_linea_gateway


def test_decodificar_tramas_gateway_nrf24_y_terrabit_v1() -> None:
    # 1. Trama compacta Pipe/Key-Value de un receptor nRF24L01+ PA+LNA (sin JSON en el receptor)
    trama_kv = decodificar_linea_gateway(
        "NRF24|inbeersa-nodo01|temperatura_interna=23.4,humedad_interna=85.4,temperatura_externa=19.4,actividad_pir=0|1763090000"
    )
    assert trama_kv is not None
    assert trama_kv.device_label == "inbeersa-nodo01"
    assert trama_kv.protocolo == "nrf24_kv"
    assert trama_kv.ts_epoch == 1_763_090_000
    assert trama_kv.metricas["delta_temp"] == pytest.approx(4.0)
    assert "vpd_nido" in trama_kv.metricas

    # 2. Trama TerraBit Frame v1 (JSONL)
    trama_v1 = decodificar_linea_gateway(
        '{"v":1,"id":"terrabit-nodointi","ts":1763090100,"bat":4.08,"m":{"suelo-a":77.29,"temp-aire":18.94,"hum-aire":94.94}}'
    )
    assert trama_v1 is not None
    assert trama_v1.device_label == "terrabit-nodointi"
    assert trama_v1.protocolo == "terrabit_v1"
    assert trama_v1.metricas["suelo_a"] == pytest.approx(77.29)
    assert trama_v1.metricas["voltaje"] == pytest.approx(4.08)
    assert "vpd" in trama_v1.metricas


def test_parsear_respuesta_open_meteo_utp_pereira() -> None:
    payload_simulado = {
        "latitude": LATITUD_UTP_PEREIRA,
        "longitude": LONGITUD_UTP_PEREIRA,
        "hourly": {
            "time": ["2026-11-14T00:00", "2026-11-14T01:00"],
            "temperature_2m": [18.5, 18.1],
            "relative_humidity_2m": [88.0, 90.0],
            "precipitation_probability": [45.0, 60.0],
            "precipitation": [0.4, 1.2],
            "wind_speed_10m": [1.8, 2.1],
            "et0_fao_evapotranspiration": [0.05, 0.04],
        },
    }
    puntos = parsear_respuesta_open_meteo(payload_simulado, estacion_id=1)
    assert len(puntos) == 2
    assert puntos[0].temp_c == pytest.approx(18.5)
    assert puntos[1].lluvia_mm == pytest.approx(1.2)
    assert puntos[1].lluvia_prob_pct == pytest.approx(60.0)


def test_ingesta_gateway_nrf24_sincroniza_parcela_y_busqueda_inteligente(tmp_path: Path) -> None:
    cfg = Configuracion(ruta_db=tmp_path / "v42_gateway.db")
    cont = construir_contenedor(cfg, sembrar_legacy=False)
    try:
        cont.copiloto.orquestador.config = ConfiguracionIA(proveedor_preferido="local_reglas")
        estaciones = cont.sincronizacion.asegurar_estaciones_terrabit_base()
        assert len(estaciones) == 2
        est_inti = next(e for e in estaciones if e.codigo == "terrabit-nodointi")

        with cont.conexion:
            parcela = RepositorioParcelas(cont.conexion).crear(
                DatosParcela(
                    nombre="Parcela Piloto UTP",
                    cultivo="Tomate",
                    area_m2=100.0,
                    humedad_pct=40.0,
                    tipo_suelo=TipoSuelo.FRANCO,
                    riego_auto=True,
                    estacion_id=est_inti.id,
                )
            )
            RepositorioEventosEstacion(cont.conexion).insertar_lote(
                [
                    EventoEstacion(
                        estacion_id=est_inti.id,
                        tipo_evento="mantenimiento_sensor",
                        ts_epoch=1_763_090_000,
                        ts_iso="2026-11-13T22:00:00-05:00",
                        valor_texto="Limpieza de pluviómetro y verificación nRF24L01+",
                    )
                ]
            )

        # Ingerimos 2 tramas por radio nRF24L01+ (incluyendo voltaje centinela -1 de Ubidots/NodoINTI)
        lineas = [
            "NRF24|terrabit-nodointi|suelo-a=77.29,suelo-b=97.09,temp-aire=18.94,hum-aire=94.94,temp-raiz=21.56,presion=857.39,voltaje=-1|1763090200",
            "NRF24|inbeersa-nodo01|temperatura_interna=23.4,humedad_interna=85.4,vpd_nido=0.42,actividad_pir=0,lluvia_evento=0|1763090200",
        ]
        res_lote = cont.sincronizacion.ingerir_lote_lineas_gateway(lineas)
        assert len(res_lote) == 2

        # La parcela vinculada a terrabit-nodointi debe haberse actualizado a 77.3%
        parcela_act = cont.parcelas.obtener(parcela.id)
        assert parcela_act.humedad_pct == pytest.approx(77.3)

        # Y el voltaje centinela -1 debe haber quedado con calidad=2 (no aparece en serie válida)
        repo_lec = RepositorioLecturas(cont.conexion)
        assert repo_lec.serie(est_inti.id, "voltaje") == []
        assert len(repo_lec.serie(est_inti.id, "suelo_a")) == 1

        # Narrador ejecutivo 24h listo para WhatsApp / Telegram / n8n
        mensaje_wa, prov = cont.copiloto.narrar_pulso_24h(
            est_inti.id, hasta_epoch=1_763_090_300
        )
        assert "TerraBit-NodoINTI" in mensaje_wa
        assert prov == "local_reglas"

        # Barra de búsqueda inteligente transversal
        busq_nrf = cont.copiloto.buscar_inteligente_bitacora("nrf24l01")
        assert busq_nrf.total_hallazgos >= 1
        assert busq_nrf.items[0].categoria == "evento_estacion"

        busq_inti = cont.copiloto.buscar_inteligente_bitacora("nodointi")
        assert any(i.categoria == "estacion" for i in busq_inti.items)
    finally:
        cont.cerrar()


def test_sincronizacion_ubidots_incremental_y_clima_con_clientes_simulados(
    tmp_path: Path,
) -> None:
    cfg = Configuracion(ruta_db=tmp_path / "v42_sync_mock.db")
    cont = construir_contenedor(cfg, sembrar_legacy=False)
    try:
        estaciones = cont.sincronizacion.asegurar_estaciones_terrabit_base()
        est_inb = next(e for e in estaciones if e.codigo == "inbeersa-nodo01")

        class ClienteUbidotsFake:
            tiene_token = True

            def descargar_lecturas_estacion(
                self, estacion, *, desde_epoch=None, page_size=100, variables_override=None
            ):
                from aquaterra.infrastructure.iot_ingest.adaptadores import parsear_payload_ubidots

                lecturas = parsear_payload_ubidots(
                    {
                        "temperatura_interna": {"value": 23.4, "timestamp": 1_763_090_000_000},
                        "humedad_interna": {"value": 85.4, "timestamp": 1_763_090_000_000},
                        "vpd_nido": {"value": 0.42, "timestamp": 1_763_090_000_000},
                    },
                    estacion_id=estacion.id,
                )
                return lecturas, ()

        class ClienteClimaFake:
            def descargar_pronostico_estacion(self, estacion, *, dias=3):
                puntos = parsear_respuesta_open_meteo(
                    {
                        "hourly": {
                            "time": ["2026-11-14T06:00", "2026-11-14T07:00"],
                            "temperature_2m": [19.2, 20.5],
                            "relative_humidity_2m": [84.0, 79.0],
                            "precipitation_probability": [20.0, 35.0],
                            "precipitation": [0.0, 0.2],
                            "wind_speed_10m": [1.2, 1.5],
                            "et0_fao_evapotranspiration": [0.12, 0.21],
                        }
                    },
                    estacion_id=estacion.id,
                )
                return LATITUD_UTP_PEREIRA, LONGITUD_UTP_PEREIRA, puntos

        cont.sincronizacion.ubidots = ClienteUbidotsFake()  # type: ignore[assignment]
        cont.sincronizacion.clima = ClienteClimaFake()  # type: ignore[assignment]

        res_ubi = cont.sincronizacion.sincronizar_ubidots_estacion(est_inb.id)
        assert res_ubi.lecturas_nuevas_insertadas == 3
        assert res_ubi.desde_epoch is None

        # En la segunda corrida la marca de agua `desde_epoch` ya es 1_763_090_000 y no duplica filas
        res_ubi_2 = cont.sincronizacion.sincronizar_ubidots_estacion(est_inb.id)
        assert res_ubi_2.desde_epoch == 1_763_090_000
        assert res_ubi_2.lecturas_nuevas_insertadas == 0

        res_clima = cont.sincronizacion.sincronizar_clima_estacion(est_inb.id)
        assert res_clima.puntos_guardados == 2
        ventana_clima = RepositorioPronosticoClima(cont.conexion).ventana(
            est_inb.id, desde_epoch=0, hasta_epoch=2_000_000_000
        )
        assert len(ventana_clima) == 2
    finally:
        cont.cerrar()
