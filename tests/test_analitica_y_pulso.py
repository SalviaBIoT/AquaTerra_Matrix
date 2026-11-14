"""Pruebas de Fase B2: Motor analítico (ventana móvil, tasa de secado, correlación, viento circular) y Pulso 24h."""

from __future__ import annotations

import pytest

from aquaterra.application import NodePulseService
from aquaterra.core import tiempo
from aquaterra.core.analitica import (
    NivelSeveridadPulso,
    TendenciaVariable,
    calcular_ventana_movil_memoria,
    clasificar_tendencia,
    promedio_vectorial_grados,
    resolver_ventana_seg,
    tasa_cambio_por_hora,
    tiempo_hasta_umbral_horas,
)
from aquaterra.core.domain import EventoEstacion, LecturaSensor, TipoEstacion
from aquaterra.infrastructure.db.repositorios import (
    RepositorioEstaciones,
    RepositorioEventosEstacion,
    RepositorioLecturas,
)
from aquaterra.infrastructure.iot_ingest import (
    parsear_csv_conservacion,
    parsear_csv_nodo_inti,
    parsear_csv_sigatoka,
    parsear_jsonl_inbeersa,
)


def _lectura(estacion_id: int, variable: str, valor: float, ts_epoch: int, *, calidad: int = 0) -> LecturaSensor:
    return LecturaSensor(
        estacion_id=estacion_id,
        variable=variable,
        valor=valor,
        unidad="%",
        ts_epoch=ts_epoch,
        ts_iso=tiempo.a_iso(tiempo.desde_epoch(ts_epoch)),
        fuente="sd_csv",
        calidad=calidad,
    )


def test_ventana_movil_sqlite_coincide_con_memoria_y_filtra_calidad_2(db):
    with db:
        est = RepositorioEstaciones(db).crear("inti-vm", "Nodo Ventana Móvil", TipoEstacion.TERRABIT_INTI)

    t0 = 1_794_600_000
    puntos_validos = [
        (t0, 40.0),
        (t0 + 1800, 42.0),
        (t0 + 3600, 46.0),
        (t0 + 5400, 44.0),
    ]
    lote = [_lectura(est.id, "suelo_a", v, ts) for ts, v in puntos_validos]
    # Muestra corrupta (calidad=2) en medio de la ventana que NO debe alterar el promedio
    lote.append(_lectura(est.id, "suelo_a", 999.0, t0 + 2000, calidad=2))

    with db:
        RepositorioLecturas(db).insertar_lote(lote)

    srv = NodePulseService(db)
    en_sqlite = srv.consultar_ventana_movil(
        est.id,
        "suelo_a",
        desde_epoch=t0,
        hasta_epoch=t0 + 5400,
        ventana="1h",
    )
    en_memoria = calcular_ventana_movil_memoria(puntos_validos, ventana="1h")

    assert en_sqlite == en_memoria
    # En t0 + 5400 la ventana de 1h [t0+1800 .. t0+5400] abarca (42.0, 46.0, 44.0) -> media = 44.0
    assert en_sqlite[-1].media_movil == pytest.approx(44.0)
    assert en_sqlite[-1].min_movil == pytest.approx(42.0)
    assert en_sqlite[-1].max_movil == pytest.approx(46.0)

    with pytest.raises(ValueError, match="no reconocida"):
        resolver_ventana_seg("99x")


def test_tasa_secado_edafico_y_tiempo_hasta_estres():
    t0 = 1_794_600_000
    # Cae exactamente 0.5 % por hora: 36.0 -> 35.5 -> 35.0 -> 34.5
    serie = [(t0 + i * 3600, 36.0 - 0.5 * i) for i in range(4)]

    tasa = tasa_cambio_por_hora(serie)
    assert tasa == pytest.approx(-0.5)

    tendencia = clasificar_tendencia(tasa)
    assert tendencia is TendenciaVariable.DESCENDENTE
    assert tendencia.simbolo == "↓"

    # Desde 34.5 % bajando a -0.5 %/h hasta umbral 30.0 % -> faltan (4.5 / 0.5) = 9.0 horas
    horas_restantes = tiempo_hasta_umbral_horas(34.5, tasa, umbral_critico=30.0)
    assert horas_restantes == pytest.approx(9.0)
    assert tiempo_hasta_umbral_horas(29.0, tasa, umbral_critico=30.0) == 0.0
    assert tiempo_hasta_umbral_horas(34.5, 0.2, umbral_critico=30.0) is None


def test_correlacion_bivariada_y_promedio_vectorial_viento(db):
    assert promedio_vectorial_grados([350.0, 10.0]) == pytest.approx(0.0)
    assert promedio_vectorial_grados([45.0, 135.0]) == pytest.approx(90.0)
    assert promedio_vectorial_grados([]) is None

    with db:
        est = RepositorioEstaciones(db).crear("inti-corr", "Nodo Correlación", TipoEstacion.TERRABIT_INTI)

    t0 = 1_794_600_000
    lecturas: list[LecturaSensor] = []
    for i in range(6):
        ts = t0 + i * 600
        temp = 20.0 + 2.0 * i
        hum = 85.0 - 5.0 * i
        vpd = 0.5 + 0.25 * i
        lecturas.extend(
            [
                _lectura(est.id, "temp_aire", temp, ts),
                _lectura(est.id, "hum_aire", hum, ts),
                _lectura(est.id, "vpd", vpd, ts),
            ]
        )
    with db:
        RepositorioLecturas(db).insertar_lote(lecturas)

    srv = NodePulseService(db)
    corr_neg = srv.comparar_variables(
        est.id,
        "temp_aire",
        "hum_aire",
        desde_epoch=t0,
        hasta_epoch=t0 + 3600,
    )
    assert corr_neg.pares_alineados == 6
    assert corr_neg.pearson_r == pytest.approx(-1.0)
    assert corr_neg.interpretacion == "fuerte_negativa"

    corr_pos = srv.comparar_variables(
        est.id,
        "temp_aire",
        "vpd",
        desde_epoch=t0,
        hasta_epoch=t0 + 3600,
    )
    assert corr_pos.pearson_r == pytest.approx(1.0)
    assert corr_pos.interpretacion == "fuerte_positiva"


def test_pulso_24h_nodo_inti_detecta_secado_y_estres(db):
    with db:
        est = RepositorioEstaciones(db).crear("inti-p24", "Nodo INTI Lote Sur", TipoEstacion.TERRABIT_INTI)

    csv_inti = (
        "Uptime,HumedadA,HumedadB,TempAire,HumAire,Presion,TempRaiz,Voltaje,VPD,SessionID\n"
        "2026-11-13 06:00:00,35.0,40.0,26.0,50.0,852.0,21.0,3.95,1.68,1\n"
        "2026-11-13 07:00:00,34.0,39.8,27.5,45.0,851.8,21.2,3.92,2.02,1\n"
        "2026-11-13 08:00:00,33.0,39.5,28.5,42.0,851.5,21.5,3.90,2.26,1\n"
    )
    lecturas = parsear_csv_nodo_inti(csv_inti, estacion_id=est.id)
    with db:
        RepositorioLecturas(db).insertar_lote(lecturas)

    pulso = NodePulseService(db).obtener_pulso_24h(est.id)
    assert pulso.tipo_estacion is TipoEstacion.TERRABIT_INTI
    assert pulso.inti is not None
    # Suelo A cae 1.0 % por hora (35 -> 34 -> 33); faltan 3.0 h para tocar 30.0 %
    assert pulso.inti.tasa_secado_suelo_a_pct_h == pytest.approx(-1.0)
    assert pulso.inti.horas_hasta_estres_suelo_a == pytest.approx(3.0)
    assert pulso.inti.diferencial_horizontes_ab_pct == pytest.approx(33.0 - 39.5)
    assert pulso.inti.horas_estres_vpd > 0.0
    assert pulso.severidad is NivelSeveridadPulso.ATENCION
    assert any("Secado activo" in a for a in pulso.alertas_detectadas)


def test_pulso_24h_inbeersa_homeostasis_pir_y_audios_wav(db):
    with db:
        est = RepositorioEstaciones(db).crear("inb-p24", "Meliponario Colmena 1", TipoEstacion.INBEERSA)

    jsonl = (
        '{"fecha":"2026-11-13","hora":"10:00:00","tempInterna":30.0,"humInterna":74.0,'
        '"tempExterna":22.0,"humExterna":80.0,"pirDetectado":1,"cAire":520}\n'
        '{"fecha":"2026-11-13","hora":"10:05:00","tempInterna":30.2,"humInterna":73.5,'
        '"tempExterna":22.2,"humExterna":79.0,"pirDetectado":1,"cAire":530}\n'
    )
    lecturas = parsear_jsonl_inbeersa(jsonl, estacion_id=est.id)
    ts_ev = lecturas[0].ts_epoch
    evento_wav = EventoEstacion(
        estacion_id=est.id,
        tipo_evento="audio_wav_evento",
        ts_epoch=ts_ev,
        ts_iso=lecturas[0].ts_iso,
        archivo_ruta="/Audios_PIR/pir_0001.wav",
    )
    with db:
        RepositorioLecturas(db).insertar_lote(lecturas)
        RepositorioEventosEstacion(db).insertar_lote([evento_wav])

    pulso = NodePulseService(db).obtener_pulso_24h(est.id)
    assert pulso.inbeersa is not None
    assert pulso.inbeersa.en_rango_homeostasis is True
    assert pulso.inbeersa.delta_temp_medio_c == pytest.approx(8.0)
    assert pulso.inbeersa.conteo_audios_bioacusticos == 1
    assert pulso.severidad is NivelSeveridadPulso.OPTIMO


def test_pulso_24h_sigatoka_ventana_infeccion_y_rumbo_circular(db):
    with db:
        est = RepositorioEstaciones(db).crear("sig-p24", "Sigatoka Lote Plátano", TipoEstacion.SIGATOKA)

    csv_sig = (
        "Fecha,Hora,Lluvia_mm_min,Velocidad_ms,Direccion,"
        "Temperatura_C,Humedad_pct,Humectacion_Foliar_pct,Duracion_Humectacion_min\n"
        "2026-11-13,05:00:00,0.20,1.4,N,26.0,90.0,82.0,350\n"
        "2026-11-13,05:05:00,0.10,1.6,NE,26.5,92.0,85.0,380\n"
    )
    lecturas, eventos = parsear_csv_sigatoka(csv_sig, estacion_id=est.id)
    with db:
        RepositorioLecturas(db).insertar_lote(lecturas)
        RepositorioEventosEstacion(db).insertar_lote(eventos)

    pulso = NodePulseService(db).obtener_pulso_24h(est.id)
    assert pulso.sigatoka is not None
    assert pulso.sigatoka.alerta_infeccion_fungica is True
    assert pulso.sigatoka.duracion_humectacion_continua_min == pytest.approx(380.0)
    # Promedio vectorial entre N (0°) y NE (45°) = 22.5°
    assert pulso.sigatoka.rumbo_viento_dominante_grados == pytest.approx(22.5)
    assert pulso.sigatoka.precipitacion_acumulada_mm > 0.0
    assert pulso.severidad is NivelSeveridadPulso.CRITICO


def test_pulso_24h_conservacion_paramo_y_estacion_sin_datos(db):
    with db:
        est_vacia = RepositorioEstaciones(db).crear("par-vacia", "Páramo Vacío", TipoEstacion.CONSERVACION)
        est_paramo = RepositorioEstaciones(db).crear("par-01", "Turbera Otún", TipoEstacion.CONSERVACION)

    srv = NodePulseService(db)
    pulso_vacio = srv.obtener_pulso_24h(est_vacia.id)
    assert pulso_vacio.severidad is NivelSeveridadPulso.SIN_DATOS

    csv_con = (
        "Uptime,nivel_freatico_cm,humedad_turba_a,humedad_turba_b,"
        "radiacion_solar_wm2,temp_suelo_paramo,temp_aire,hum_aire,voltaje\n"
        "2026-11-13 09:00:00,-10.0,88.0,90.0,420.0,6.5,8.5,88.0,12.40\n"
        "2026-11-13 12:00:00,-16.0,87.0,89.0,780.0,7.2,11.0,82.0,12.85\n"
    )
    lecturas = parsear_csv_conservacion(csv_con, estacion_id=est_paramo.id)
    with db:
        RepositorioLecturas(db).insertar_lote(lecturas)

    pulso = srv.obtener_pulso_24h(est_paramo.id)
    assert pulso.conservacion is not None
    assert pulso.conservacion.variacion_nivel_freatico_cm == pytest.approx(-6.0)
    assert pulso.conservacion.humedad_turba_media_pct == pytest.approx(88.5)
    assert pulso.conservacion.irradiancia_max_wm2 == pytest.approx(780.0)
    assert pulso.conservacion.balance_bateria_v == pytest.approx(0.45)
    assert pulso.severidad is NivelSeveridadPulso.ATENCION
