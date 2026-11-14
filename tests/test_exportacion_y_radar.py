"""Pruebas de Fase B4: Radar de estaciones priorizado por criticidad, detector MicroSD y exportador .xlsx/.csv."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from aquaterra.application import (
    AnalyticsAndExportService,
    DecisionAndControlService,
    ServicioParcelas,
    ServicioRiego,
    StationDiscoveryService,
)
from aquaterra.core.analitica import NivelSeveridadPulso
from aquaterra.core.domain import EventoEstacion, TipoEstacion
from aquaterra.infrastructure.db.repositorios import (
    RepositorioEstaciones,
    RepositorioEventosEstacion,
    RepositorioLecturas,
)
from aquaterra.infrastructure.exportacion import HojaCalculo, escribir_libro_xlsx, leer_hojas_xlsx
from aquaterra.infrastructure.iot_ingest import parsear_csv_nodo_inti, parsear_csv_sigatoka
from tests.conftest import campos_parcela


def test_radar_prioriza_estaciones_por_criticidad_y_busqueda_multicriterio(db, admin):
    repo_est = RepositorioEstaciones(db)
    with db:
        est_optima = repo_est.crear("inti-01", "Nodo INTI Estable", TipoEstacion.TERRABIT_INTI)
        est_critica = repo_est.crear("sig-01", "Estación Mundo Nuevo", TipoEstacion.SIGATOKA)
        est_vacia = repo_est.crear("par-01", "Páramo Sin Datos", TipoEstacion.CONSERVACION)

    ServicioParcelas(db).crear(
        admin,
        **campos_parcela(nombre="Lote Musáceas Sur", cultivo="Hortalizas", estacion_id=est_critica.id),
    )

    csv_inti_ok = (
        "Uptime,HumedadA,HumedadB,TempAire,HumAire,Presion,TempRaiz,Voltaje,VPD,SessionID\n"
        "2026-11-13 10:00:00,55.0,52.0,23.0,68.0,852.0,20.5,4.05,0.90,1\n"
        "2026-11-13 10:05:00,55.0,52.0,23.2,67.5,852.0,20.5,4.05,0.92,1\n"
    )
    csv_sig_crit = (
        "Fecha,Hora,Lluvia_mm_min,Velocidad_ms,Direccion,"
        "Temperatura_C,Humedad_pct,Humectacion_Foliar_pct,Duracion_Humectacion_min\n"
        "2026-11-13,06:00:00,0.2,1.2,NE,26.5,92.0,86.0,410\n"
    )
    lect_inti = parsear_csv_nodo_inti(csv_inti_ok, estacion_id=est_optima.id)
    lect_sig, ev_sig = parsear_csv_sigatoka(csv_sig_crit, estacion_id=est_critica.id)
    with db:
        RepositorioLecturas(db).insertar_lote([*lect_inti, *lect_sig])
        RepositorioEventosEstacion(db).insertar_lote(ev_sig)

    radar = StationDiscoveryService(db)
    priorizadas = radar.listar_radar_priorizado()

    assert [e.estacion.id for e in priorizadas] == [est_critica.id, est_optima.id, est_vacia.id]
    assert priorizadas[0].severidad is NivelSeveridadPulso.CRITICO
    assert priorizadas[0].parcelas_asociadas == ("Lote Musáceas Sur",)
    assert priorizadas[1].severidad is NivelSeveridadPulso.OPTIMO
    assert priorizadas[2].severidad is NivelSeveridadPulso.SIN_DATOS

    # Búsqueda por nombre de parcela asociada
    por_parcela = radar.buscar_estaciones("musáceas")
    assert [e.estacion.id for e in por_parcela] == [est_critica.id]

    # Filtro solo con alertas activas
    con_alertas = radar.buscar_estaciones(solo_con_alertas=True)
    assert [e.estacion.id for e in con_alertas] == [est_critica.id]

    # Filtro por tipo de estación
    solo_inti = radar.buscar_estaciones(tipo_estacion=TipoEstacion.TERRABIT_INTI)
    assert [e.estacion.id for e in solo_inti] == [est_optima.id]


def test_deteccion_automatica_e_importacion_de_archivos_de_campo(db, tmp_path: Path):
    (tmp_path / "data.csv").write_text(
        "Uptime,HumedadA,HumedadB,TempAire,HumAire\n2026-11-13 08:00:00,48.0,45.0,24.0,65.0\n",
        encoding="utf-8",
    )
    (tmp_path / "data.json").write_text(
        '{"Fecha":"2026-11-13","Hora":"08:00:00","TempI":30.1,"HumedadI":72.0}\n',
        encoding="utf-8",
    )
    (tmp_path / "MUNDONUEVO.csv").write_text(
        "Fecha,Hora,Lluvia_mm_min,Velocidad_ms,Direccion,"
        "Temperatura_C,Humedad_pct,Humectacion_Foliar_pct,Duracion_Humectacion_min\n"
        "2026-11-13,08:00:00,0.0,1.5,E,25.0,80.0,75.0,30\n",
        encoding="utf-8",
    )
    (tmp_path / "turbera.csv").write_text(
        "Uptime,nivel_freatico_cm,humedad_turba_a,temp_aire,hum_aire\n"
        "2026-11-13 08:00:00,-14.0,88.0,9.5,85.0\n",
        encoding="utf-8",
    )

    detectados = StationDiscoveryService.detectar_archivos_estacion([tmp_path])
    mapa_tipos = {d.ruta_archivo.name: d.tipo_estacion_inferido for d in detectados}

    assert mapa_tipos == {
        "MUNDONUEVO.csv": TipoEstacion.SIGATOKA,
        "data.csv": TipoEstacion.TERRABIT_INTI,
        "data.json": TipoEstacion.INBEERSA,
        "turbera.csv": TipoEstacion.CONSERVACION,
    }

    with db:
        est_sig = RepositorioEstaciones(db).crear("sig-imp", "Sigatoka Importada", TipoEstacion.SIGATOKA)

    res = StationDiscoveryService(db).importar_archivo_estacion(est_sig.id, tmp_path / "MUNDONUEVO.csv")
    assert res.lecturas_nuevas == 9
    assert res.eventos_nuevos == 1


def test_exportacion_ejecutiva_xlsx_tres_hojas_y_csv(db, admin, tmp_path: Path):
    with pytest.raises(ValueError, match="al menos una hoja"):
        escribir_libro_xlsx(tmp_path / "vacio.xlsx", [])

    with db:
        est = RepositorioEstaciones(db).crear(
            "inti-exp",
            "Nodo INTI Exportación",
            TipoEstacion.TERRABIT_INTI,
            latitud=4.795,
            longitud=-75.690,
            altitud_m=1450.0,
        )
    parcela = ServicioParcelas(db).crear(
        admin,
        **campos_parcela(nombre="Lote Exportable", humedad=32, estacion_id=est.id),
    )

    csv_inti = (
        "Uptime,HumedadA,HumedadB,TempAire,HumAire,Presion,TempRaiz,Voltaje,VPD,SessionID\n"
        "2026-11-13 07:00:00,32.0,38.0,22.0,70.0,852.0,20.0,4.08,0.79,1\n"
        "2026-11-13 08:00:00,45.0,40.0,23.5,66.0,851.8,20.4,4.06,0.99,1\n"
    )
    lecturas = parsear_csv_nodo_inti(csv_inti, estacion_id=est.id)
    ts_ref = lecturas[0].ts_epoch

    with db:
        RepositorioLecturas(db).insertar_lote(lecturas)
        RepositorioEventosEstacion(db).insertar_lote(
            [
                EventoEstacion(
                    estacion_id=est.id,
                    tipo_evento="mantenimiento_campo",
                    ts_epoch=ts_ref,
                    ts_iso=lecturas[0].ts_iso,
                    valor_texto="Limpieza de celda solar",
                )
            ]
        )

    res_riego = ServicioRiego(db).aplicar_riego(
        admin,
        parcela_id=parcela.id,
        umbral_pct=45,
        litros=50,
        fecha=date(2026, 11, 13),
        hora="07:30",
    )
    assert res_riego.evento is not None
    DecisionAndControlService(db).registrar_verificacion_e_incidencia(
        evento_riego_id=res_riego.evento.id,
        humedad_a_antes=32.0,
        humedad_a_despues=45.0,
        humedad_b_antes=38.0,
        humedad_b_despues=40.0,
    )

    srv_exp = AnalyticsAndExportService(db)
    ruta_xlsx = srv_exp.exportar_xlsx_estacion(est.id, tmp_path / "reporte_ejecutivo.xlsx", ventana="1h")
    ruta_csv = srv_exp.exportar_csv_estacion(est.id, tmp_path / "series_estacion.csv", ventana="1h")

    assert ruta_xlsx.exists()
    assert ruta_csv.exists()

    hojas = leer_hojas_xlsx(ruta_xlsx)
    assert list(hojas.keys()) == ["1_Ficha_y_Resumen", "2_Series_Temporales", "3_Eventos_y_Riegos"]

    # Verificar Hoja 1 (Ficha y estadísticas)
    textos_h1 = {fila[0]: fila[1] for fila in hojas["1_Ficha_y_Resumen"] if len(fila) >= 2}
    assert textos_h1["Codigo_Estacion"] == "inti-exp"
    assert textos_h1["Severidad_Periodo"] == "optimo"
    assert "suelo_a" in textos_h1

    # Verificar Hoja 2 (Series en formato ancho con media móvil)
    encabezados_h2 = hojas["2_Series_Temporales"][0]
    assert "suelo_a" in encabezados_h2
    assert "suelo_a_media_movil_1h" in encabezados_h2
    assert len(hojas["2_Series_Temporales"]) == 3  # 1 encabezado + 2 timestamps

    # Verificar Hoja 3 (Riego con efectividad + Evento de estación)
    filas_h3 = hojas["3_Eventos_y_Riegos"]
    categorias = [f[0] for f in filas_h3[1:]]
    assert "RIEGO" in categorias
    assert "EVENTO_ESTACION" in categorias

    contenido_csv = ruta_csv.read_text(encoding="utf-8")
    assert "suelo_a_media_movil_1h" in contenido_csv
    assert isinstance(HojaCalculo("Test", ("A",), [[1]]), HojaCalculo)
