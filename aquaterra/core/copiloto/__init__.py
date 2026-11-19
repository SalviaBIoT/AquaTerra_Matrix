"""Paquete de dominio del Copiloto de Calibración, Guardarraíles Físicos y Contratos IA."""

from aquaterra.core.copiloto.asesor_reglas import AsesorDeterministaCopiloto
from aquaterra.core.copiloto.contratos_ia import (
    ESQUEMA_JSON_RESPUESTA_COPILOTO,
    ContextoDiagnosticoCopiloto,
    PropuestaCopiloto,
    construir_prompt_contexto_copiloto,
    construir_system_instruction_salviabiot,
    construir_system_instruction_terrabit,
)
from aquaterra.core.copiloto.cotas_calibracion import (
    CATALOGO_COTAS_CALIBRACION,
    PARAMETROS_CALIBRACION_POR_DEFECTO,
    CotaParametro,
    RecorteParametro,
    ResultadoAuditoriaCalibracion,
    auditar_y_acotar_ajustes,
)

__all__ = [
    "CATALOGO_COTAS_CALIBRACION",
    "ESQUEMA_JSON_RESPUESTA_COPILOTO",
    "PARAMETROS_CALIBRACION_POR_DEFECTO",
    "AsesorDeterministaCopiloto",
    "ContextoDiagnosticoCopiloto",
    "CotaParametro",
    "PropuestaCopiloto",
    "RecorteParametro",
    "ResultadoAuditoriaCalibracion",
    "auditar_y_acotar_ajustes",
    "construir_prompt_contexto_copiloto",
    "construir_system_instruction_salviabiot",
    "construir_system_instruction_terrabit",
]
