"""Router de autenticación, sesión actual y gestión de usuarios."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from aquaterra.api.deps import (
    COOKIE_SESION,
    GestorSesiones,
    extraer_token,
    get_contenedor,
    get_gestor_sesiones,
    get_usuario_actual,
)
from aquaterra.api.schemas import (
    CambiarClaveRequest,
    CrearUsuarioRequest,
    LoginRequest,
    serializar_objeto,
)
from aquaterra.application.contenedor import Contenedor
from aquaterra.core.domain import ErrorValidacion, Rol, Usuario

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/auth/login")
def login(
    body: LoginRequest,
    response: Response,
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
    sesiones: Annotated[GestorSesiones, Depends(get_gestor_sesiones)],
) -> dict[str, object]:
    usuario = contenedor.auth.iniciar_sesion(body.usuario, body.clave)
    token = sesiones.crear(usuario.id, conexion=contenedor.conexion)
    response.set_cookie(
        key=COOKIE_SESION,
        value=token,
        httponly=True,
        samesite="lax",
    )
    return {"token": token, "usuario": serializar_objeto(usuario)}


@router.post("/auth/logout")
def logout(
    response: Response,
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
    sesiones: Annotated[GestorSesiones, Depends(get_gestor_sesiones)],
    token: Annotated[str | None, Depends(extraer_token)],
) -> dict[str, bool]:
    sesiones.revocar(token, conexion=contenedor.conexion)
    response.delete_cookie(COOKIE_SESION)
    return {"ok": True}


@router.get("/auth/me")
def me(usuario: Annotated[Usuario, Depends(get_usuario_actual)]) -> dict[str, object]:
    return {"usuario": serializar_objeto(usuario)}


@router.get("/usuarios")
def listar_usuarios(
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, object]:
    return {"usuarios": serializar_objeto(contenedor.auth.listar_usuarios())}


@router.post("/usuarios", status_code=201)
def crear_usuario(
    body: CrearUsuarioRequest,
    actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, object]:
    try:
        rol = Rol(body.rol)
    except ValueError as exc:
        raise ErrorValidacion(f"Rol inválido: '{body.rol}'.") from exc
    nuevo = contenedor.auth.crear_usuario(
        actor,
        usuario=body.usuario,
        nombre=body.nombre,
        clave=body.clave,
        rol=rol,
    )
    return {"usuario": serializar_objeto(nuevo)}


@router.post("/usuarios/{usuario_id}/clave")
def cambiar_clave(
    usuario_id: int,
    body: CambiarClaveRequest,
    actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, bool]:
    contenedor.auth.cambiar_clave(actor, usuario_id=usuario_id, nueva_clave=body.nueva_clave)
    return {"ok": True}
