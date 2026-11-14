"""Contratos de datos, esquemas JSON y constructores de prompts para el Copiloto IA.

Garantiza que tanto el motor determinista local (`RuleBasedAdvisor`) como los
proveedores generativos (`Gemini AI Studio` y `Ollama Local`) reciban el mismo
contexto matemático extraído de SQLite y devuelvan una estructura idéntica y
auditable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from aquaterra.core.analitica.pulso import ResumenPulso24h
from aquaterra.core.copiloto.cotas_calibracion import CATALOGO_COTAS_CALIBRACION
from aquaterra.core.domain.entidades import IncidenciaRiego, Parcela


@dataclass(frozen=True, slots=True)
class ContextoDiagnosticoCopiloto:
    """Fotografía matemática e histórica inyectada al Copiloto en cada consulta."""

    mensaje_usuario: str
    parametros_actuales: dict[str, float | int | str | bool]
    version_calibracion_actual: int = 0
    resumen_pulso: ResumenPulso24h | None = None
    parcela: Parcela | None = None
    ultima_incidencia_riego: IncidenciaRiego | None = None
    candados_activos: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PropuestaCopiloto:
    """Respuesta estructurada de diagnóstico y recalibración antes/después de auditoría."""

    diagnostico_tecnico: str
    justificacion_agronomica: str
    ajustes_propuestos: dict[str, float] = field(default_factory=dict)
    confianza: float = 0.85
    alertas_consideradas: tuple[str, ...] = ()
    proveedor_ia: str = "local_reglas"


# Esquema JSON estricto compatible con Gemini Interactions API (`response_format`) y Ollama (`format`).
ESQUEMA_JSON_RESPUESTA_COPILOTO: dict[str, Any] = {
    "type": "object",
    "properties": {
        "diagnostico_tecnico": {
            "type": "string",
            "description": (
                "Diagnóstico directo en español técnico sobre lo ocurrido en la estación o parcela, "
                "citando las variables medidas (humedad, VPD, delta post-riego, ADC, temperatura)."
            ),
        },
        "justificacion_agronomica": {
            "type": "string",
            "description": (
                "Explicación física y agronómica de por qué se sugieren o no ajustes de calibración."
            ),
        },
        "ajustes_propuestos": {
            "type": "object",
            "description": (
                "Diccionario opcional de parámetros a recalibrar (solo claves del catálogo oficial "
                "cuando la evidencia o solicitud del usuario lo justifique)."
            ),
            "properties": {
                clave: {
                    "type": "number",
                    "description": (
                        f"{cota.descripcion} Rango permitido: [{cota.minimo}, {cota.maximo}] {cota.unidad}. "
                        f"Cambio máximo por paso: ±{cota.delta_max_por_paso} {cota.unidad}."
                    ),
                }
                for clave, cota in CATALOGO_COTAS_CALIBRACION.items()
            },
        },
        "confianza": {
            "type": "number",
            "description": "Nivel de confianza del diagnóstico entre 0.0 y 1.0.",
        },
        "alertas_consideradas": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Lista breve de alertas o factores críticos tomados en cuenta.",
        },
    },
    "required": [
        "diagnostico_tecnico",
        "justificacion_agronomica",
        "ajustes_propuestos",
        "confianza",
        "alertas_consideradas",
    ],
}


def construir_system_instruction_terrabit() -> str:
    """Construye la instrucción maestra del sistema para Gemini AI Studio y Ollama."""
    lineas_cotas = [
        (
            f"- {c.clave}: [{c.minimo}, {c.maximo}] {c.unidad} "
            f"(paso máx ±{c.delta_max_por_paso}, defecto {c.valor_por_defecto}) -> {c.descripcion}"
        )
        for c in CATALOGO_COTAS_CALIBRACION.values()
    ]
    catalogo_txt = "\n".join(lineas_cotas)
    return (
        "Eres el Copiloto de Ingeniería Agronómica, Bio-IoT y Metrología del Ecosistema TerraBit "
        "(AquaTerra Matrix v4.1). Tu rol es asistir al ingeniero o productor en el diagnóstico de "
        "estaciones ESP32/ESP32-S3 (Nodo INTI, InBeersa Melipona, Sigatoka Plátano y Conservación "
        "Páramo Polylepis) y proponer ajustes seguros de calibración.\n\n"
        "REGLAS INNEGOCIABLES:\n"
        "1. Responde SIEMPRE en español técnico, claro y riguroso, únicamente en formato JSON "
        "que cumpla el esquema solicitado.\n"
        "2. Nunca inventes lecturas de sensores que no estén en el bloque de contexto.\n"
        "3. Si propones cambios en `ajustes_propuestos`, usa EXCLUSIVAMENTE las siguientes claves "
        "y respeta sus cotas físicas y paso máximo por iteración:\n"
        f"{catalogo_txt}\n"
        "4. Si el usuario solo pide un resumen o consulta informativa sin requerir recalibración, "
        "devuelve `ajustes_propuestos` como un objeto vacío `{}`."
    )


def construir_prompt_contexto_copiloto(ctx: ContextoDiagnosticoCopiloto) -> str:
    """Empaqueta el contexto SQLite en un payload JSON legible para el modelo generativo."""
    resumen_dict: dict[str, Any] | None = None
    if ctx.resumen_pulso is not None:
        p = ctx.resumen_pulso
        resumen_dict = {
            "estacion_id": p.estacion_id,
            "codigo_estacion": p.codigo_estacion,
            "nombre_estacion": p.nombre_estacion,
            "tipo_estacion": p.tipo_estacion.value,
            "severidad": p.severidad.value,
            "diagnostico_determinista": p.diagnostico_determinista,
            "alertas_detectadas": list(p.alertas_detectadas),
            "ultimos_valores": {
                var: round(est.ultimo_valor, 3) for var, est in p.variables.items()
            },
        }

    parcela_dict: dict[str, Any] | None = None
    if ctx.parcela is not None:
        parcela_dict = {
            "id": ctx.parcela.id,
            "nombre": ctx.parcela.nombre,
            "cultivo": ctx.parcela.cultivo,
            "tipo_suelo": ctx.parcela.tipo_suelo.value,
            "area_m2": ctx.parcela.area_m2,
            "humedad_pct": ctx.parcela.humedad_pct,
        }

    incidencia_dict: dict[str, Any] | None = None
    if ctx.ultima_incidencia_riego is not None:
        inc = ctx.ultima_incidencia_riego
        incidencia_dict = {
            "evento_riego_id": inc.evento_riego_id,
            "humedad_a_antes": inc.humedad_a_antes,
            "humedad_a_despues": inc.humedad_a_despues,
            "delta_a_pct": inc.delta_a_pct,
            "delta_b_pct": inc.delta_b_pct,
            "efectividad": inc.efectividad.value,
            "observaciones": inc.observaciones,
        }

    payload = {
        "consulta_operador": ctx.mensaje_usuario,
        "version_calibracion_activa": ctx.version_calibracion_actual,
        "parametros_calibracion_actuales": ctx.parametros_actuales,
        "pulso_estacion_24h": resumen_dict,
        "parcela_asociada": parcela_dict,
        "ultima_incidencia_riego": incidencia_dict,
        "candados_seguridad_activos": list(ctx.candados_activos),
    }
    return (
        "Analiza el siguiente contexto operativo de la estación/parcela y responde en JSON:\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )
