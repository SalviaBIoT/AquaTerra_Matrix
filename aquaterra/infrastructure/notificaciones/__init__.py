"""Paquete de notificaciones externas (Webhook n8n / WhatsApp y Telegram Bot directo)."""

from aquaterra.infrastructure.notificaciones.mensajeria import (
    DespachadorNotificaciones,
    ResultadoEnvioNotificacion,
)

__all__ = [
    "DespachadorNotificaciones",
    "ResultadoEnvioNotificacion",
]
