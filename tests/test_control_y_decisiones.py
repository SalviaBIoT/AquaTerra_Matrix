"""Pruebas de Fase B3: Enclavamientos (5 candados), diagnóstico de bomba, incidencia post-riego y planificador."""

from __future__ import annotations

from datetime import date

import pytest

from aquaterra.application import DecisionAndControlService, ServicioParcelas, ServicioRiego
from aquaterra.core import tiempo
from aquaterra.core.control import (
    AccionRecomendadaRiego,
    CodigoCandado,
    ContextoSeguridadRiego,
    SafetyInterlockEngine,
    diagnosticar_salud_bomba,
    evaluar_incidencia_riego,
)
from aquaterra.core.domain import (
    DiagnosticoMecanicoBomba,
    EfectividadRiego,
    ErrorPermiso,
    EstadoRiegoProgramado,
    LecturaSensor,
    ModoVerificacionRiego,
    PuntoPronosticoClima,
    TipoEstacion,
    TipoSuelo,
)
from aquaterra.infrastructure.db.repositorios import (
    RepositorioEstaciones,
    RepositorioLecturas,
    RepositorioPronosticoClima,
)
from tests.conftest import campos_parcela


def _lectura(estacion_id: int, variable: str, valor: float, ts_epoch: int) -> LecturaSensor:
    return LecturaSensor(
        estacion_id=estacion_id,
        variable=variable,
        valor=valor,
        unidad="%",
        ts_epoch=ts_epoch,
        ts_iso=tiempo.a_iso(tiempo.desde_epoch(ts_epoch)),
        fuente="sd_csv",
        calidad=0,
    )


def test_enclavamientos_5_candados_bloqueos_y_recortes():
    # 1. Recorte de volumen máximo (Riesgo 2: 2000 L en 20 m² Franco -> tope 120 L) y llovizna (apertura -> 50%)
    veredicto_recorte = SafetyInterlockEngine.evaluar(
        ContextoSeguridadRiego(
            area_m2=20.0,
            tipo_suelo=TipoSuelo.FRANCO,
            humedad_actual_pct=35.0,
            litros_solicitados=2000.0,
            apertura_solicitada_pct=100.0,
            lluvia_pronosticada_24h_mm=5.0,
            prob_lluvia_24h_pct=80.0,
            voltaje_nodo_v=3.95,
        )
    )
    assert veredicto_recorte.autorizado is True
    assert veredicto_recorte.litros_autorizados == pytest.approx(120.0)
    assert veredicto_recorte.apertura_autorizada_pct == pytest.approx(50.0)
    assert len(veredicto_recorte.advertencias_recorte) == 2

    # 2. Bloqueos múltiples: lluvia torrencial + suelo saturado + batería baja
    veredicto_bloqueado = SafetyInterlockEngine.evaluar(
        ContextoSeguridadRiego(
            area_m2=50.0,
            tipo_suelo=TipoSuelo.FRANCO,
            humedad_actual_pct=85.0,
            litros_solicitados=100.0,
            lluvia_actual_mm_min=0.30,
            voltaje_nodo_v=3.20,
        )
    )
    assert veredicto_bloqueado.autorizado is False
    assert veredicto_bloqueado.litros_autorizados == 0.0
    assert veredicto_bloqueado.apertura_autorizada_pct == 0.0
    fallidos = {c.codigo for c in veredicto_bloqueado.candados if not c.superado}
    assert fallidos == {
        CodigoCandado.CANDADO_LLUVIA_ACTIVA,
        CodigoCandado.CANDADO_SATURACION,
        CodigoCandado.CANDADO_ENERGIA_NODO,
    }

    # 3. Candado de bomba es transparente en modo SIN_SENSOR_ACTUADOR (sin bomba física hoy)
    veredicto_sin_bomba = SafetyInterlockEngine.evaluar(
        ContextoSeguridadRiego(
            area_m2=50.0,
            tipo_suelo=TipoSuelo.FRANCO,
            humedad_actual_pct=35.0,
            litros_solicitados=100.0,
            modo_verificacion=ModoVerificacionRiego.SIN_SENSOR_ACTUADOR,
            ultimo_diagnostico_bomba=DiagnosticoMecanicoBomba.CAVITACION_O_VACIO,
        )
    )
    assert veredicto_sin_bomba.autorizado is True


def test_diagnostico_salud_bomba_en_4_modos_y_evaluacion_incidencia():
    assert (
        diagnosticar_salud_bomba(ModoVerificacionRiego.SIN_SENSOR_ACTUADOR)
        is DiagnosticoMecanicoBomba.SIN_TELEMETRIA
    )
    assert (
        diagnosticar_salud_bomba(ModoVerificacionRiego.VIBRACION_RMS, vibracion_rms_g=0.02)
        is DiagnosticoMecanicoBomba.FALLO_NO_ARRANCO
    )
    assert (
        diagnosticar_salud_bomba(ModoVerificacionRiego.VIBRACION_RMS, vibracion_rms_g=2.10)
        is DiagnosticoMecanicoBomba.SOBRECARGA_MECANICA
    )
    assert (
        diagnosticar_salud_bomba(
            ModoVerificacionRiego.VIBRACION_RMS,
            vibracion_rms_g=0.45,
            vibracion_freq_hz=165.0,
        )
        is DiagnosticoMecanicoBomba.CAVITACION_O_VACIO
    )
    assert (
        diagnosticar_salud_bomba(
            ModoVerificacionRiego.VIBRACION_RMS,
            vibracion_rms_g=0.35,
            vibracion_freq_hz=58.0,
        )
        is DiagnosticoMecanicoBomba.NOMINAL
    )
    assert (
        diagnosticar_salud_bomba(
            ModoVerificacionRiego.CORRIENTE_O_CAUDAL,
            corriente_a=3.5,
            caudal_lpm=0.0,
        )
        is DiagnosticoMecanicoBomba.CAVITACION_O_VACIO
    )
    assert (
        diagnosticar_salud_bomba(
            ModoVerificacionRiego.IMPACTO_SUELO_DIFERIDO,
            delta_suelo_a_pct=12.0,
        )
        is DiagnosticoMecanicoBomba.NOMINAL
    )

    assert (
        evaluar_incidencia_riego(30.0, 30.8).efectividad
        is EfectividadRiego.SIN_RESPUESTA_EN_SUELO
    )
    assert (
        evaluar_incidencia_riego(30.0, 33.5).efectividad
        is EfectividadRiego.INFILTRACION_PARCIAL
    )
    assert (
        evaluar_incidencia_riego(30.0, 42.0, humedad_b_antes=30.0, humedad_b_despues=40.5).efectividad
        is EfectividadRiego.EXCESO_PERCOLACION
    )
    assert (
        evaluar_incidencia_riego(30.0, 45.0, humedad_b_antes=30.0, humedad_b_despues=33.0).efectividad
        is EfectividadRiego.EFECTIVO
    )


def test_recomendador_proactivo_cruza_secado_y_pronostico_lluvia(db, admin):
    with db:
        est = RepositorioEstaciones(db).crear("inti-ctrl", "Nodo Control", TipoEstacion.TERRABIT_INTI)
    parcela = ServicioParcelas(db).crear(
        admin,
        **campos_parcela(nombre="Lote Proactivo", area="50", humedad=42, estacion_id=est.id),
    )

    t0 = 1_794_600_000
    # Suelo A está en 42% (> umbral 40%), pero cayendo a -1.0 %/h -> tocará 40% en 2.0 horas
    with db:
        RepositorioLecturas(db).insertar_lote(
            [
                _lectura(est.id, "suelo_a", 44.0, t0 - 7200),
                _lectura(est.id, "suelo_a", 43.0, t0 - 3600),
                _lectura(est.id, "suelo_a", 42.0, t0),
                _lectura(est.id, "voltaje", 3.95, t0),
            ]
        )

    srv = DecisionAndControlService(db)
    rec_preventiva = srv.recomendar_riego_parcela(
        parcela.id,
        umbral_disparo_pct=40.0,
        momento_epoch=t0,
    )
    assert rec_preventiva.accion is AccionRecomendadaRiego.PROGRAMAR_PREVENTIVO
    assert rec_preventiva.regar is True
    assert rec_preventiva.horas_hasta_estres == pytest.approx(2.0)

    # Ahora entra un pronóstico de 7.5 mm de lluvia con 80 % de probabilidad en las próximas horas:
    with db:
        RepositorioPronosticoClima(db).guardar_lote(
            [
                PuntoPronosticoClima(
                    estacion_id=est.id,
                    ts_objetivo_epoch=t0 + 3600,
                    ts_objetivo_iso=tiempo.a_iso(tiempo.desde_epoch(t0 + 3600)),
                    lluvia_mm=7.5,
                    lluvia_prob_pct=80.0,
                )
            ]
        )

    rec_pospuesta = srv.recomendar_riego_parcela(
        parcela.id,
        umbral_disparo_pct=40.0,
        momento_epoch=t0,
    )
    assert rec_pospuesta.accion is AccionRecomendadaRiego.POSPONER_POR_LLUVIA
    assert rec_pospuesta.regar is False


def test_servicio_control_programar_bloqueo_interlock_y_post_evaluacion(db, admin, operador):
    parcela = ServicioParcelas(db).crear(
        admin,
        **campos_parcela(nombre="Lote Seguridad", area="30", humedad=32),
    )
    srv = DecisionAndControlService(db)
    t_prog = 1_794_650_000

    with pytest.raises(ErrorPermiso):
        srv.programar_riego_validado(
            operador,
            parcela_id=parcela.id,
            ts_programado_epoch=t_prog,
            litros_solicitados=50.0,
        )

    # 1. Programación válida (sin sensor de bomba instalado aún) con recorte de volumen (30 m² * 6 L/m² = 180 L)
    prog_ok, ver_ok = srv.programar_riego_validado(
        admin,
        parcela_id=parcela.id,
        ts_programado_epoch=t_prog,
        litros_solicitados=500.0,
    )
    assert ver_ok.autorizado is True
    assert prog_ok.estado is EstadoRiegoProgramado.PENDIENTE
    assert prog_ok.litros_propuestos == pytest.approx(180.0)

    # 2. Se ejecuta un riego y al evaluarlo con sensor de vibración se detecta que la bomba no arrancó
    res_riego = ServicioRiego(db).aplicar_riego(
        admin,
        parcela_id=parcela.id,
        umbral_pct=45,
        litros=60,
        fecha=date(2026, 11, 13),
        hora="08:00",
    )
    assert res_riego.evento is not None
    # Bajamos humedad nuevamente a 32 % para probar el candado de bomba (y no el de saturación)
    ServicioParcelas(db).actualizar(admin, parcela.id, **campos_parcela(nombre="Lote Seguridad", area="30", humedad=32))

    salud, incidencia = srv.registrar_verificacion_e_incidencia(
        evento_riego_id=res_riego.evento.id,
        humedad_a_antes=32.0,
        humedad_a_despues=32.4,
        modo_verificacion=ModoVerificacionRiego.VIBRACION_RMS,
        vibracion_rms_g=0.01,
    )
    assert salud.diagnostico_mecanico is DiagnosticoMecanicoBomba.FALLO_NO_ARRANCO
    assert incidencia.efectividad is EfectividadRiego.SIN_RESPUESTA_EN_SUELO

    # 3. Al intentar programar otro riego con verificación VIBRACION_RMS sin mantenimiento confirmado, se bloquea
    prog_bloq, ver_bloq = srv.programar_riego_validado(
        admin,
        parcela_id=parcela.id,
        ts_programado_epoch=t_prog + 3600,
        litros_solicitados=80.0,
        modo_verificacion=ModoVerificacionRiego.VIBRACION_RMS,
    )
    assert ver_bloq.autorizado is False
    assert prog_bloq.estado is EstadoRiegoProgramado.BLOQUEADO_INTERLOCK
    assert "fallo_no_arranco" in (prog_bloq.motivo_bloqueo or "")
