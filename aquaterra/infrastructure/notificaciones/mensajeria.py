"""Conectores de notificación externa: Webhook `n8n` (WhatsApp / Notion / Make) y Telegram Bot directo.

Diseñado para despachar el Resumen Ejecutivo del Pulso 24h o alertas críticas de
enclavamiento hacia el celular del ingeniero o del productor agrícola:
1. **Vía Directa (Cero Intermediarios, Costo $0):** API nativa de **Telegram Bot**
   (`AQUATERRA_TELEGRAM_BOT_TOKEN` + `AQUATERRA_TELEGRAM_CHAT_ID`).
2. **Vía Orquestador (`n8n` / `Make` -> WhatsApp / Telegram / Notion / Email):**
   Webhook HTTP POST JSON (`AQUATERRA_WEBHOOK_URL`) con el texto ya formateado y
   los metadatos estructurados de la estación.
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ResultadoEnvioNotificacion:
    """Estado del despacho hacia los canales externos configurados."""

    canal: str  # "telegram" | "webhook_n8n"
    enviado: bool
    detalle: str


class DespachadorNotificaciones:
    """Cliente HTTP ligero para Telegram Bot API y Webhooks de `n8n`."""

    def __init__(
        self,
        *,
        webhook_url: str | None = None,
        telegram_bot_token: str | None = None,
        telegram_chat_id: str | None = None,
        timeout_segundos: float = 10.0,
    ) -> None:
        self._webhook_url = (
            webhook_url or os.environ.get("AQUATERRA_WEBHOOK_URL") or ""
        ).strip()
        self._tg_token = (
            telegram_bot_token or os.environ.get("AQUATERRA_TELEGRAM_BOT_TOKEN") or ""
        ).strip()
        self._tg_chat_id = (
            telegram_chat_id or os.environ.get("AQUATERRA_TELEGRAM_CHAT_ID") or ""
        ).strip()
        self._timeout = timeout_segundos

    @property
    def canales_configurados(self) -> tuple[str, ...]:
        """Canales con credenciales completas (para las píldoras de estado de la consola v5.0)."""
        canales: list[str] = []
        if self._webhook_url:
            canales.append("n8n_webhook")
        if self._tg_token and self._tg_chat_id:
            canales.append("telegram")
        return tuple(canales)

    def enviar_webhook_n8n(
        self,
        *,
        evento: str,
        mensaje_ejecutivo: str,
        metadatos: dict[str, Any] | None = None,
    ) -> ResultadoEnvioNotificacion:
        """Envía un payload JSON estructurado a un nodo Webhook de `n8n` (para WhatsApp/Notion)."""
        if not self._webhook_url:
            return ResultadoEnvioNotificacion(
                canal="webhook_n8n",
                enviado=False,
                detalle="AQUATERRA_WEBHOOK_URL no configurado.",
            )

        payload = {
            "origen": "SalviaBIoT_v6.0",
            "evento": evento,
            "mensaje_whatsapp_telegram": mensaje_ejecutivo,
            "metadatos": metadatos or {},
        }
        req = urllib.request.Request(
            self._webhook_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return ResultadoEnvioNotificacion(
                    canal="webhook_n8n",
                    enviado=200 <= resp.status < 300,
                    detalle=f"HTTP {resp.status}",
                )
        except Exception as exc:
            return ResultadoEnvioNotificacion(
                canal="webhook_n8n",
                enviado=False,
                detalle=str(exc),
            )

    def enviar_telegram_directo(self, mensaje_ejecutivo: str) -> ResultadoEnvioNotificacion:
        """Envía el reporte directamente a un chat o grupo de Telegram sin intermediarios."""
        if not self._tg_token or not self._tg_chat_id:
            return ResultadoEnvioNotificacion(
                canal="telegram",
                enviado=False,
                detalle="AQUATERRA_TELEGRAM_BOT_TOKEN o AQUATERRA_TELEGRAM_CHAT_ID no configurados.",
            )

        url = f"https://api.telegram.org/bot{self._tg_token}/sendMessage"
        payload = {
            "chat_id": self._tg_chat_id,
            "text": mensaje_ejecutivo,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return ResultadoEnvioNotificacion(
                    canal="telegram",
                    enviado=200 <= resp.status < 300,
                    detalle=f"HTTP {resp.status}",
                )
        except Exception as exc:
            return ResultadoEnvioNotificacion(
                canal="telegram",
                enviado=False,
                detalle=str(exc),
            )

    def despachar_todos(
        self,
        *,
        evento: str,
        mensaje_ejecutivo: str,
        metadatos: dict[str, Any] | None = None,
    ) -> list[ResultadoEnvioNotificacion]:
        """Despacha a todos los canales externos que estén configurados."""
        resultados: list[ResultadoEnvioNotificacion] = []
        if self._webhook_url:
            resultados.append(
                self.enviar_webhook_n8n(
                    evento=evento,
                    mensaje_ejecutivo=mensaje_ejecutivo,
                    metadatos=metadatos,
                )
            )
        if self._tg_token and self._tg_chat_id:
            resultados.append(self.enviar_telegram_directo(mensaje_ejecutivo))
        return resultados
