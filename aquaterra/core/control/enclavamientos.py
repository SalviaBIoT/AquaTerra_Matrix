r"""Motor de Enclavamientos Duros de Seguridad (``SafetyInterlockEngine`` — Dominio Puro, Cero I/O).

Evalúa los 5 candados deterministas definidos en la Brújula Maestra antes de autorizar
cualquier apertura de válvula o programación de riego:
1. ``CANDADO_LLUVIA_ACTIVA``: Bloquea bajo lluvia fuerte o recorta apertura máxima bajo llovizna/pronóstico alto.
2. ``CANDADO_SATURACION``: Impide regar si la humedad iguala o supera la Capacidad de Campo ($\theta_{CC}$).
3. ``CANDADO_VOLUMEN_MAXIMO``: Acota los litros máximos por aplicación según el área y la textura USDA.
4. ``CANDADO_ENERGIA_NODO``: Impide conmutar actuadores si la tensión de batería del nodo es crítica.
5. ``CANDADO_SALUD_BOMBA``: Si existe sensor en bomba y el último ciclo reportó falla mecánica no atendida,
   bloquea el arranque. Cuando la estación opera sin bomba o sin sensor (``SIN_SENSOR_ACTUADOR``),
   este candado permanece transparente sin bloquear la operación.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from aquaterra.core.domain import DiagnosticoMecanicoBomba, ModoVerificacionRiego, TipoSuelo

# Capacidad de campo referencial (%) en escala de humedad relativa del sustrato por textura
CAPACIDAD_CAMPO_POR_SUELO: dict[TipoSuelo, float] = {
    TipoSuelo.ARENOSO: 70.0,
    TipoSuelo.FRANCO: 80.0,
    TipoSuelo.ARCILLOSO: 85.0,
}

# Lámina máxima segura por pulso de riego (L / m²) para evitar escorrentía y lixiviación
LAMINA_MAX_L_M2_POR_SUELO: dict[TipoSuelo, float] = {
    TipoSuelo.ARENOSO: 4.5,
    TipoSuelo.FRANCO: 6.0,
    TipoSuelo.ARCILLOSO: 5.0,
}


class CodigoCandado(StrEnum):
    CANDADO_LLUVIA_ACTIVA = "candado_lluvia_activa"
    CANDADO_SATURACION = "candado_saturacion"
    CANDADO_VOLUMEN_MAXIMO = "candado_volumen_maximo"
    CANDADO_ENERGIA_NODO = "candado_energia_nodo"
    CANDADO_SALUD_BOMBA = "candado_salud_bomba"


@dataclass(frozen=True, slots=True)
class EstadoCandado:
    codigo: CodigoCandado
    superado: bool
    recorte_aplicado: bool
    detalle: str


@dataclass(frozen=True, slots=True)
class ContextoSeguridadRiego:
    area_m2: float
    tipo_suelo: TipoSuelo
    humedad_actual_pct: float
    litros_solicitados: float
    apertura_solicitada_pct: float = 100.0
    capacidad_campo_pct: float | None = None
    lamina_max_l_m2: float | None = None
    lluvia_actual_mm_min: float = 0.0
    lluvia_pronosticada_24h_mm: float = 0.0
    prob_lluvia_24h_pct: float = 0.0
    voltaje_nodo_v: float | None = None
    voltaje_minimo_v: float = 3.45
    modo_verificacion: ModoVerificacionRiego = ModoVerificacionRiego.SIN_SENSOR_ACTUADOR
    ultimo_diagnostico_bomba: DiagnosticoMecanicoBomba | None = None
    mantenimiento_confirmado: bool = False


@dataclass(frozen=True, slots=True)
class VeredictoEnclavamientos:
    autorizado: bool
    litros_autorizados: float
    apertura_autorizada_pct: float
    candados: tuple[EstadoCandado, ...]
    motivos_bloqueo: tuple[str, ...]
    advertencias_recorte: tuple[str, ...]


class SafetyInterlockEngine:
    """Validador determinista de los 5 candados físicos y agronómicos de riego."""

    @staticmethod
    def evaluar(ctx: ContextoSeguridadRiego) -> VeredictoEnclavamientos:
        candados: list[EstadoCandado] = []
        bloqueos: list[str] = []
        recortes: list[str] = []

        litros_aut = max(0.0, float(ctx.litros_solicitados))
        apertura_aut = min(100.0, max(0.0, float(ctx.apertura_solicitada_pct)))

        # 1. CANDADO_LLUVIA_ACTIVA
        if ctx.lluvia_actual_mm_min >= 0.15 or ctx.lluvia_pronosticada_24h_mm >= 10.0:
            msg = (
                f"Precipitación activa ({ctx.lluvia_actual_mm_min:.2f} mm/min) o pronóstico "
                f"alto ({ctx.lluvia_pronosticada_24h_mm:.1f} mm en 24h): riego bloqueado."
            )
            candados.append(EstadoCandado(CodigoCandado.CANDADO_LLUVIA_ACTIVA, False, False, msg))
            bloqueos.append(msg)
            apertura_aut = 0.0
        elif (
            ctx.lluvia_actual_mm_min > 0.0
            or ctx.lluvia_pronosticada_24h_mm >= 4.0
            or ctx.prob_lluvia_24h_pct >= 75.0
        ):
            apertura_aut = min(apertura_aut, 50.0)
            msg = (
                f"Llovizna o probabilidad de lluvia ({ctx.prob_lluvia_24h_pct:.0f}%, "
                f"{ctx.lluvia_pronosticada_24h_mm:.1f} mm): apertura limitada al {apertura_aut:.0f}%."
            )
            candados.append(EstadoCandado(CodigoCandado.CANDADO_LLUVIA_ACTIVA, True, True, msg))
            recortes.append(msg)
        else:
            candados.append(
                EstadoCandado(
                    CodigoCandado.CANDADO_LLUVIA_ACTIVA,
                    True,
                    False,
                    "Sin lluvia activa ni pronóstico restrictivo.",
                )
            )

        # 2. CANDADO_SATURACION
        cc_pct = (
            ctx.capacidad_campo_pct
            if ctx.capacidad_campo_pct is not None
            else CAPACIDAD_CAMPO_POR_SUELO[ctx.tipo_suelo]
        )
        if ctx.humedad_actual_pct >= cc_pct:
            msg = (
                f"Suelo en o sobre Capacidad de Campo ({ctx.humedad_actual_pct:.1f}% >= "
                f"{cc_pct:.1f}% para suelo {ctx.tipo_suelo.value}): riesgo de asfixia radicular."
            )
            candados.append(EstadoCandado(CodigoCandado.CANDADO_SATURACION, False, False, msg))
            bloqueos.append(msg)
        else:
            candados.append(
                EstadoCandado(
                    CodigoCandado.CANDADO_SATURACION,
                    True,
                    False,
                    f"Humedad actual ({ctx.humedad_actual_pct:.1f}%) bajo Capacidad de Campo ({cc_pct:.1f}%).",
                )
            )

        # 3. CANDADO_VOLUMEN_MAXIMO
        lamina_max = (
            ctx.lamina_max_l_m2
            if ctx.lamina_max_l_m2 is not None
            else LAMINA_MAX_L_M2_POR_SUELO[ctx.tipo_suelo]
        )
        litros_max = round(ctx.area_m2 * lamina_max, 2)
        if litros_aut > litros_max:
            msg = (
                f"Volumen solicitado ({litros_aut:.1f} L) excede cota segura para {ctx.area_m2:.1f} m² "
                f"({lamina_max:.1f} L/m²): recortado a {litros_max:.1f} L."
            )
            litros_aut = litros_max
            candados.append(EstadoCandado(CodigoCandado.CANDADO_VOLUMEN_MAXIMO, True, True, msg))
            recortes.append(msg)
        else:
            candados.append(
                EstadoCandado(
                    CodigoCandado.CANDADO_VOLUMEN_MAXIMO,
                    True,
                    False,
                    f"Volumen ({litros_aut:.1f} L) dentro del tope seguro ({litros_max:.1f} L).",
                )
            )

        # 4. CANDADO_ENERGIA_NODO
        if ctx.voltaje_nodo_v is not None and ctx.voltaje_nodo_v < ctx.voltaje_minimo_v:
            msg = (
                f"Voltaje del nodo insuficiente ({ctx.voltaje_nodo_v:.2f} V < "
                f"{ctx.voltaje_minimo_v:.2f} V): riesgo de reinicio al accionar solenoide/relé."
            )
            candados.append(EstadoCandado(CodigoCandado.CANDADO_ENERGIA_NODO, False, False, msg))
            bloqueos.append(msg)
        else:
            detalle_v = (
                f"Energía del nodo nominal ({ctx.voltaje_nodo_v:.2f} V)."
                if ctx.voltaje_nodo_v is not None
                else "Sin restricción de batería reportada."
            )
            candados.append(EstadoCandado(CodigoCandado.CANDADO_ENERGIA_NODO, True, False, detalle_v))

        # 5. CANDADO_SALUD_BOMBA (Transparente cuando opera en SIN_SENSOR_ACTUADOR)
        fallos_criticos = {
            DiagnosticoMecanicoBomba.FALLO_NO_ARRANCO,
            DiagnosticoMecanicoBomba.CAVITACION_O_VACIO,
            DiagnosticoMecanicoBomba.SOBRECARGA_MECANICA,
        }
        if ctx.modo_verificacion is ModoVerificacionRiego.SIN_SENSOR_ACTUADOR:
            candados.append(
                EstadoCandado(
                    CodigoCandado.CANDADO_SALUD_BOMBA,
                    True,
                    False,
                    "Modo sin sensor de bomba activo (mando lógico / preparado para hardware futuro).",
                )
            )
        elif (
            ctx.ultimo_diagnostico_bomba in fallos_criticos
            and not ctx.mantenimiento_confirmado
        ):
            msg = (
                f"Bomba bloqueada preventivamente por diagnóstico previo "
                f"'{ctx.ultimo_diagnostico_bomba.value}' sin confirmación de mantenimiento."
            )
            candados.append(EstadoCandado(CodigoCandado.CANDADO_SALUD_BOMBA, False, False, msg))
            bloqueos.append(msg)
        else:
            candados.append(
                EstadoCandado(
                    CodigoCandado.CANDADO_SALUD_BOMBA,
                    True,
                    False,
                    "Salud hidromecánica de actuador verificada.",
                )
            )

        autorizado = len(bloqueos) == 0
        if not autorizado:
            litros_aut = 0.0
            apertura_aut = 0.0

        return VeredictoEnclavamientos(
            autorizado=autorizado,
            litros_autorizados=round(litros_aut, 2),
            apertura_autorizada_pct=round(apertura_aut, 1),
            candados=tuple(candados),
            motivos_bloqueo=tuple(bloqueos),
            advertencias_recorte=tuple(recortes),
        )
