"""Entidades del dominio agro-ecológico.

Las entidades son ``dataclass`` inmutables (``frozen``): cualquier cambio de estado
pasa por un servicio de aplicación que persiste y devuelve una nueva instancia.
Esto elimina la clase de bugs de v3.2 donde la UI mutaba un ``DataFrame`` cacheado
(``self.mapa_parcelas[nombre]['humedad'] = 95``) desincronizado del disco.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Rol(StrEnum):
    ADMIN = "admin"        # CRUD completo + ejecución de riego
    OPERADOR = "operador"  # Consulta y monitoreo (equivale al rol "user" de v3.2)
    LECTOR = "lector"      # Reservado: acceso de solo lectura (jurados, aliados)


class TipoSuelo(StrEnum):
    """Clases texturales USDA simplificadas usadas en v3.2.

    Agronómicamente determinan capacidad de campo (CC) y punto de marchitez
    permanente (PMP); se usarán en v4.x para umbrales de riego por textura.
    """

    FRANCO = "Franco"
    ARENOSO = "Arenoso"
    ARCILLOSO = "Arcilloso"


class TipoEstacion(StrEnum):
    TERRABIT_INTI = "terrabit_inti"   # Edafoclimática: suelo A/B, raíz, VPD
    INBEERSA = "inbeersa"             # Meliponario: DHT int/ext, MQ-135, bioacústica
    SIGATOKA = "sigatoka"             # Microclima foliar / mojado de hoja
    CONSERVACION = "conservacion"     # Páramo, turberas, Polylepis
    OTRO = "otro"


class OrigenRiego(StrEnum):
    MANUAL = "manual"
    AUTOMATICO = "automatico"
    LEGACY_V32 = "legacy_v32"


CULTIVOS_SOPORTADOS: tuple[str, ...] = ("Maiz", "Tomate", "Fresas", "Hortalizas", "Flores")


@dataclass(frozen=True, slots=True)
class Usuario:
    id: int
    usuario: str
    nombre: str
    rol: Rol
    activo: bool = True

    @property
    def es_admin(self) -> bool:
        return self.rol is Rol.ADMIN


@dataclass(frozen=True, slots=True)
class DatosParcela:
    """Datos de entrada YA validados y normalizados (ver ``validadores``)."""

    nombre: str
    cultivo: str
    area_m2: float
    humedad_pct: float
    tipo_suelo: TipoSuelo
    riego_auto: bool
    estacion_id: int | None = None


@dataclass(frozen=True, slots=True)
class Parcela:
    id: int
    nombre: str
    cultivo: str
    area_m2: float
    humedad_pct: float
    tipo_suelo: TipoSuelo
    riego_auto: bool
    estacion_id: int | None
    activa: bool
    creado_en: str
    actualizado_en: str


@dataclass(frozen=True, slots=True)
class EventoRiego:
    id: int
    parcela_id: int
    ts_iso: str
    ts_epoch: int
    humedad_inicial_pct: float | None
    humedad_final_pct: float | None
    agua_litros: float
    origen: OrigenRiego
    usuario_id: int | None


@dataclass(frozen=True, slots=True)
class Estacion:
    id: int
    codigo: str            # Identificador estable, p. ej. "inti-01" (= device_label de Ubidots)
    nombre: str
    tipo: TipoEstacion
    latitud: float | None = None
    longitud: float | None = None
    altitud_m: float | None = None
    activa: bool = True


@dataclass(frozen=True, slots=True)
class LecturaSensor:
    """Una muestra de una variable física de una estación (formato largo / narrow).

    El formato largo (una fila por variable) permite que estaciones heterogéneas
    (INTI con 9 variables, InBeersa con MQ-135 y DHT dobles, Sigatoka con mojado
    foliar) compartan la misma tabla sin migraciones de esquema por cada sensor nuevo.
    """

    estacion_id: int
    variable: str          # p. ej. "suelo_a", "vpd", "temp_aire"
    valor: float
    ts_epoch: int
    ts_iso: str
    fuente: str            # sd_csv | sd_jsonl | ubidots | mqtt_local | lora | manual
    unidad: str | None = None
    calidad: int = 0       # 0 válido · 1 sospechoso · 2 inválido (p. ej. DHT -200 °C)
