"""Esquemas Pydantic v2 y serialización segura de entidades de dominio."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


def serializar_objeto(obj: Any) -> Any:
    """Convierte recursivamente dataclasses, Enums y Paths a tipos JSON nativos."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, Path):
        return str(obj)
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: serializar_objeto(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): serializar_objeto(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [serializar_objeto(item) for item in obj]
    return str(obj)


# ── Autenticación & Usuarios ─────────────────────────────────────────────────
class LoginRequest(BaseModel):
    usuario: str = Field(..., min_length=1)
    clave: str = Field(..., min_length=1)


class CrearUsuarioRequest(BaseModel):
    usuario: str
    nombre: str
    clave: str
    rol: str = "operador"


class CambiarClaveRequest(BaseModel):
    nueva_clave: str


# ── Estaciones ───────────────────────────────────────────────────────────────
class RegistrarEstacionRequest(BaseModel):
    codigo: str
    nombre: str
    tipo: str
    latitud: float | None = None
    longitud: float | None = None
    altitud_m: float | None = None


# ── Parcelas ─────────────────────────────────────────────────────────────────
class CrearParcelaRequest(BaseModel):
    nombre: str
    cultivo: str
    area_m2: float | str
    humedad_pct: float | str
    tipo_suelo: str
    riego_auto: bool = False
    estacion_id: int | None = None


class ActualizarParcelaRequest(BaseModel):
    nombre: str | None = None
    cultivo: str | None = None
    area_m2: float | str | None = None
    humedad_pct: float | str | None = None
    tipo_suelo: str | None = None
    riego_auto: bool | None = None
    estacion_id: int | None = None
    desvincular_estacion: bool = False


# ── Riego & Enclavamientos ───────────────────────────────────────────────────
class AplicarRiegoRequest(BaseModel):
    umbral_pct: float
    litros: float
    fecha_iso: str  # YYYY-MM-DD
    hora: str       # HH:MM


class ProgramarRiegoRequest(BaseModel):
    ts_programado_epoch: int | None = None
    fecha_iso: str | None = None
    hora: str = "06:00"
    litros_solicitados: float
    apertura_solicitada_pct: float = 100.0
    origen: str = "ia_proactivo"
    modo_verificacion: str = "sin_sensor_actuador"
    mantenimiento_confirmado: bool = False


class RegistrarIncidenciaRequest(BaseModel):
    evento_riego_id: int
    humedad_a_antes: float
    humedad_a_despues: float
    humedad_b_antes: float | None = None
    humedad_b_despues: float | None = None
    modo_verificacion: str = "sin_sensor_actuador"
    apertura_max_pct: float = 100.0
    vibracion_rms_g: float | None = None
    vibracion_freq_hz: float | None = None
    corriente_a: float | None = None
    caudal_lpm: float | None = None


# ── Copiloto IA & Calibración ────────────────────────────────────────────────
class ConsultarCopilotoRequest(BaseModel):
    mensaje: str
    estacion_id: int | None = None
    parcela_id: int | None = None
    aplicar_ajustes: bool = False


class AplicarCalibracionRequest(BaseModel):
    interaccion_id: int
    motivo_adicional: str | None = None


class RollbackCalibracionRequest(BaseModel):
    estacion_id: int | None = None
    parcela_id: int | None = None
    version_id_destino: int | None = None


# ── Hardware nRF24L01+ & MicroSD ─────────────────────────────────────────────
class LeerSerialRequest(BaseModel):
    puerto: str
    baudrate: int = 115200
    max_lineas: int = 25


class IngerirTramasRequest(BaseModel):
    lineas: list[str]
    ts_epoch_defecto: int | None = None


class EscanearMicroSDRequest(BaseModel):
    directorios: list[str] | None = None


class ImportarMicroSDRequest(BaseModel):
    estacion_id: int
    ruta_archivo: str


# ── Sistema & Conectores ─────────────────────────────────────────────────────
class SyncHibridaRequest(BaseModel):
    dias_clima: int = 2


class Notificar24hRequest(BaseModel):
    estacion_id: int


class ReconfigurarConectoresRequest(BaseModel):
    ubidots_token: str | None = None
    ia_proveedor: str | None = None
    ia_gemini_key: str | None = None
    ia_gemini_modelo: str | None = None
    ia_ollama_url: str | None = None
    ia_ollama_modelo: str | None = None
    webhook_n8n_url: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    guardar_en_env_local: bool = False


class WorkerControlRequest(BaseModel):
    activo: bool
    intervalo_segundos: float = 900.0
    precalentar_ollama: bool = True
