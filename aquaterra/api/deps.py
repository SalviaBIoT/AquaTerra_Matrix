"""Dependencias FastAPI: resolución de ``Contenedor`` y sesiones autenticadas."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
import threading
import time
from typing import Annotated

from fastapi import Cookie, Depends, Header, Request

from aquaterra.application.contenedor import Contenedor
from aquaterra.core.domain import EntidadNoEncontrada, ErrorPermiso, ErrorSesionExpirada, Usuario
from aquaterra.infrastructure.db.conexion import ConexionSQLiteSegura
from aquaterra.infrastructure.db.repositorios import RepositorioUsuarios

COOKIE_SESION = "aquaterra_session"
_MAX_EDAD_SESION_S = 60 * 60 * 24 * 30  # 30 días en uso local de estación base


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class GestorSesiones:
    """Almacén thread-safe de tokens ``Bearer`` / cookie con respaldo persistente en SQLite."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sesiones: dict[str, int] = {}
        self._tablas_listas: set[int] = set()

    def _asegurar_tabla(self, conexion: ConexionSQLiteSegura) -> None:
        conn_id = id(conexion)
        if conn_id in self._tablas_listas:
            return
        with conexion:
            conexion.execute(
                """
                CREATE TABLE IF NOT EXISTS sesiones_api (
                    token_hash   TEXT PRIMARY KEY,
                    usuario_id   INTEGER NOT NULL,
                    creado_epoch INTEGER NOT NULL,
                    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
                );
                """
            )
        self._tablas_listas.add(conn_id)

    def crear(
        self, usuario_id: int, *, conexion: ConexionSQLiteSegura | None = None
    ) -> str:
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._sesiones[token] = usuario_id
            if conexion is not None:
                try:
                    self._asegurar_tabla(conexion)
                    ahora = int(time.time())
                    with conexion:
                        conexion.execute(
                            """
                            INSERT OR REPLACE INTO sesiones_api (token_hash, usuario_id, creado_epoch)
                            VALUES (?, ?, ?)
                            """,
                            (_hash_token(token), usuario_id, ahora),
                        )
                except sqlite3.Error:
                    pass
        return token

    def obtener_usuario_id(
        self, token: str | None, *, conexion: ConexionSQLiteSegura | None = None
    ) -> int | None:
        if not token:
            return None
        with self._lock:
            en_ram = self._sesiones.get(token)
            if en_ram is not None:
                return en_ram
            if conexion is None:
                return None
            try:
                self._asegurar_tabla(conexion)
                fila = conexion.execute(
                    """
                    SELECT usuario_id, creado_epoch
                    FROM sesiones_api
                    WHERE token_hash = ?
                    """,
                    (_hash_token(token),),
                ).fetchone()
                if fila is None:
                    return None
                if int(time.time()) - int(fila["creado_epoch"]) > _MAX_EDAD_SESION_S:
                    with conexion:
                        conexion.execute(
                            "DELETE FROM sesiones_api WHERE token_hash = ?",
                            (_hash_token(token),),
                        )
                    return None
                uid = int(fila["usuario_id"])
                self._sesiones[token] = uid
                return uid
            except sqlite3.Error:
                return None

    def revocar(
        self, token: str | None, *, conexion: ConexionSQLiteSegura | None = None
    ) -> None:
        if not token:
            return
        with self._lock:
            self._sesiones.pop(token, None)
            if conexion is not None:
                try:
                    self._asegurar_tabla(conexion)
                    with conexion:
                        conexion.execute(
                            "DELETE FROM sesiones_api WHERE token_hash = ?",
                            (_hash_token(token),),
                        )
                except sqlite3.Error:
                    pass


def get_contenedor(request: Request) -> Contenedor:
    return request.app.state.contenedor


def get_gestor_sesiones(request: Request) -> GestorSesiones:
    return request.app.state.sesiones


def extraer_token(
    authorization: Annotated[str | None, Header()] = None,
    x_aquaterra_token: Annotated[str | None, Header()] = None,
    aquaterra_session: Annotated[str | None, Cookie()] = None,
) -> str | None:
    if authorization:
        partes = authorization.split(" ", 1)
        if len(partes) == 2 and partes[0].lower() == "bearer":
            return partes[1].strip()
        return authorization.strip()
    if x_aquaterra_token:
        return x_aquaterra_token.strip()
    if aquaterra_session:
        return aquaterra_session.strip()
    return None


def get_usuario_actual(
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
    sesiones: Annotated[GestorSesiones, Depends(get_gestor_sesiones)],
    token: Annotated[str | None, Depends(extraer_token)],
) -> Usuario:
    with contenedor.conexion.bloqueo():
        usuario_id = sesiones.obtener_usuario_id(token, conexion=contenedor.conexion)
        if usuario_id is None:
            raise ErrorSesionExpirada()
        try:
            usuario = RepositorioUsuarios(contenedor.conexion).obtener(usuario_id)
        except EntidadNoEncontrada as exc:
            sesiones.revocar(token, conexion=contenedor.conexion)
            raise ErrorSesionExpirada() from exc
        if not usuario.activo:
            sesiones.revocar(token, conexion=contenedor.conexion)
            raise ErrorSesionExpirada("Tu cuenta está desactivada. Contacta al administrador.")
        return usuario


def exigir_admin(actor: Usuario, accion: str) -> None:
    if not actor.es_admin:
        raise ErrorPermiso(accion)
