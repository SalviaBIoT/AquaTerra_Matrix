"""Paquete de infraestructura meteorológica (Open-Meteo)."""

from aquaterra.infrastructure.clima.open_meteo_client import (
    ALTITUD_UTP_PEREIRA_M,
    LATITUD_UTP_PEREIRA,
    LONGITUD_UTP_PEREIRA,
    ClienteOpenMeteo,
    ResultadoSyncClima,
    parsear_respuesta_open_meteo,
)

__all__ = [
    "ALTITUD_UTP_PEREIRA_M",
    "LATITUD_UTP_PEREIRA",
    "LONGITUD_UTP_PEREIRA",
    "ClienteOpenMeteo",
    "ResultadoSyncClima",
    "parsear_respuesta_open_meteo",
]
