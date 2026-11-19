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
    panorama_ecosistema: tuple[dict[str, Any], ...] = ()
    ultimos_turnos: tuple[dict[str, str], ...] = ()
    clima_pronostico: dict[str, Any] | None = None
    fecha_hora_local: str | None = None
    parcelas_relacionadas: tuple[dict[str, Any], ...] = ()


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
                "Respuesta principal de Mandarino en español claro. Si el usuario hace una "
                "consulta técnica o diagnóstica, describe con rigor lo ocurrido citando "
                "variables medidas reales. Si solo saluda o conversa ('Hola', 'Quién eres'), "
                "responde con calidez en primera persona como Mandarino y resume en 1 frase "
                "el estado vivo de la estación si aporta contexto."
            ),
        },
        "justificacion_agronomica": {
            "type": "string",
            "description": (
                "Explicación física y agronómica de por qué se sugieren o no ajustes de calibración. "
                "Déjalo como cadena vacía \"\" si el usuario solo saludó o conversó sin pedir "
                "análisis técnico ni cambios."
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


def construir_system_instruction_salviabiot() -> str:
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
        "Te llamas **Mandarino**: eres el Copiloto de Inteligencia Ambiental, Ingeniería Agronómica, "
        "Bio-IoT y Metrología del Ecosistema **SalviaBIoT** (Biological Internet of Things). "
        "Tu personalidad es cercana, clara, futurista y colaborativa; "
        "asistes al investigador, guardabosques o productor en el monitoreo y diagnóstico de "
        "estaciones ESP32/ESP32-S3 (**TerraBit Station · Nodo INTI**, **InBeersa Melipona**, "
        "**Sigatoka Plátano** y **Conservación Páramo Polylepis**) y en calibraciones seguras.\n\n"
        "REGLAS INNEGOCIABLES:\n"
        "1. Responde SIEMPRE en español natural y en PRIMERA PERSONA ('Hola, soy Mandarino...', "
        "'Te sugiero...'), únicamente en formato JSON válido que cumpla el esquema. PROHIBIDO "
        "hablar del usuario en tercera persona ('el operador realizó un saludo', 'el usuario').\n"
        "2. MODO CONVERSACIONAL NATURAL: Si el usuario saluda ('Hola', 'Buenos días', 'Qué tal'), "
        "agradece o pregunta qué puedes hacer, respóndele con cercanía como Mandarino en "
        "`diagnostico_tecnico` (preséntate brevemente, menciona en 1 frase si hay una novedad "
        "puntual y ofrece ayudar). En charla casual deja `justificacion_agronomica` en \"\" y "
        "`ajustes_propuestos` en `{}`.\n"
        "3. CONTINUIDAD DE HILO Y ANTI-REPETICIÓN: Lee `historial_hilo_actual` antes de contestar. "
        "Si el usuario hace seguimiento ('¿qué sugerencias me das?', '¿cómo lo soluciono?', "
        "'¿al respecto?'), responde DIRECTAMENTE a esa pregunta con pasos prácticos de campo, "
        "hardware o manejo agronómico SIN volver a recitar el mismo reporte numérico del turno previo.\n"
        "4. FORMATO ENRIQUECIDO Y RIGOR TÉCNICO: Puedes usar Markdown limpio (listas con viñetas, "
        "**negritas** para cifras clave y tablas breves al comparar cotas) dentro de `diagnostico_tecnico`. "
        "Nunca inventes lecturas que no estén en el contexto. Si el payload indica `modo: 'charla_ligera'`, "
        "mantén `ajustes_propuestos` OBLIGATORIAMENTE como `{}`.\n"
        "5. CONSCIENCIA METEOROLÓGICA EN TIEMPO REAL: Si el contexto incluye "
        "`clima_actual_y_pronostico` (proveniente de Open-Meteo para las coordenadas reales de la "
        "estación), TIENES acceso directo al clima exterior y pronóstico horario. Úsalo con cifras "
        "exactas (temperatura exterior, humedad relativa, probabilidad/acumulado de lluvia, viento y "
        "$ET_0$) cruzándolo con el microclima medido por los sensores ESP32/ESP32-S3 cuando el usuario "
        "pregunte por el clima, lluvia o condiciones del día. Nunca digas que careces de datos del clima "
        "si ese bloque está presente.\n"
        "6. VISIÓN GLOBAL Y SEGMENTACIÓN: Estás conversando en el hilo seleccionado (puede ser "
        "una estación puntual o la charla general del ecosistema). Si `panorama_global_estaciones` "
        "está presente, úsalo con criterio proactivo sin mezclar hilos.\n"
        "7. Si propones cambios en `ajustes_propuestos`, usa EXCLUSIVAMENTE estas claves oficiales "
        "y respeta sus cotas físicas y paso máximo por iteración:\n"
        f"{catalogo_txt}\n"
        "8. Si no hace falta recalibrar, devuelve `ajustes_propuestos` como `{}`."
    )


# Alias retrocompatible para integraciones existentes
construir_system_instruction_terrabit = construir_system_instruction_salviabiot


def es_consulta_ligera(mensaje: str) -> bool:
    """Detecta saludos o charla sin intención explícita de recalibrar ni consultar clima/técnica."""
    txt = mensaje.lower().strip()
    claves_tecnicas = (
        "calibr",
        "umbral",
        "lamina",
        "lámina",
        "adc",
        "audita",
        "recalibr",
        "riego",
        "regar",
        "satur",
        "vpd",
        "suelo",
        "humedad",
        "temperatura",
        "nido",
        "alerta",
        "anomal",
        "analiz",
        "diagnost",
        "reporte",
        "estado",
        "pulso",
        "lluvia",
        "llover",
        "clima",
        "pronost",
        "pronóst",
        "meteor",
        "viento",
        "et0",
        "calor",
        "frio",
        "frío",
        "estrés",
        "estres",
        "sugerencia",
        "pasos",
        "variables",
    )
    if any(tok in txt for tok in claves_tecnicas):
        return False
    return len(txt) <= 120


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

    if es_consulta_ligera(ctx.mensaje_usuario):
        clima_ligero = None
        if isinstance(ctx.clima_pronostico, dict):
            clima_ligero = {
                "ubicacion": ctx.clima_pronostico.get("ubicacion"),
                "ahora": ctx.clima_pronostico.get("ahora"),
                "resumen_24h": ctx.clima_pronostico.get("resumen_24h"),
            }
        payload = {
            "modo": "charla_ligera",
            "fecha_hora_local": ctx.fecha_hora_local,
            "regla": (
                "El usuario está saludando o conversando sin pedir calibración ni cambios. "
                "Responde en primera persona con cercanía y brevedad; devuelve "
                "ajustes_propuestos = {} y justificacion_agronomica = ''."
            ),
            "consulta_operador": ctx.mensaje_usuario,
            "historial_hilo_actual": list(ctx.ultimos_turnos),
            "estacion_actual_resumen": (
                {
                    "nombre": resumen_dict["nombre_estacion"],
                    "severidad": resumen_dict["severidad"],
                    "alertas": resumen_dict["alertas_detectadas"][:2],
                }
                if resumen_dict
                else None
            ),
            "clima_actual_y_pronostico": clima_ligero,
            "panorama_global_estaciones": list(ctx.panorama_ecosistema),
        }
    else:
        payload = {
            "modo": "analisis_tecnico",
            "fecha_hora_local": ctx.fecha_hora_local,
            "consulta_operador": ctx.mensaje_usuario,
            "historial_hilo_actual": list(ctx.ultimos_turnos),
            "version_calibracion_activa": ctx.version_calibracion_actual,
            "parametros_calibracion_actuales": ctx.parametros_actuales,
            "pulso_estacion_24h": resumen_dict,
            "clima_actual_y_pronostico": ctx.clima_pronostico,
            "parcela_asociada": parcela_dict,
            "parcelas_vinculadas": list(ctx.parcelas_relacionadas),
            "ultima_incidencia_riego": incidencia_dict,
            "candados_seguridad_activos": list(ctx.candados_activos),
            "panorama_global_estaciones": list(ctx.panorama_ecosistema),
        }
    return (
        "Analiza el siguiente contexto operativo y responde en JSON válido:\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )
