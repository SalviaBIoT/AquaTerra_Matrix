"""Diagnóstico hidromecánico de bomba y evaluación de incidencia post-riego (Dominio Puro — Cero I/O).

Diseñado con arquitectura desacoplada para operar:
- **Hoy (sin bomba ni acelerómetro instalados):** mediante ``ModoVerificacionRiego.SIN_SENSOR_ACTUADOR``
  o ``ModoVerificacionRiego.IMPACTO_SUELO_DIFERIDO`` (evaluando la respuesta real en los sensores de
  suelo Horizonte A y Horizonte B).
- **A futuro (cuando se incorpore motobomba + MPU6050/ADXL345 o sensor de corriente/caudal):**
  mediante ``ModoVerificacionRiego.VIBRACION_RMS`` y ``ModoVerificacionRiego.CORRIENTE_O_CAUDAL``.
"""

from __future__ import annotations

from dataclasses import dataclass

from aquaterra.core.domain import (
    DiagnosticoMecanicoBomba,
    EfectividadRiego,
    ModoVerificacionRiego,
)


@dataclass(frozen=True, slots=True)
class UmbralesSaludBomba:
    vibracion_min_arranque_g: float = 0.08
    vibracion_max_nominal_g: float = 1.50
    frecuencia_cavitacion_hz: float = 120.0
    corriente_min_arranque_a: float = 0.35
    corriente_max_nominal_a: float = 12.0
    caudal_min_operativo_lpm: float = 1.0


@dataclass(frozen=True, slots=True)
class ResultadoIncidenciaRiego:
    delta_a_pct: float
    delta_b_pct: float | None
    efectividad: EfectividadRiego
    observaciones: str


def diagnosticar_salud_bomba(
    modo_verificacion: ModoVerificacionRiego,
    *,
    vibracion_rms_g: float | None = None,
    vibracion_freq_hz: float | None = None,
    corriente_a: float | None = None,
    caudal_lpm: float | None = None,
    delta_suelo_a_pct: float | None = None,
    umbrales: UmbralesSaludBomba = UmbralesSaludBomba(),
) -> DiagnosticoMecanicoBomba:
    """Clasifica el estado mecánico de la bomba según el modo de verificación configurado."""
    if modo_verificacion is ModoVerificacionRiego.SIN_SENSOR_ACTUADOR:
        return DiagnosticoMecanicoBomba.SIN_TELEMETRIA

    if modo_verificacion is ModoVerificacionRiego.VIBRACION_RMS:
        if vibracion_rms_g is None:
            return DiagnosticoMecanicoBomba.SIN_TELEMETRIA
        if vibracion_rms_g < umbrales.vibracion_min_arranque_g:
            return DiagnosticoMecanicoBomba.FALLO_NO_ARRANCO
        if vibracion_rms_g > umbrales.vibracion_max_nominal_g:
            return DiagnosticoMecanicoBomba.SOBRECARGA_MECANICA
        if (
            vibracion_freq_hz is not None
            and vibracion_freq_hz >= umbrales.frecuencia_cavitacion_hz
        ) or (caudal_lpm is not None and caudal_lpm < umbrales.caudal_min_operativo_lpm):
            return DiagnosticoMecanicoBomba.CAVITACION_O_VACIO
        return DiagnosticoMecanicoBomba.NOMINAL

    if modo_verificacion is ModoVerificacionRiego.CORRIENTE_O_CAUDAL:
        if corriente_a is None and caudal_lpm is None:
            return DiagnosticoMecanicoBomba.SIN_TELEMETRIA
        if corriente_a is not None:
            if corriente_a < umbrales.corriente_min_arranque_a:
                return DiagnosticoMecanicoBomba.FALLO_NO_ARRANCO
            if corriente_a > umbrales.corriente_max_nominal_a:
                return DiagnosticoMecanicoBomba.SOBRECARGA_MECANICA
            if caudal_lpm is not None and caudal_lpm < umbrales.caudal_min_operativo_lpm:
                return DiagnosticoMecanicoBomba.CAVITACION_O_VACIO
            return DiagnosticoMecanicoBomba.NOMINAL
        return (
            DiagnosticoMecanicoBomba.NOMINAL
            if (caudal_lpm or 0.0) >= umbrales.caudal_min_operativo_lpm
            else DiagnosticoMecanicoBomba.FALLO_NO_ARRANCO
        )

    # Modo IMPACTO_SUELO_DIFERIDO: deduce si hubo entrega real de agua a partir de suelo_a
    if delta_suelo_a_pct is None:
        return DiagnosticoMecanicoBomba.SIN_TELEMETRIA
    if delta_suelo_a_pct < 2.0:
        return DiagnosticoMecanicoBomba.FALLO_NO_ARRANCO
    return DiagnosticoMecanicoBomba.NOMINAL


def evaluar_incidencia_riego(
    humedad_a_antes: float,
    humedad_a_despues: float,
    *,
    humedad_b_antes: float | None = None,
    humedad_b_despues: float | None = None,
) -> ResultadoIncidenciaRiego:
    r"""Evalúa el efecto real de un evento de riego sobre los Horizontes A y B ($\Delta\theta_A, \Delta\theta_B$)."""
    delta_a = round(float(humedad_a_despues) - float(humedad_a_antes), 2)
    delta_b = (
        round(float(humedad_b_despues) - float(humedad_b_antes), 2)
        if humedad_b_antes is not None and humedad_b_despues is not None
        else None
    )

    if delta_a < 2.0:
        return ResultadoIncidenciaRiego(
            delta_a_pct=delta_a,
            delta_b_pct=delta_b,
            efectividad=EfectividadRiego.SIN_RESPUESTA_EN_SUELO,
            observaciones=(
                f"Incremento nulo o marginal en Horizonte A (Δθ_A = {delta_a:+.1f}%). "
                "Verificar si la válvula abrió, si hay obstrucción o si el caudal no llegó al bulbo radicular."
            ),
        )

    if delta_b is not None and delta_b >= 8.0 and delta_b > (0.6 * delta_a):
        return ResultadoIncidenciaRiego(
            delta_a_pct=delta_a,
            delta_b_pct=delta_b,
            efectividad=EfectividadRiego.EXCESO_PERCOLACION,
            observaciones=(
                f"Percolación profunda elevada (Δθ_A = {delta_a:+.1f}%, Δθ_B = {delta_b:+.1f}%). "
                "Se recomienda fraccionar el volumen de riego o reducir la apertura máxima."
            ),
        )

    if delta_a < 5.0:
        return ResultadoIncidenciaRiego(
            delta_a_pct=delta_a,
            delta_b_pct=delta_b,
            efectividad=EfectividadRiego.INFILTRACION_PARCIAL,
            observaciones=(
                f"Humedecimiento superficial moderado (Δθ_A = {delta_a:+.1f}%). "
                "El pulso humedeció parcialmente la zona radicular."
            ),
        )

    obs_b = f", Δθ_B = {delta_b:+.1f}%" if delta_b is not None else ""
    return ResultadoIncidenciaRiego(
        delta_a_pct=delta_a,
        delta_b_pct=delta_b,
        efectividad=EfectividadRiego.EFECTIVO,
        observaciones=(
            f"Infiltración efectiva en zona radicular activa (Δθ_A = {delta_a:+.1f}%{obs_b}) "
            "sin pérdida excesiva por drenaje profundo."
        ),
    )
