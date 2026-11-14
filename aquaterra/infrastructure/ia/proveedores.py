"""Conectores de infraestructura IA (Google Gemini AI Studio, Ollama Local y Orquestador en Cascada).

Implementa la arquitectura híbrida de 3 niveles de la Fase B5:
1. Nube: Google Gemini (`gemini-4-hydrogen` por defecto) mediante la API moderna
   `Interactions` (`google-genai >= 3.2.0` o cliente REST `/v1beta/interactions`).
2. Borde en Finca (PC Offline): `Ollama` local (`http://127.0.0.1:11434/api/chat`)
   con salida estructurada JSON (`gemma3:4b` / `qwen2.5:3b`).
3. Respaldo Determinista Nativo: `AsesorDeterministaCopiloto` (`local_reglas`),
   garantizando operación continua sin internet y auditoría de cotas físicas.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, replace
from typing import Protocol

from aquaterra.core.copiloto.asesor_reglas import AsesorDeterministaCopiloto
from aquaterra.core.copiloto.contratos_ia import (
    ESQUEMA_JSON_RESPUESTA_COPILOTO,
    ContextoDiagnosticoCopiloto,
    PropuestaCopiloto,
    construir_prompt_contexto_copiloto,
    construir_system_instruction_terrabit,
)
from aquaterra.core.copiloto.cotas_calibracion import (
    ResultadoAuditoriaCalibracion,
    auditar_y_acotar_ajustes,
)

log = logging.getLogger(__name__)

MODELO_GEMINI_POR_DEFECTO = "gemini-3.5-flash-lite"
MODELO_OLLAMA_POR_DEFECTO = "qwen2.5:3b"
PREFIJOS_GEMINI_OBSOLETOS = ("gemini-2.5-", "gemini-2.0-", "gemini-1.5-")


def normalizar_modelo_gemini(modelo: str) -> str:
    """Reemplaza identificadores de modelos Gemini heredados por `gemini-4-hydrogen`."""
    limpio = modelo.strip()
    if not limpio or limpio.startswith(PREFIJOS_GEMINI_OBSOLETOS):
        log.warning(
            "Modelo Gemini '%s' obsoleto o vacío; sustituyendo automáticamente por '%s'.",
            modelo,
            MODELO_GEMINI_POR_DEFECTO,
        )
        return MODELO_GEMINI_POR_DEFECTO
    return limpio


@dataclass(frozen=True, slots=True)
class ConfiguracionIA:
    """Parámetros de conexión para el Orquestador IA híbrido."""

    proveedor_preferido: str = field(
        default_factory=lambda: os.environ.get("AQUATERRA_IA_PROVEEDOR", "auto").strip().lower()
    )
    gemini_api_key: str | None = field(
        default_factory=lambda: (
            os.environ.get("GEMINI_API_KEY") or os.environ.get("AQUATERRA_GEMINI_API_KEY")
        )
    )
    gemini_modelo: str = field(
        default_factory=lambda: normalizar_modelo_gemini(
            os.environ.get("AQUATERRA_GEMINI_MODEL", MODELO_GEMINI_POR_DEFECTO)
        )
    )
    ollama_base_url: str = field(
        default_factory=lambda: os.environ.get(
            "AQUATERRA_OLLAMA_URL", "http://127.0.0.1:11434"
        ).rstrip("/")
    )
    ollama_modelo: str = field(
        default_factory=lambda: os.environ.get("AQUATERRA_OLLAMA_MODEL", MODELO_OLLAMA_POR_DEFECTO)
    )
    timeout_segundos: float = 12.0
    ollama_timeout_segundos: float = field(
        default_factory=lambda: float(os.environ.get("AQUATERRA_OLLAMA_TIMEOUT", "90.0"))
    )


class ProveedorCopilotoProtocol(Protocol):
    """Contrato común para cualquier proveedor de inferencia del Copiloto."""

    proveedor_id: str

    def diagnosticar(self, ctx: ContextoDiagnosticoCopiloto) -> PropuestaCopiloto: ...


def limpiar_bloque_json(texto: str) -> str:
    """Extrae el objeto JSON aunque el modelo lo envuelva en bloques Markdown ```json."""
    limpio = texto.strip()
    if limpio.startswith("```"):
        lineas = limpio.splitlines()
        if lineas and lineas[0].startswith("```"):
            lineas = lineas[1:]
        if lineas and lineas[-1].strip().startswith("```"):
            lineas = lineas[:-1]
        limpio = "\n".join(lineas).strip()
    return limpio


def parsear_respuesta_json_ia(texto_json: str, *, proveedor_ia: str) -> PropuestaCopiloto:
    """Convierte el JSON devuelto por Gemini u Ollama en `PropuestaCopiloto`."""
    limpio = limpiar_bloque_json(texto_json)
    datos = json.loads(limpio)
    if not isinstance(datos, dict):
        raise ValueError("La respuesta del modelo IA no es un objeto JSON válido.")

    diagnostico = str(datos.get("diagnostico_tecnico") or "").strip()
    justificacion = str(datos.get("justificacion_agronomica") or "").strip()
    if not diagnostico:
        raise ValueError("La respuesta JSON del modelo no contiene `diagnostico_tecnico`.")

    ajustes_raw = datos.get("ajustes_propuestos") or {}
    ajustes: dict[str, float] = {}
    if isinstance(ajustes_raw, dict):
        for k, v in ajustes_raw.items():
            if v is not None and not isinstance(v, bool):
                try:
                    ajustes[str(k)] = float(v)
                except (ValueError, TypeError):
                    ajustes[str(k)] = v  # Lo filtrará auditar_y_acotar_ajustes con trazabilidad

    try:
        confianza = float(datos.get("confianza", 0.85))
    except (ValueError, TypeError):
        confianza = 0.85
    confianza = max(0.0, min(1.0, round(confianza, 3)))

    alertas_raw = datos.get("alertas_consideradas") or []
    alertas = (
        tuple(str(a) for a in alertas_raw if a)
        if isinstance(alertas_raw, list)
        else ()
    )

    return PropuestaCopiloto(
        diagnostico_tecnico=diagnostico,
        justificacion_agronomica=justificacion,
        ajustes_propuestos=ajustes,
        confianza=confianza,
        alertas_consideradas=alertas,
        proveedor_ia=proveedor_ia,
    )


class ClienteGeminiAIStudio:
    """Conector hacia Google AI Studio usando la API Interactions (`gemini-4-hydrogen`)."""

    def __init__(
        self,
        *,
        api_key: str,
        modelo: str = MODELO_GEMINI_POR_DEFECTO,
        timeout_segundos: float = 12.0,
    ) -> None:
        self._api_key = api_key.strip()
        self._modelo = normalizar_modelo_gemini(modelo)
        self._timeout = timeout_segundos
        self.proveedor_id = f"gemini:{self._modelo}"

    def diagnosticar(self, ctx: ContextoDiagnosticoCopiloto) -> PropuestaCopiloto:
        if not self._api_key:
            raise RuntimeError("No se ha configurado GEMINI_API_KEY.")

        system_instruction = construir_system_instruction_terrabit()
        prompt_usuario = construir_prompt_contexto_copiloto(ctx)

        # 1. Intentar con el SDK oficial moderno `google-genai` (>= 3.2.0) si está instalado
        try:
            from google import genai  # type: ignore[import-not-found]
            from google.genai import types as genai_types  # type: ignore[import-not-found]

            # Máximo 3 reintentos rápidos SOLO ante errores transitorios (408/5xx);
            # se excluye HTTP 429 para no dormir horas en backoff ante cuota agotada.
            http_opts = genai_types.HttpOptions(
                timeout=int(max(2.0, self._timeout) * 1000),
                retry_options=genai_types.HttpRetryOptions(
                    attempts=3,
                    initial_delay=0.5,
                    max_delay=1.5,
                    exp_base=2.0,
                    http_status_codes=[408, 500, 502, 503, 504],
                ),
            )
            client = genai.Client(api_key=self._api_key, http_options=http_opts)
            interaction = client.interactions.create(
                model=self._modelo,
                system_instruction=system_instruction,
                input=prompt_usuario,
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": ESQUEMA_JSON_RESPUESTA_COPILOTO,
                },
                timeout=self._timeout,
            )
            texto_salida = getattr(interaction, "output_text", None)
            if not texto_salida:
                raise RuntimeError("Gemini Interactions API devolvió output_text vacío.")
            return parsear_respuesta_json_ia(texto_salida, proveedor_ia=self.proveedor_id)
        except ImportError:
            pass

        # 2. Respaldo HTTP REST directo (cero dependencias externas) hacia /v1beta/interactions
        url = "https://generativelanguage.googleapis.com/v1beta/interactions"
        cuerpo = json.dumps(
            {
                "model": self._modelo,
                "system_instruction": system_instruction,
                "input": prompt_usuario,
                "response_format": {
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": ESQUEMA_JSON_RESPUESTA_COPILOTO,
                },
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=cuerpo,
            headers={
                "x-goog-api-key": self._api_key,
                "Content-Type": "application/json",
                "Api-Revision": "2026-05-20",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            datos_resp = json.loads(resp.read().decode("utf-8"))

        texto_salida = datos_resp.get("output_text")
        if not texto_salida and isinstance(datos_resp.get("steps"), list):
            for step in reversed(datos_resp["steps"]):
                contenido = step.get("content") or step.get("text")
                if isinstance(contenido, str) and contenido.strip():
                    texto_salida = contenido
                    break
        if not texto_salida:
            raise RuntimeError("Respuesta REST de Gemini Interactions no contiene output_text.")

        return parsear_respuesta_json_ia(texto_salida, proveedor_ia=self.proveedor_id)


class ClienteOllamaLocal:
    """Conector hacia servidor local Ollama (`http://127.0.0.1:11434/api/chat`)."""

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        modelo: str = MODELO_OLLAMA_POR_DEFECTO,
        timeout_segundos: float = 90.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._modelo = modelo.strip() or MODELO_OLLAMA_POR_DEFECTO
        self._timeout = timeout_segundos
        self.proveedor_id = f"ollama:{self._modelo}"

    def esta_disponible(self, timeout_ping: float = 1.2) -> bool:
        """Verifica rápidamente si el demonio local de Ollama responde."""
        try:
            req = urllib.request.Request(f"{self._base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=timeout_ping) as resp:
                return resp.status == 200
        except Exception:
            return False

    def precalentar(self, *, keep_alive: str = "10m") -> bool:
        """Pre-carga el modelo en la VRAM de la GPU sin generar tokens para eliminar la latencia en frío."""
        if not self.esta_disponible():
            return False
        url = f"{self._base_url}/api/generate"
        cuerpo = json.dumps(
            {
                "model": self._modelo,
                "prompt": "",
                "keep_alive": keep_alive,
                "stream": False,
            }
        ).encode("utf-8")
        try:
            req = urllib.request.Request(
                url,
                data=cuerpo,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return resp.status == 200
        except Exception:
            return False

    def diagnosticar(self, ctx: ContextoDiagnosticoCopiloto) -> PropuestaCopiloto:
        url = f"{self._base_url}/api/chat"
        cuerpo = json.dumps(
            {
                "model": self._modelo,
                "messages": [
                    {"role": "system", "content": construir_system_instruction_terrabit()},
                    {"role": "user", "content": construir_prompt_contexto_copiloto(ctx)},
                ],
                "format": ESQUEMA_JSON_RESPUESTA_COPILOTO,
                "options": {
                    "temperature": 0.25,
                    "num_predict": 650,
                },
                "keep_alive": "10m",
                "stream": False,
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=cuerpo,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            datos_resp = json.loads(resp.read().decode("utf-8"))

        mensaje = datos_resp.get("message") or {}
        texto_salida = mensaje.get("content", "")
        if not texto_salida:
            raise RuntimeError("Ollama devolvió un mensaje vacío.")

        return parsear_respuesta_json_ia(texto_salida, proveedor_ia=self.proveedor_id)


def _es_error_cuota_gemini(exc: BaseException) -> bool:
    """Detecta HTTP 429 / cuota agotada en Gemini para activar enfriamiento sin reintentos inútiles."""
    msg = f"{type(exc).__name__} {exc}".lower()
    return any(
        tok in msg
        for tok in ("429", "ratelimit", "rate limit", "too_many_requests", "resource_exhausted")
    )


class OrquestadorIA:
    """Orquestador en cascada con guardarraíles físicos deterministas."""

    COOLDOWN_CUOTA_GEMINI_SEG = 300.0

    def __init__(
        self,
        config: ConfiguracionIA | None = None,
        *,
        proveedor_override: ProveedorCopilotoProtocol | None = None,
    ) -> None:
        self.config = config or ConfiguracionIA()
        self._override = proveedor_override
        self._asesor_reglas = AsesorDeterministaCopiloto()
        self._cooldown_lock = threading.Lock()
        self._gemini_cooldown_hasta = 0.0

    def gemini_en_enfriamiento(self) -> bool:
        """Indica si Gemini está temporalmente en pausa tras agotamiento de cuota."""
        with self._cooldown_lock:
            return time.monotonic() < self._gemini_cooldown_hasta

    def diagnosticar_con_auditoria(
        self, ctx: ContextoDiagnosticoCopiloto
    ) -> tuple[PropuestaCopiloto, ResultadoAuditoriaCalibracion]:
        """Ejecuta el diagnóstico en cascada y audita/acota cualquier ajuste propuesto."""
        propuesta_bruta = self._ejecutar_cascada(ctx)
        auditoria = auditar_y_acotar_ajustes(
            propuesta_bruta.ajustes_propuestos,
            ctx.parametros_actuales,
        )
        propuesta_segura = replace(
            propuesta_bruta,
            ajustes_propuestos=auditoria.ajustes_seguros,
        )
        return propuesta_segura, auditoria

    def _ejecutar_cascada(self, ctx: ContextoDiagnosticoCopiloto) -> PropuestaCopiloto:
        if self._override is not None:
            try:
                return self._override.diagnosticar(ctx)
            except Exception as exc:
                log.warning(
                    "Proveedor IA override (%s) falló: %s. Cayendo a motor determinista.",
                    getattr(self._override, "proveedor_id", "custom"),
                    exc,
                )
                return self._asesor_reglas.diagnosticar(ctx)

        modo = self.config.proveedor_preferido

        # 1. Intento con Google Gemini AI Studio (respetando enfriamiento por cuota 429)
        if modo in ("auto", "gemini") and self.config.gemini_api_key:
            en_pausa = modo == "auto" and self.gemini_en_enfriamiento()
            if en_pausa:
                log.info(
                    "Gemini AI Studio en enfriamiento por cuota; delegando directo al siguiente nivel."
                )
            else:
                cliente_gemini = ClienteGeminiAIStudio(
                    api_key=self.config.gemini_api_key,
                    modelo=self.config.gemini_modelo,
                    timeout_segundos=self.config.timeout_segundos,
                )
                try:
                    return cliente_gemini.diagnosticar(ctx)
                except (urllib.error.URLError, TimeoutError, ValueError, RuntimeError, Exception) as exc:
                    if _es_error_cuota_gemini(exc):
                        with self._cooldown_lock:
                            self._gemini_cooldown_hasta = (
                                time.monotonic() + self.COOLDOWN_CUOTA_GEMINI_SEG
                            )
                        log.warning(
                            "Gemini AI Studio alcanzó límite de cuota (429); "
                            "activando enfriamiento %.0fs y pasando a respaldo local.",
                            self.COOLDOWN_CUOTA_GEMINI_SEG,
                        )
                    else:
                        log.warning(
                            "Gemini AI Studio no disponible (%s). Evaluando siguiente nivel.", exc
                        )

        # 2. Intento con Ollama Local
        if modo in ("auto", "ollama"):
            cliente_ollama = ClienteOllamaLocal(
                base_url=self.config.ollama_base_url,
                modelo=self.config.ollama_modelo,
                timeout_segundos=self.config.ollama_timeout_segundos,
            )
            if modo == "ollama" or cliente_ollama.esta_disponible():
                try:
                    return cliente_ollama.diagnosticar(ctx)
                except (
                    urllib.error.URLError,
                    TimeoutError,
                    ValueError,
                    RuntimeError,
                    Exception,
                ) as exc:
                    log.warning(
                        "Ollama Local no disponible (%s). Cayendo a motor determinista.", exc
                    )

        # 3. Respaldo determinista nativo (siempre disponible 100% offline)
        return self._asesor_reglas.diagnosticar(ctx)

    def precalentar_ollama_async(self, *, keep_alive: str = "10m") -> threading.Thread:
        """Lanza un hilo daemon no bloqueante que sube el modelo de Ollama a VRAM en segundo plano."""
        cliente_ollama = ClienteOllamaLocal(
            base_url=self.config.ollama_base_url,
            modelo=self.config.ollama_modelo,
            timeout_segundos=self.config.ollama_timeout_segundos,
        )
        hilo = threading.Thread(
            target=cliente_ollama.precalentar,
            kwargs={"keep_alive": keep_alive},
            name="AquaTerra-OllamaWarmup",
            daemon=True,
        )
        hilo.start()
        return hilo
