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


def cargar_env_local(ruta_env: Path | None = None) -> int:
    """Carga pares KEY=VALUE desde `.env` local (si existe) sin sobreescribir el entorno del SO."""
    destino = ruta_env or (RAIZ_PROYECTO / ".env")
    if not destino.exists() or not destino.is_file():
        return 0
    cargadas = 0
    for linea in destino.read_text(encoding="utf-8", errors="ignore").splitlines():
        texto = linea.strip()
        if not texto or texto.startswith("#") or "=" not in texto:
            continue
        clave, valor = texto.split("=", 1)
        clave = clave.strip()
        valor = valor.strip().strip('"').strip("'")
        if clave and clave not in os.environ:
            os.environ[clave] = valor
            cargadas += 1
    return cargadas


def guardar_env_local(pares: dict[str, str], ruta_env: Path | None = None) -> Path:
    """Persiste configuración local del cliente en `.env` (ignorado por Git)."""
    destino = ruta_env or (RAIZ_PROYECTO / ".env")
    existentes: dict[str, str] = {}
    if destino.exists():
        for linea in destino.read_text(encoding="utf-8", errors="ignore").splitlines():
            texto = linea.strip()
            if not texto or texto.startswith("#") or "=" not in texto:
                continue
            k, v = texto.split("=", 1)
            existentes[k.strip()] = v.strip().strip('"').strip("'")
    for k, v in pares.items():
        if v:
            existentes[k] = v
        else:
            existentes.pop(k, None)
    lineas = [
        "# Configuración local del cliente AquaTerra Matrix (NO subir a Git)",
        *(f"{k}={v}" for k, v in sorted(existentes.items())),
        "",
    ]
    destino.write_text("\n".join(lineas), encoding="utf-8")
    return destino


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
    tema_ui: str = field(default_factory=lambda: os.environ.get("AQUATERRA_TEMA", "aquaterra-dark"))


def configuracion_por_defecto() -> Configuracion:
    cargar_env_local()
    return Configuracion()
