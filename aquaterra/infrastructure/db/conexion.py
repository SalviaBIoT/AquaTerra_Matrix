"""Fábrica de conexiones SQLite endurecidas para series temporales.

PRAGMAs aplicados en cada conexión:
- ``journal_mode=WAL``   : escrituras concurrentes con lecturas y resistencia a cortes
                           de energía (crítico en estaciones base rurales). En archivos
                           en memoria SQLite lo ignora y queda en "memory".
- ``synchronous=NORMAL`` : con WAL es seguro ante caída de la app; equilibrio entre
                           durabilidad y velocidad de ingesta (288 muestras/día/nodo).
- ``foreign_keys=ON``    : SQLite las trae APAGADAS por defecto; sin esto la
                           integridad referencial parcelas↔riegos no se haría cumplir.
- ``busy_timeout=5000``  : espera hasta 5 s si otro proceso (p. ej. el daemon de
                           ingesta MQTT de v5.0) tiene bloqueada la base.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


def abrir_conexion(ruta: Path | str) -> sqlite3.Connection:
    """Abre (y crea si no existe) la base SQLite. Usar ``":memory:"`` en pruebas."""
    if str(ruta) != ":memory:":
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)

    conexion = sqlite3.connect(str(ruta), detect_types=0)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON;")
    conexion.execute("PRAGMA journal_mode = WAL;")
    conexion.execute("PRAGMA synchronous = NORMAL;")
    conexion.execute("PRAGMA busy_timeout = 5000;")
    return conexion
