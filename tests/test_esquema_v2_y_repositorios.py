"""Pruebas del esquema SQLite v2 y los repositorios de control, calibración y copiloto."""

from __future__ import annotations

from datetime import date

import pytest

from aquaterra.application.servicios import ServicioParcelas, ServicioRiego
from aquaterra.core import tiempo
from aquaterra.core.domain import (
    DiagnosticoMecanicoBomba,
    EfectividadRiego,
    EstadoRiegoProgramado,
    EventoEstacion,
    ModoVerificacionRiego,
    PuntoPronosticoClima,
    TipoEstacion,
)
from aquaterra.infrastructure.db import abrir_conexion
from aquaterra.infrastructure.db.esquema import (
    _MIGRACION_001,
    VERSION_ESQUEMA,
    aplicar_migraciones,
    version_actual,
)
from aquaterra.infrastructure.db.repositorios import (
    RepositorioCalibraciones,
    RepositorioCopiloto,
    RepositorioEstaciones,
    RepositorioEventosEstacion,
    RepositorioIncidenciaRiego,
    RepositorioPronosticoClima,
    RepositorioRiegosProgramados,
    RepositorioSaludActuadores,
)
from tests.conftest import campos_parcela

_TABLAS_V2 = {
    "eventos_estacion",
    "calibraciones_nodo",
    "salud_actuadores_log",
    "incidencia_riego",
    "riegos_programados",
    "pronostico_clima_cache",
    "conversaciones_copiloto",
}


def test_esquema_actual_es_v2_y_migracion_incremental_desde_v1():
    assert VERSION_ESQUEMA == 2

    conexion = abrir_conexion(":memory:")
    try:
        conexion.executescript(f"BEGIN;\n{_MIGRACION_001}\nPRAGMA user_version = 1;\nCOMMIT;")
        assert version_actual(conexion) == 1

        version_final = aplicar_migraciones(conexion)
        assert version_final == 2

        tablas = {
            fila[0]
            for fila in conexion.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
        assert _TABLAS_V2.issubset(tablas)
    finally:
        conexion.close()


def test_calibraciones_versionadas_y_rollback_en_un_clic(db, admin):
    with db:
        est = RepositorioEstaciones(db).crear("inti-cal-01", "Nodo INTI Cal", TipoEstacion.TERRABIT_INTI)

    repo = RepositorioCalibraciones(db)
    with pytest.raises(ValueError, match="estacion_id o parcela_id"):
        repo.guardar_nueva_version(parametros={"adc_seco": 3100}, motivo="Sin ancla", autor_id=admin.id)

    with db:
        v1 = repo.guardar_nueva_version(
            estacion_id=est.id,
            parametros={"adc_seco": 3200, "adc_agua": 1350, "ema_alpha": 0.25},
            motivo="Calibración inicial en laboratorio",
            autor_id=admin.id,
        )
        v2 = repo.guardar_nueva_version(
            estacion_id=est.id,
            parametros={"adc_seco": 3350, "adc_agua": 1400, "ema_alpha": 0.15},
            motivo="Ajuste tras cambio de sustrato",
            autor_id=admin.id,
        )

    assert (v1.version, v2.version) == (1, 2)
    activa = repo.obtener_activa(estacion_id=est.id)
    assert activa is not None
    assert activa.id == v2.id
    assert activa.activa is True

    with db:
        v3 = repo.restaurar_version(v1.id, autor_id=admin.id)

    assert v3.version == 3
    assert v3.activa is True
    assert v3.parametros == v1.parametros
    assert "v1" in v3.motivo

    historial = repo.listar_versiones(estacion_id=est.id)
    assert [c.version for c in historial] == [1, 2, 3]
    assert [c.activa for c in historial] == [False, False, True]


def test_salud_actuadores_e_incidencia_riego(db, admin):
    parcela = ServicioParcelas(db).crear(admin, **campos_parcela(nombre="Lote Bomba 1"))
    resultado = ServicioRiego(db).aplicar_riego(
        admin,
        parcela_id=parcela.id,
        umbral_pct=45,
        litros=60,
        fecha=date(2026, 11, 13),
        hora="07:00",
    )
    assert resultado.aplicado is True
    assert resultado.evento is not None
    evento = resultado.evento

    repo_salud = RepositorioSaludActuadores(db)
    repo_inc = RepositorioIncidenciaRiego(db)
    with db:
        salud = repo_salud.registrar(
            evento_riego_id=evento.id,
            modo_verificacion=ModoVerificacionRiego.VIBRACION_RMS,
            diagnostico_mecanico=DiagnosticoMecanicoBomba.NOMINAL,
            apertura_max_pct=80.0,
            vibracion_rms_g=0.28,
            vibracion_freq_hz=58.5,
            corriente_a=3.4,
            caudal_lpm=12.5,
        )
        incidencia = repo_inc.registrar(
            evento_riego_id=evento.id,
            humedad_a_antes=31.0,
            humedad_a_despues=46.5,
            humedad_b_antes=29.5,
            humedad_b_despues=38.0,
            efectividad=EfectividadRiego.EFECTIVO,
            observaciones="Infiltración homogénea en ambos horizontes",
        )

    assert repo_salud.por_evento(evento.id) == salud
    assert salud.vibracion_rms_g == pytest.approx(0.28)
    assert salud.vibracion_freq_hz == pytest.approx(58.5)

    leida = repo_inc.por_evento(evento.id)
    assert leida == incidencia
    assert leida.delta_a_pct == pytest.approx(15.5)
    assert leida.delta_b_pct == pytest.approx(8.5)
    assert repo_inc.listar_por_parcela(parcela.id) == [incidencia]


def test_riegos_programados_e_interlock(db, admin):
    parcela = ServicioParcelas(db).crear(admin, **campos_parcela(nombre="Lote Interlock"))
    repo = RepositorioRiegosProgramados(db)
    momento = tiempo.combinar(date(2026, 11, 14), tiempo.parsear_hora("05:30"))

    with db:
        prog = repo.programar(
            parcela_id=parcela.id,
            ts_programado_epoch=tiempo.a_epoch(momento),
            ts_programado_iso=tiempo.a_iso(momento),
            litros_propuestos=85.0,
            apertura_max_pct=50.0,
        )

    assert prog.estado == EstadoRiegoProgramado.PENDIENTE
    assert len(repo.listar_pendientes(parcela_id=parcela.id)) == 1

    with db:
        bloqueado = repo.actualizar_estado(
            prog.id,
            EstadoRiegoProgramado.BLOQUEADO_INTERLOCK,
            motivo_bloqueo="Lluvia activa > 5 mm/h detectada en estación",
        )

    assert bloqueado.estado == EstadoRiegoProgramado.BLOQUEADO_INTERLOCK
    assert "Lluvia activa" in (bloqueado.motivo_bloqueo or "")
    assert repo.listar_pendientes(parcela_id=parcela.id) == []


def test_pronostico_clima_eventos_estacion_y_copiloto(db, admin):
    with db:
        est = RepositorioEstaciones(db).crear("sig-02", "Estación Mundo Nuevo", TipoEstacion.SIGATOKA)
    parcela = ServicioParcelas(db).crear(admin, **campos_parcela(nombre="Musáceas"))

    base_epoch = 1_794_600_000
    puntos_v1 = [
        PuntoPronosticoClima(
            estacion_id=est.id,
            ts_objetivo_epoch=base_epoch,
            ts_objetivo_iso=tiempo.a_iso(tiempo.desde_epoch(base_epoch)),
            temp_c=23.5,
            hum_relativa_pct=84.0,
            lluvia_prob_pct=70.0,
            lluvia_mm=4.2,
            viento_ms=1.8,
            et0_mm=3.1,
        ),
        PuntoPronosticoClima(
            estacion_id=est.id,
            ts_objetivo_epoch=base_epoch + 3600,
            ts_objetivo_iso=tiempo.a_iso(tiempo.desde_epoch(base_epoch + 3600)),
            temp_c=22.0,
            hum_relativa_pct=88.0,
            lluvia_prob_pct=85.0,
            lluvia_mm=9.5,
        ),
    ]
    punto_actualizado = [
        PuntoPronosticoClima(
            estacion_id=est.id,
            ts_objetivo_epoch=base_epoch,
            ts_objetivo_iso=tiempo.a_iso(tiempo.desde_epoch(base_epoch)),
            temp_c=24.0,
            hum_relativa_pct=80.0,
            lluvia_prob_pct=65.0,
            lluvia_mm=3.0,
        )
    ]

    repo_clima = RepositorioPronosticoClima(db)
    repo_eventos = RepositorioEventosEstacion(db)
    repo_copiloto = RepositorioCopiloto(db)
    with db:
        repo_clima.guardar_lote(puntos_v1)
        repo_clima.guardar_lote(punto_actualizado)

        insertados = repo_eventos.insertar_lote(
            [
                EventoEstacion(
                    estacion_id=est.id,
                    tipo_evento="cambio_clima",
                    ts_epoch=base_epoch,
                    ts_iso=tiempo.a_iso(tiempo.desde_epoch(base_epoch)),
                    valor_texto="Tormenta vespertina",
                    metadatos={"origen": "pluviometro"},
                )
            ]
        )
        interaccion = repo_copiloto.registrar(
            estacion_id=est.id,
            parcela_id=parcela.id,
            usuario_id=admin.id,
            mensaje_usuario="La última vez regué de más en el lote",
            diagnostico_ia="Reducir pulso máximo y esperar drenaje de horizonte B",
            ajustes_propuestos={"umbral_riego_pct": 38.0, "apertura_max_pct": 60.0},
            proveedor_ia="heuristico_local",
        )

    ventana = repo_clima.ventana(est.id, desde_epoch=base_epoch, hasta_epoch=base_epoch + 3600)
    assert len(ventana) == 2
    assert ventana[0].lluvia_mm == pytest.approx(3.0)  # Upsert reemplazó el mismo ts_objetivo_epoch

    eventos = repo_eventos.listar(est.id, tipo_evento="cambio_clima")
    assert insertados == 1
    assert len(eventos) == 1
    assert eventos[0].metadatos == {"origen": "pluviometro"}

    conversaciones = repo_copiloto.listar(estacion_id=est.id, parcela_id=parcela.id)
    assert len(conversaciones) == 1
    assert conversaciones[0] == interaccion
    assert conversaciones[0].ajustes_propuestos == {"umbral_riego_pct": 38.0, "apertura_max_pct": 60.0}
