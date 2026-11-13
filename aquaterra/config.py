"""Configuración central de rutas y parámetros operativos.

Toda ruta se resuelve de forma relativa a la raíz del repositorio para que el
software funcione igual en el PC de desarrollo, una MiniPC de campo o una
Raspberry Pi actuando como estación base.

Variables de entorno soportadas (útiles para despliegue en servidor):
    AQUATERRA_DB     -> ruta absoluta alternativa del archivo SQLite.
    AQUATERRA_TEMA   -> tema ttkbootstrap (por defecto "superhero").
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Raíz del repositorio: .../AquaTerra_Matrix
RAIZ_PROYECTO: Path = Path(__file__).resolve().parent.parent
PAQUETE: Path = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Configuracion:
    """Parámetros inmutables de una instancia de la aplicación."""

    ruta_db: Path = field(
        default_factory=lambda: Path(
            os.environ.get("AQUATERRA_DB", RAIZ_PROYECTO / "data" / "runtime" / "aquaterra.db")
        )
    )
    # Semilla de datos heredada de AquaUTP v3.2 (solo lectura, se importa una vez).
    ruta_semilla_legacy: Path = RAIZ_PROYECTO / "legacy" / "aquautp_v3.2" / "data"
    ruta_assets: Path = PAQUETE / "ui" / "assets"
    tema_ui: str = field(default_factory=lambda: os.environ.get("AQUATERRA_TEMA", "bootstrap-dark"))


def configuracion_por_defecto() -> Configuracion:
    return Configuracion()
