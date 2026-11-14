"""Servicio de aplicación para Toma de Decisiones, Enclavamientos, Salud de Bomba e Incidencia de Riego.

Orquesta ``SafetyInterlockEngine``, el recomendador proactivo, la evaluación de bombas
(tanto en modo ``SIN_SENSOR_ACTUADOR`` actual como con acelerómetro/caudalímetro a futuro)
y la trazabilidad de efectividad en suelo (Fase B3 — Pestaña 3).
"""

from __future__ import annotations

import sqlite3
from typing import Any

from aquaterra.core import tiempo
from aquaterra.core.analitica.series import tasa_cambio_por_hora
from aquaterra.core.control import (
    ContextoSeguridadRiego,
    RecomendacionRiego,
    SafetyInterlockEngine,
    VeredictoEnclavamientos,
    diagnosticar_salud_bomba,
    evaluar_incidencia_riego,
    generar_recomendacion_proactiva,
)
from aquaterra.core.domain import (
    DiagnosticoMecanicoBomba,
    ErrorPermiso,
    EstadoRiegoProgramado,
    IncidenciaRiego,
    ModoVerificacionRiego,
    Parcela,
    RegistroSaludActuador,
    RiegoProgramado,
    Usuario,
)
from aquaterra.infrastructure.db.repositorios import (
    RepositorioAuditoria,
    RepositorioCalibraciones,
    RepositorioIncidenciaRiego,
    RepositorioLecturas,
    RepositorioParcelas,
    RepositorioPronosticoClima,
    RepositorioRiegosProgramados,
    RepositorioSaludActuadores,
)


class DecisionAndControlService:
    """Orquestador de recomendaciones proactivas, enclavamientos duros, cola de riegos y post-evaluación."""

    def __init__(self, conexion: sqlite3.Connection):
        self._db = conexion
        self._parcelas = RepositorioParcelas(conexion)
        self._lecturas = RepositorioLecturas(conexion)
        self._clima = RepositorioPronosticoClima(conexion)
        self._calibraciones = RepositorioCalibraciones(conexion)
        self._salud_act = RepositorioSaludActuadores(conexion)
        self._incidencia = RepositorioIncidenciaRiego(conexion)
        self._programados = RepositorioRiegosProgramados(conexion)
        self._auditoria = RepositorioAuditoria(conexion)

    def _parametros_calibracion(self, parcela: Parcela) -> dict[str, Any]:
        cal = self._calibraciones.obtener_activa(parcela_id=parcela.id)
        if cal is None and parcela.estacion_id is not None:
            cal = self._calibraciones.obtener_activa(estacion_id=parcela.estacion_id)
        return dict(cal.parametros) if cal else {}

    def _contexto_telemetria(
        self,
        parcela: Parcela,
        *,
        momento_epoch: int,
    ) -> tuple[float, float | None, float, float, float, float | None]:
        """Devuelve (humedad_actual, tasa_secado_h, lluvia_actual_mm_min, lluvia_24h_mm, prob_24h_pct, voltaje_v)."""
        humedad_actual = parcela.humedad_pct
        tasa_secado: float | None = None
        lluvia_actual = 0.0
        lluvia_24h = 0.0
        prob_24h = 0.0
        voltaje_v: float | None = None

        if parcela.estacion_id is not None:
            est_id = parcela.estacion_id
            techo = self._lecturas.ultimo_epoch(est_id) or momento_epoch
            piso_24h = techo - 86_400

            serie_suelo = self._lecturas.serie_rango(est_id, "suelo_a", desde_epoch=piso_24h, hasta_epoch=techo)
            if serie_suelo:
                humedad_actual = serie_suelo[-1][1]
                tasa_secado = tasa_cambio_por_hora(serie_suelo)

            serie_volt = self._lecturas.serie_rango(est_id, "voltaje", desde_epoch=piso_24h, hasta_epoch=techo)
            if serie_volt:
                voltaje_v = serie_volt[-1][1]

            serie_lluvia = self._lecturas.serie_rango(
                est_id, "lluvia_mm_min", desde_epoch=techo - 1_800, hasta_epoch=techo
            )
            if serie_lluvia:
                lluvia_actual = serie_lluvia[-1][1]

            pronosticos = self._clima.ventana(
                est_id,
                desde_epoch=momento_epoch,
                hasta_epoch=momento_epoch + 86_400,
            )
            if pronosticos:
                lluvia_24h = round(sum(p.lluvia_mm or 0.0 for p in pronosticos), 2)
                prob_24h = max((p.lluvia_prob_pct or 0.0 for p in pronosticos), default=0.0)

        return humedad_actual, tasa_secado, lluvia_actual, lluvia_24h, prob_24h, voltaje_v

    def recomendar_riego_parcela(
        self,
        parcela_id: int,
        *,
        umbral_disparo_pct: float | None = None,
        momento_epoch: int | None = None,
    ) -> RecomendacionRiego:
        """Cruza humedad, tasa de secado, pronóstico climático, calibración y enclavamientos de la parcela."""
        parcela = self._parcelas.obtener(parcela_id)
        params = self._parametros_calibracion(parcela)
        ahora_ep = momento_epoch if momento_epoch is not None else tiempo.a_epoch(tiempo.ahora())

        hum_act, tasa_sec, lluvia_act, lluvia_24h, prob_24h, volt_v = self._contexto_telemetria(
            parcela,
            momento_epoch=ahora_ep,
        )
        umbral = (
            float(umbral_disparo_pct)
            if umbral_disparo_pct is not None
            else float(params.get("umbral_disparo_pct", 40.0))
        )
        modo_str = str(params.get("modo_verificacion", ModoVerificacionRiego.SIN_SENSOR_ACTUADOR.value))
        modo_verif = ModoVerificacionRiego(modo_str)

        ultimo_reg = self._salud_act.ultimo_por_parcela(parcela.id)
        ultimo_diag: DiagnosticoMecanicoBomba | None = (
            ultimo_reg.diagnostico_mecanico if ultimo_reg else None
        )

        return generar_recomendacion_proactiva(
            area_m2=parcela.area_m2,
            tipo_suelo=parcela.tipo_suelo,
            humedad_actual_pct=hum_act,
            umbral_disparo_pct=umbral,
            tasa_secado_pct_h=tasa_sec,
            lluvia_actual_mm_min=lluvia_act,
            lluvia_pronosticada_24h_mm=lluvia_24h,
            prob_lluvia_24h_pct=prob_24h,
            voltaje_nodo_v=volt_v,
            modo_verificacion=modo_verif,
            ultimo_diagnostico_bomba=ultimo_diag,
            capacidad_campo_pct=(
                float(params["capacidad_campo_pct"]) if "capacidad_campo_pct" in params else None
            ),
            lamina_max_l_m2=(
                float(params["lamina_max_l_m2"]) if "lamina_max_l_m2" in params else None
            ),
        )

    def programar_riego_validado(
        self,
        actor: Usuario,
        *,
        parcela_id: int,
        ts_programado_epoch: int,
        litros_solicitados: float,
        apertura_solicitada_pct: float = 100.0,
        origen: str = "ia_proactivo",
        modo_verificacion: ModoVerificacionRiego = ModoVerificacionRiego.SIN_SENSOR_ACTUADOR,
        mantenimiento_confirmado: bool = False,
    ) -> tuple[RiegoProgramado, VeredictoEnclavamientos]:
        """Valida los 5 candados de seguridad y registra el riego en cola (o lo marca bloqueado con motivo)."""
        if not actor.es_admin:
            raise ErrorPermiso("programar riegos")

        parcela = self._parcelas.obtener(parcela_id)
        params = self._parametros_calibracion(parcela)
        hum_act, _, lluvia_act, lluvia_24h, prob_24h, volt_v = self._contexto_telemetria(
            parcela,
            momento_epoch=ts_programado_epoch,
        )
        ultimo_reg = self._salud_act.ultimo_por_parcela(parcela.id)

        veredicto = SafetyInterlockEngine.evaluar(
            ContextoSeguridadRiego(
                area_m2=parcela.area_m2,
                tipo_suelo=parcela.tipo_suelo,
                humedad_actual_pct=hum_act,
                litros_solicitados=litros_solicitados,
                apertura_solicitada_pct=apertura_solicitada_pct,
                capacidad_campo_pct=(
                    float(params["capacidad_campo_pct"]) if "capacidad_campo_pct" in params else None
                ),
                lamina_max_l_m2=(
                    float(params["lamina_max_l_m2"]) if "lamina_max_l_m2" in params else None
                ),
                lluvia_actual_mm_min=lluvia_act,
                lluvia_pronosticada_24h_mm=lluvia_24h,
                prob_lluvia_24h_pct=prob_24h,
                voltaje_nodo_v=volt_v,
                modo_verificacion=modo_verificacion,
                ultimo_diagnostico_bomba=(
                    ultimo_reg.diagnostico_mecanico if ultimo_reg else None
                ),
                mantenimiento_confirmado=mantenimiento_confirmado,
            )
        )

        ts_iso = tiempo.a_iso(tiempo.desde_epoch(ts_programado_epoch))
        litros_guardar = veredicto.litros_autorizados if veredicto.autorizado else max(litros_solicitados, 0.1)
        apertura_guardar = veredicto.apertura_autorizada_pct if veredicto.autorizado else 0.0

        with self._db:
            prog = self._programados.programar(
                parcela_id=parcela.id,
                ts_programado_epoch=ts_programado_epoch,
                ts_programado_iso=ts_iso,
                litros_propuestos=litros_guardar,
                apertura_max_pct=apertura_guardar,
                origen=origen,
            )
            if not veredicto.autorizado:
                motivo = "; ".join(veredicto.motivos_bloqueo)
                prog = self._programados.actualizar_estado(
                    prog.id,
                    EstadoRiegoProgramado.BLOQUEADO_INTERLOCK,
                    motivo_bloqueo=motivo,
                )
            self._auditoria.registrar(
                "programar_riego" if veredicto.autorizado else "bloqueo_interlock_riego",
                "riego_programado",
                prog.id,
                actor.id,
                {
                    "parcela_id": parcela.id,
                    "autorizado": veredicto.autorizado,
                    "litros": prog.litros_propuestos,
                    "apertura_pct": prog.apertura_max_pct,
                    "motivos_bloqueo": list(veredicto.motivos_bloqueo),
                },
            )
        return prog, veredicto

    def registrar_verificacion_e_incidencia(
        self,
        *,
        evento_riego_id: int,
        humedad_a_antes: float,
        humedad_a_despues: float,
        humedad_b_antes: float | None = None,
        humedad_b_despues: float | None = None,
        modo_verificacion: ModoVerificacionRiego = ModoVerificacionRiego.SIN_SENSOR_ACTUADOR,
        apertura_max_pct: float = 100.0,
        vibracion_rms_g: float | None = None,
        vibracion_freq_hz: float | None = None,
        corriente_a: float | None = None,
        caudal_lpm: float | None = None,
    ) -> tuple[RegistroSaludActuador, IncidenciaRiego]:
        """Evalúa y persiste atómicamente la salud mecánica del actuador y la incidencia real en el suelo."""
        eval_suelo = evaluar_incidencia_riego(
            humedad_a_antes,
            humedad_a_despues,
            humedad_b_antes=humedad_b_antes,
            humedad_b_despues=humedad_b_despues,
        )
        diag_bomba = diagnosticar_salud_bomba(
            modo_verificacion,
            vibracion_rms_g=vibracion_rms_g,
            vibracion_freq_hz=vibracion_freq_hz,
            corriente_a=corriente_a,
            caudal_lpm=caudal_lpm,
            delta_suelo_a_pct=eval_suelo.delta_a_pct,
        )

        with self._db:
            salud = self._salud_act.registrar(
                evento_riego_id=evento_riego_id,
                modo_verificacion=modo_verificacion,
                diagnostico_mecanico=diag_bomba,
                apertura_max_pct=apertura_max_pct,
                vibracion_rms_g=vibracion_rms_g,
                vibracion_freq_hz=vibracion_freq_hz,
                corriente_a=corriente_a,
                caudal_lpm=caudal_lpm,
            )
            incidencia = self._incidencia.registrar(
                evento_riego_id=evento_riego_id,
                humedad_a_antes=humedad_a_antes,
                humedad_a_despues=humedad_a_despues,
                humedad_b_antes=humedad_b_antes,
                humedad_b_despues=humedad_b_despues,
                efectividad=eval_suelo.efectividad,
                observaciones=eval_suelo.observaciones,
            )
        return salud, incidencia
