"""Fábrica de la aplicación FastAPI local y montaje del frontend compilado."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from aquaterra import __version__
from aquaterra.api.deps import GestorSesiones
from aquaterra.api.routers import auth, copiloto, estaciones, hardware, parcelas, riego, sistema
from aquaterra.application.contenedor import Contenedor, construir_contenedor
from aquaterra.config import RAIZ_RECURSOS
from aquaterra.core.domain import (
    EntidadNoEncontrada,
    ErrorAutenticacion,
    ErrorDominio,
    ErrorPermiso,
    ErrorSesionExpirada,
    ErrorValidacion,
)


def crear_app(
    contenedor: Contenedor | None = None,
    *,
    static_dir: Path | None = None,
) -> FastAPI:
    """Construye la API local 1:1 sobre ``Contenedor`` y opcionalmente sirve ``frontend/dist``."""
    propio_contenedor = contenedor is None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if propio_contenedor:
            app.state.contenedor = construir_contenedor()
        else:
            app.state.contenedor = contenedor
        yield
        if propio_contenedor and app.state.contenedor is not None:
            app.state.contenedor.cerrar()

    app = FastAPI(
        title="SalviaBIoT Local API",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.contenedor = contenedor
    app.state.sesiones = GestorSesiones()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:8765",
            "http://localhost:8765",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ErrorAutenticacion)
    async def _err_auth(_req: Request, exc: ErrorAutenticacion) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": str(exc), "codigo": "credenciales_invalidas"})

    @app.exception_handler(ErrorSesionExpirada)
    async def _err_sesion(_req: Request, exc: ErrorSesionExpirada) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": str(exc), "codigo": "sesion_expirada"})

    @app.exception_handler(ErrorPermiso)
    async def _err_perm(_req: Request, exc: ErrorPermiso) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(EntidadNoEncontrada)
    async def _err_not_found(_req: Request, exc: EntidadNoEncontrada) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ErrorValidacion)
    async def _err_val(_req: Request, exc: ErrorValidacion) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": str(exc), "problemas": exc.problemas},
        )

    @app.exception_handler(ErrorDominio)
    async def _err_dom(_req: Request, exc: ErrorDominio) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    for router in (
        auth.router,
        estaciones.router,
        parcelas.router,
        riego.router,
        copiloto.router,
        hardware.router,
        sistema.router,
    ):
        app.include_router(router)

    dist = static_dir or (RAIZ_RECURSOS / "frontend" / "dist")
    if dist.exists() and (dist / "index.html").is_file():
        assets_dir = dist / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")

        index_html = dist / "index.html"

        @app.get("/{full_path:path}", include_in_schema=False)
        async def _spa_fallback(full_path: str):
            if full_path.startswith("api/"):
                return JSONResponse(status_code=404, content={"detail": "Ruta API no encontrada."})
            candidato = (dist / full_path).resolve()
            if full_path and candidato.is_file() and str(candidato).startswith(str(dist.resolve())):
                return FileResponse(candidato)
            return FileResponse(index_html)

    return app
