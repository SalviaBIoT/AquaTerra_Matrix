"""Lanzador unificado de AquaTerra Matrix v6.0 (PyWebView nativo, ``--web`` o ``--legacy-ui``)."""

from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from typing import TYPE_CHECKING

import uvicorn

from aquaterra import __version__
from aquaterra.api import crear_app
from aquaterra.application.contenedor import construir_contenedor
from aquaterra.config import RAIZ_PROYECTO, RAIZ_RECURSOS

if TYPE_CHECKING:
    from aquaterra.application.contenedor import Contenedor


def buscar_puerto_libre(host: str = "127.0.0.1") -> int:
    """Reserva brevemente un puerto TCP libre en localhost para evitar colisiones."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def esperar_api_lista(url_salud: str, timeout_s: float = 10.0) -> bool:
    """Espera activamente hasta que ``/api/health`` responda HTTP 200."""
    limite = time.monotonic() + timeout_s
    while time.monotonic() < limite:
        try:
            with urllib.request.urlopen(url_salud, timeout=0.6) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.1)
    return False


def _asegurar_flujos_sin_consola() -> None:
    """Evita fallos de ``uvicorn``/``logging`` cuando ``pythonw.exe`` ejecuta sin consola."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        ruta_log = RAIZ_PROYECTO / "data" / "runtime" / "aquaterra_desktop.log"
        ruta_log.parent.mkdir(parents=True, exist_ok=True)
        stream = open(ruta_log, "a", encoding="utf-8", buffering=1)  # noqa: SIM115
    except OSError:
        stream = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream


class ServidorLocalEmbebido:
    """Administra Uvicorn en un hilo daemon junto al ``Contenedor`` compartido."""

    def __init__(self, contenedor: Contenedor, host: str = "127.0.0.1", port: int = 8765) -> None:
        _asegurar_flujos_sin_consola()
        self.contenedor = contenedor
        self.host = host
        self.port = port
        self.app = crear_app(contenedor)
        tiene_tty = bool(sys.stdout is not None and getattr(sys.stdout, "isatty", lambda: False)())
        self.config = uvicorn.Config(
            self.app,
            host=host,
            port=port,
            log_level="warning",
            access_log=False,
            use_colors=tiene_tty,
        )
        self.server = uvicorn.Server(self.config)
        self._thread = threading.Thread(target=self.server.run, name="AquaTerra-API", daemon=True)

    @property
    def url_base(self) -> str:
        return f"http://{self.host}:{self.port}"

    def iniciar(self, timeout_s: float = 10.0) -> None:
        self._thread.start()
        if not esperar_api_lista(f"{self.url_base}/api/health", timeout_s=timeout_s):
            self.detener()
            raise RuntimeError(f"El servidor local no respondió a tiempo en {self.url_base}.")

    def detener(self) -> None:
        self.server.should_exit = True
        if self._thread.is_alive():
            self._thread.join(timeout=3.0)


def parsear_argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="aquaterra",
        description=f"AquaTerra Matrix v{__version__} · Telemetría y Control Hidráulico",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Inicia el servidor local y abre la interfaz web en el navegador predeterminado.",
    )
    parser.add_argument(
        "--legacy-ui",
        action="store_true",
        help="Ejecuta la interfaz de escritorio clásica basada en Tkinter / ttkbootstrap.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Con --web, evita abrir automáticamente una pestaña del navegador.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Interfaz de escucha HTTP local (por defecto 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Puerto HTTP local (0 selecciona puerto libre en modo nativo o 8765 en --web).",
    )
    return parser.parse_args(argv)


def _ejecutar_pywebview(url_base: str) -> None:
    import webview  # import perezoso para no requerir GUI en pruebas headless

    icono = RAIZ_RECURSOS / "aquaterra" / "ui" / "assets" / "aquaterra.ico"
    perfil = RAIZ_PROYECTO / "data" / "runtime" / "webview_profile"
    perfil.mkdir(parents=True, exist_ok=True)

    webview.create_window(
        title=f"AquaTerra Matrix v{__version__}",
        url=url_base,
        width=1380,
        height=860,
        min_size=(1024, 680),
        background_color="#0A0E0C",
    )
    webview.start(
        icon=str(icono) if icono.is_file() else None,
        private_mode=False,
        storage_path=str(perfil),
    )


def _servidor_ya_activo(url_base: str) -> bool:
    try:
        with urllib.request.urlopen(f"{url_base}/api/health", timeout=0.6) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def ejecutar(argv: list[str] | None = None) -> None:
    """Punto de entrada principal de AquaTerra Matrix v6.0."""
    _asegurar_flujos_sin_consola()
    args = parsear_argumentos(argv)

    if args.legacy_ui:
        from aquaterra.ui.app import ejecutar as ejecutar_legacy

        ejecutar_legacy()
        return

    puerto = args.port
    if puerto <= 0:
        puerto = 8765 if args.web else buscar_puerto_libre(args.host)

    if args.web and _servidor_ya_activo(f"http://{args.host}:{puerto}"):
        if not args.no_browser:
            webbrowser.open(f"http://{args.host}:{puerto}")
        return

    contenedor = construir_contenedor()
    servidor = ServidorLocalEmbebido(contenedor, host=args.host, port=puerto)
    try:
        servidor.iniciar()
        contenedor.copiloto.orquestador.precalentar_ollama_async()
        if args.web:
            print(f"AquaTerra Matrix v{__version__} disponible en {servidor.url_base}")
            if not args.no_browser:
                webbrowser.open(servidor.url_base)
            try:
                while True:
                    time.sleep(0.5)
            except KeyboardInterrupt:
                print("\nDeteniendo AquaTerra Matrix…")
        else:
            _ejecutar_pywebview(servidor.url_base)
    finally:
        servidor.detener()
        contenedor.cerrar()


if __name__ == "__main__":
    ejecutar()
