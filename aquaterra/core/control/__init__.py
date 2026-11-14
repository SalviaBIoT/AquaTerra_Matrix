"""Paquete de control determinista: enclavamientos de seguridad, salud de bomba y planificación proactiva."""

from aquaterra.core.control.actuadores import (
    ResultadoIncidenciaRiego,
    UmbralesSaludBomba,
    diagnosticar_salud_bomba,
    evaluar_incidencia_riego,
)
from aquaterra.core.control.enclavamientos import (
    CAPACIDAD_CAMPO_POR_SUELO,
    LAMINA_MAX_L_M2_POR_SUELO,
    CodigoCandado,
    ContextoSeguridadRiego,
    EstadoCandado,
    SafetyInterlockEngine,
    VeredictoEnclavamientos,
)
from aquaterra.core.control.planificador import (
    AccionRecomendadaRiego,
    RecomendacionRiego,
    calcular_litros_reposicion,
    generar_recomendacion_proactiva,
)

__all__ = [
    "CAPACIDAD_CAMPO_POR_SUELO",
    "LAMINA_MAX_L_M2_POR_SUELO",
    "AccionRecomendadaRiego",
    "CodigoCandado",
    "ContextoSeguridadRiego",
    "EstadoCandado",
    "RecomendacionRiego",
    "ResultadoIncidenciaRiego",
    "SafetyInterlockEngine",
    "UmbralesSaludBomba",
    "VeredictoEnclavamientos",
    "calcular_litros_reposicion",
    "diagnosticar_salud_bomba",
    "evaluar_incidencia_riego",
    "generar_recomendacion_proactiva",
]
