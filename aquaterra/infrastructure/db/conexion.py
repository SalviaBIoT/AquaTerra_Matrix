"""Fábrica de conexiones SQLite endurecidas para series temporales y concurrencia multi-hilo.

PRAGMAs aplicados en cada conexión:
- ``journal_mode=WAL``   : escrituras concurrentes con lecturas y resistencia a cortes
                           de energía (crítico en estaciones base rurales). En archivos
                           en memoria SQLite lo ignora y queda en "memory".
- ``synchronous=NORMAL`` : con WAL es seguro ante caída de la app; equilibrio entre
                           durabilidad y velocidad de ingesta (288 muestras/día/nodo).
- ``foreign_keys=ON``    : SQLite las trae APAGADAS por defecto; sin esto la
                           integridad referencial parcelas↔riegos no se haría cumplir.
- ``busy_timeout=5000``  : espera hasta 5 s si otro proceso o hilo tiene bloqueada la base.

Concurrencia ``v6.0``:
- Se abre con ``check_same_thread=False`` y se envuelve en ``ConexionSQLiteSegura``,
  un proxy protegido por ``threading.RLock()`` que serializa transacciones
  (``with conexion:``) y consultas desde hilos de UI, workers en segundo plano
  y peticiones concurrentes de FastAPI/Uvicorn sin errores ``ProgrammingError`` de
  cambio de hilo.
"""

from __future__ import annotations

import contextlib
import sqlite3
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any


class _CursorSeguro:
    """Proxy sobre ``sqlite3.Cursor`` que serializa lectura/cierre bajo el mismo ``RLock``."""

    __slots__ = ("_cursor", "_lock")

    def __init__(self, cursor: sqlite3.Cursor, lock: threading.RLock) -> None:
        object.__setattr__(self, "_cursor", cursor)
        object.__setattr__(self, "_lock", lock)

    def fetchone(self) -> Any:
        with self._lock:
            return self._cursor.fetchone()

    def fetchmany(self, size: int | None = None) -> list[Any]:
        with self._lock:
            if size is None:
                return self._cursor.fetchmany()
            return self._cursor.fetchmany(size)

    def fetchall(self) -> list[Any]:
        with self._lock:
            return self._cursor.fetchall()

    def close(self) -> None:
        with self._lock:
            self._cursor.close()

    def __iter__(self) -> Iterator[Any]:
        with self._lock:
            filas = self._cursor.fetchall()
        return iter(filas)

    def __getattr__(self, nombre: str) -> Any:
        with self._lock:
            return getattr(self._cursor, nombre)


class ConexionSQLiteSegura:
    """Proxy thread-safe sobre ``sqlite3.Connection`` protegido con ``threading.RLock``."""

    __slots__ = ("_conn", "_lock", "_tx_depth")

    def __init__(self, conn: sqlite3.Connection) -> None:
        object.__setattr__(self, "_conn", conn)
        object.__setattr__(self, "_lock", threading.RLock())
        object.__setattr__(self, "_tx_depth", 0)

    @contextlib.contextmanager
    def bloqueo(self) -> Iterator[None]:
        """Serializa bloques multi-consulta de lectura sin abrir transacción DML."""
        with self._lock:
            yield

    def __enter__(self) -> ConexionSQLiteSegura:
        self._lock.acquire()
        try:
            self._tx_depth += 1
            if self._tx_depth == 1:
                self._conn.__enter__()
            return self
        except BaseException:
            self._tx_depth = max(0, self._tx_depth - 1)
            self._lock.release()
            raise

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Any:
        try:
            self._tx_depth = max(0, self._tx_depth - 1)
            if self._tx_depth == 0:
                return self._conn.__exit__(exc_type, exc_val, exc_tb)
            if exc_type is not None:
                self._conn.rollback()
            return False
        finally:
            self._lock.release()

    def execute(self, sql: str, parameters: Any = ()) -> _CursorSeguro:
        with self._lock:
            return _CursorSeguro(self._conn.execute(sql, parameters), self._lock)

    def executemany(self, sql: str, seq_of_parameters: Any) -> _CursorSeguro:
        with self._lock:
            return _CursorSeguro(self._conn.executemany(sql, seq_of_parameters), self._lock)

    def executescript(self, sql_script: str) -> _CursorSeguro:
        with self._lock:
            return _CursorSeguro(self._conn.executescript(sql_script), self._lock)

    def cursor(self, *args: Any, **kwargs: Any) -> _CursorSeguro:
        with self._lock:
            return _CursorSeguro(self._conn.cursor(*args, **kwargs), self._lock)

    def commit(self) -> None:
        with self._lock:
            self._conn.commit()

    def rollback(self) -> None:
        with self._lock:
            self._conn.rollback()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __getattr__(self, nombre: str) -> Any:
        return getattr(self._conn, nombre)

    def __setattr__(self, nombre: str, valor: Any) -> None:
        if nombre in self.__slots__:
            object.__setattr__(self, nombre, valor)
        else:
            setattr(self._conn, nombre, valor)


def abrir_conexion(ruta: Path | str) -> ConexionSQLiteSegura:
    """Abre (y crea si no existe) la base SQLite thread-safe. Usar ``":memory:"`` en pruebas."""
    if str(ruta) != ":memory:":
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)

    conexion = sqlite3.connect(str(ruta), detect_types=0, check_same_thread=False)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON;")
    conexion.execute("PRAGMA journal_mode = WAL;")
    conexion.execute("PRAGMA synchronous = NORMAL;")
    conexion.execute("PRAGMA busy_timeout = 5000;")
    return ConexionSQLiteSegura(conexion)
