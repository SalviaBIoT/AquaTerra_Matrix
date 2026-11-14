r"""Planificador Proactivo de Riego (Dominio Puro — Cero I/O).

Cruza:
1. Estado actual de humedad del sustrato ($\theta_A$) y su umbral de disparo.
2. Tasa de secado edáfico ($\Delta\theta_A / \Delta t$) y horas restantes hasta estrés ($t_{\text{crit}}$).
3. Pronóstico meteorológico de las próximas 24 horas (lluvia esperada y probabilidad).
4. Veredicto determinista del ``SafetyInterlockEngine``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from aquaterra.core.analitica.series import tiempo_hasta_umbral_horas
from aquaterra.core.control.enclavamientos import (
    CAPACIDAD_CAMPO_POR_SUELO,
    ContextoSeguridadRiego,
    SafetyInterlockEngine,
    VeredictoEnclavamientos,
)
from aquaterra.core.domain import DiagnosticoMecanicoBomba, ModoVerificacionRiego, TipoSuelo


class AccionRecomendadaRiego(StrEnum):
    NO_REGAR_HUMEDAD_SUFICIENTE = "no_regar_humedad_suficiente"
    POSPONER_POR_LLUVIA = "posponer_por_lluvia"
    PROGRAMAR_PREVENTIVO = "programar_preventivo"
    REGAR_INMEDIATO = "regar_inmediato"
    BLOQUEADO_POR_SEGURIDAD = "bloqueado_por_seguridad"


@dataclass(frozen=True, slots=True)
class RecomendacionRiego:
    accion: AccionRecomendadaRiego
    regar: bool
    litros_sugeridos: float
    apertura_sugerida_pct: float
    humedad_actual_pct: float
    umbral_disparo_pct: float
    tasa_secado_pct_h: float | None
    horas_hasta_estres: float | None
    veredicto_seguridad: VeredictoEnclavamientos
    justificacion: str


def calcular_litros_reposicion(
    *,
    area_m2: float,
    humedad_actual_pct: float,
    objetivo_pct: float,
    factor_profundidad_l_m2_por_pct: float = 0.20,
) -> float:
    """Calcula los litros necesarios para elevar la humedad desde ``humedad_actual_pct`` hasta ``objetivo_pct``."""
    deficit_pct = max(0.0, objetivo_pct - humedad_actual_pct)
    if deficit_pct <= 0.0:
        return 0.0
    return round(max(1.0, area_m2 * deficit_pct * factor_profundidad_l_m2_por_pct), 2)


def generar_recomendacion_proactiva(
    *,
    area_m2: float,
    tipo_suelo: TipoSuelo,
    humedad_actual_pct: float,
    umbral_disparo_pct: float = 40.0,
    tasa_secado_pct_h: float | None = None,
    lluvia_actual_mm_min: float = 0.0,
    lluvia_pronosticada_24h_mm: float = 0.0,
    prob_lluvia_24h_pct: float = 0.0,
    voltaje_nodo_v: float | None = None,
    modo_verificacion: ModoVerificacionRiego = ModoVerificacionRiego.SIN_SENSOR_ACTUADOR,
    ultimo_diagnostico_bomba: DiagnosticoMecanicoBomba | None = None,
    capacidad_campo_pct: float | None = None,
    lamina_max_l_m2: float | None = None,
) -> RecomendacionRiego:
    """Genera una recomendación proactiva de riego validada por ``SafetyInterlockEngine``."""
    cc_pct = (
        capacidad_campo_pct
        if capacidad_campo_pct is not None
        else CAPACIDAD_CAMPO_POR_SUELO[tipo_suelo]
    )
    horas_crit = tiempo_hasta_umbral_horas(humedad_actual_pct, tasa_secado_pct_h, umbral_disparo_pct)

    # Estimación de volumen objetivo hacia el 85 % de la Capacidad de Campo
    objetivo_hidratacion = round(min(cc_pct * 0.90, max(umbral_disparo_pct + 15.0, cc_pct * 0.80)), 1)
    litros_brutos = calcular_litros_reposicion(
        area_m2=area_m2,
        humedad_actual_pct=humedad_actual_pct,
        objetivo_pct=objetivo_hidratacion,
    )

    veredicto = SafetyInterlockEngine.evaluar(
        ContextoSeguridadRiego(
            area_m2=area_m2,
            tipo_suelo=tipo_suelo,
            humedad_actual_pct=humedad_actual_pct,
            litros_solicitados=max(litros_brutos, 1.0),
            apertura_solicitada_pct=100.0,
            capacidad_campo_pct=cc_pct,
            lamina_max_l_m2=lamina_max_l_m2,
            lluvia_actual_mm_min=lluvia_actual_mm_min,
            lluvia_pronosticada_24h_mm=lluvia_pronosticada_24h_mm,
            prob_lluvia_24h_pct=prob_lluvia_24h_pct,
            voltaje_nodo_v=voltaje_nodo_v,
            modo_verificacion=modo_verificacion,
            ultimo_diagnostico_bomba=ultimo_diagnostico_bomba,
        )
    )

    requiere_agua_hoy = humedad_actual_pct < umbral_disparo_pct
    requiere_preventivo = (
        not requiere_agua_hoy
        and horas_crit is not None
        and horas_crit <= 18.0
    )

    # Si no requiere agua ni está próximo a cruzar el umbral
    if not requiere_agua_hoy and not requiere_preventivo:
        return RecomendacionRiego(
            accion=AccionRecomendadaRiego.NO_REGAR_HUMEDAD_SUFICIENTE,
            regar=False,
            litros_sugeridos=0.0,
            apertura_sugerida_pct=0.0,
            humedad_actual_pct=humedad_actual_pct,
            umbral_disparo_pct=umbral_disparo_pct,
            tasa_secado_pct_h=tasa_secado_pct_h,
            horas_hasta_estres=horas_crit,
            veredicto_seguridad=veredicto,
            justificacion=(
                f"Humedad adecuada ({humedad_actual_pct:.1f}% >= umbral {umbral_disparo_pct:.1f}%) "
                "sin tendencia de agotamiento crítico en las próximas 18 h."
            ),
        )

    # Si requiere agua o riego preventivo, pero viene lluvia significativa que suplirá la demanda
    if (
        lluvia_pronosticada_24h_mm >= 6.0
        and prob_lluvia_24h_pct >= 65.0
        and humedad_actual_pct >= (umbral_disparo_pct - 6.0)
    ):
        return RecomendacionRiego(
            accion=AccionRecomendadaRiego.POSPONER_POR_LLUVIA,
            regar=False,
            litros_sugeridos=0.0,
            apertura_sugerida_pct=0.0,
            humedad_actual_pct=humedad_actual_pct,
            umbral_disparo_pct=umbral_disparo_pct,
            tasa_secado_pct_h=tasa_secado_pct_h,
            horas_hasta_estres=horas_crit,
            veredicto_seguridad=veredicto,
            justificacion=(
                f"Se pospone el riego proactivamente: pronóstico de {lluvia_pronosticada_24h_mm:.1f} mm "
                f"(probabilidad {prob_lluvia_24h_pct:.0f}%) cubrirá la demanda hídrica próxima."
            ),
        )

    if not veredicto.autorizado:
        motivos = "; ".join(veredicto.motivos_bloqueo)
        return RecomendacionRiego(
            accion=AccionRecomendadaRiego.BLOQUEADO_POR_SEGURIDAD,
            regar=False,
            litros_sugeridos=0.0,
            apertura_sugerida_pct=0.0,
            humedad_actual_pct=humedad_actual_pct,
            umbral_disparo_pct=umbral_disparo_pct,
            tasa_secado_pct_h=tasa_secado_pct_h,
            horas_hasta_estres=horas_crit,
            veredicto_seguridad=veredicto,
            justificacion=f"Riego requerido pero bloqueado por enclavamiento de seguridad: {motivos}",
        )

    if requiere_agua_hoy:
        nota_recorte = (
            f" ({'; '.join(veredicto.advertencias_recorte)})"
            if veredicto.advertencias_recorte
            else ""
        )
        return RecomendacionRiego(
            accion=AccionRecomendadaRiego.REGAR_INMEDIATO,
            regar=True,
            litros_sugeridos=veredicto.litros_autorizados,
            apertura_sugerida_pct=veredicto.apertura_autorizada_pct,
            humedad_actual_pct=humedad_actual_pct,
            umbral_disparo_pct=umbral_disparo_pct,
            tasa_secado_pct_h=tasa_secado_pct_h,
            horas_hasta_estres=0.0,
            veredicto_seguridad=veredicto,
            justificacion=(
                f"Déficit hídrico activo ({humedad_actual_pct:.1f}% < {umbral_disparo_pct:.1f}%): "
                f"aplicar {veredicto.litros_autorizados:.1f} L con apertura al "
                f"{veredicto.apertura_autorizada_pct:.0f}%{nota_recorte}."
            ),
        )

    # Caso preventivo: aún está sobre el umbral pero la tasa de secado lo cruzará en <= 18 h
    return RecomendacionRiego(
        accion=AccionRecomendadaRiego.PROGRAMAR_PREVENTIVO,
        regar=True,
        litros_sugeridos=veredicto.litros_autorizados,
        apertura_sugerida_pct=veredicto.apertura_autorizada_pct,
        humedad_actual_pct=humedad_actual_pct,
        umbral_disparo_pct=umbral_disparo_pct,
        tasa_secado_pct_h=tasa_secado_pct_h,
        horas_hasta_estres=horas_crit,
        veredicto_seguridad=veredicto,
        justificacion=(
            f"Riego preventivo recomendado: a la tasa de secado actual ({tasa_secado_pct_h:+.2f} %/h), "
            f"la parcela alcanzará el umbral crítico en ~{horas_crit:.1f} h. "
            f"Programar {veredicto.litros_autorizados:.1f} L."
        ),
    )
