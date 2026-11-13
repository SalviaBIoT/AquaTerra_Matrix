"""Controlador principal de la interfaz (resuelve DT-05a: doble ``mainloop``).

v3.2 creaba un ``ttk.Window`` para el login, lo ocultaba con ``withdraw()`` y
lanzaba un segundo ``mainloop()`` sobre un ``Toplevel`` huérfano. Resultado:
dos bucles de eventos Tcl anidados, cierres fantasma y "Cerrar sesión" que
terminaba el proceso en lugar de volver al login.

Ahora existe UNA sola raíz y UN solo ``mainloop()``. Cada pantalla es un
``ttk.Frame`` que se monta/desmonta dentro de la raíz; al desmontar, la vista
libera sus recursos (p. ej. figuras Matplotlib) en su propio ``destroy()``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from tkinter import messagebox

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH

from aquaterra import __version__
from aquaterra.application.contenedor import Contenedor, construir_contenedor
from aquaterra.core.domain import ErrorDominio, Usuario

log = logging.getLogger(__name__)


class AplicacionMatrix:
    def __init__(self, contenedor: Contenedor):
        self.contenedor = contenedor
        self.usuario: Usuario | None = None
        self.raiz = ttk.Window(themename=contenedor.config.tema_ui)
        self.raiz.protocol("WM_DELETE_WINDOW", self.salir)
        self._vista: ttk.Frame | None = None
        self.mostrar_login()

    # ── Navegación ────────────────────────────────────────────────────────────
    def _montar(self, fabrica: Callable[[], ttk.Frame], titulo: str, geometria: str, redimensionable: bool = True):
        if self._vista is not None:
            self._vista.destroy()
        self.raiz.title(f"{titulo} — AquaTerra Matrix v{__version__}")
        self.raiz.geometry(geometria)
        self.raiz.resizable(redimensionable, redimensionable)
        self._vista = fabrica()
        self._vista.pack(fill=BOTH, expand=True)

    def mostrar_login(self) -> None:
        from aquaterra.ui.views.login_view import VistaLogin
        self._montar(lambda: VistaLogin(self.raiz, self), "Acceso", "800x600", redimensionable=False)

    def mostrar_dashboard(self) -> None:
        from aquaterra.ui.views.dashboard_view import VistaDashboard
        self._montar(lambda: VistaDashboard(self.raiz, self), "Panel de Control", "800x600")

    def mostrar_parcelas(self) -> None:
        from aquaterra.ui.views.parcelas_view import VistaParcelas
        self._montar(lambda: VistaParcelas(self.raiz, self), "Gestión de Parcelas", "1150x680")

    def mostrar_riego(self) -> None:
        from aquaterra.ui.views.riegos_view import VistaRiego
        self._montar(lambda: VistaRiego(self.raiz, self), "Programación de Riego", "980x520")

    def mostrar_monitor(self) -> None:
        from aquaterra.ui.views.monitor_view import VistaMonitor
        self._montar(lambda: VistaMonitor(self.raiz, self), "Monitor y Gráficos", "1100x700")

    # ── Sesión ────────────────────────────────────────────────────────────────
    def al_autenticar(self, usuario: Usuario) -> None:
        self.usuario = usuario
        self.mostrar_dashboard()

    def cerrar_sesion(self) -> None:
        self.usuario = None
        self.mostrar_login()

    @property
    def actor(self) -> Usuario:
        if self.usuario is None:
            raise RuntimeError("No hay sesión activa.")
        return self.usuario

    # ── Utilidades de vista ───────────────────────────────────────────────────
    def ejecutar_accion(self, accion: Callable[[], object], *, titulo_error: str = "Operación no realizada"):
        """Ejecuta un caso de uso mostrando errores de dominio de forma amigable.

        Devuelve el resultado de la acción o ``None`` si falló.
        """
        try:
            return accion()
        except ErrorDominio as error:
            messagebox.showerror(titulo_error, str(error), parent=self.raiz)
        except Exception:  # Defecto de software: se registra con traza completa
            log.exception("Fallo inesperado en la interfaz")
            messagebox.showerror("Error interno", "Ocurrió un error inesperado. Revise el log.", parent=self.raiz)
        return None

    def salir(self) -> None:
        if self._vista is not None:
            self._vista.destroy()
            self._vista = None
        self.raiz.destroy()

    def ejecutar(self) -> None:
        self.raiz.mainloop()  # ÚNICO bucle de eventos de toda la aplicación


def ejecutar() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    contenedor = construir_contenedor()
    try:
        AplicacionMatrix(contenedor).ejecutar()
    finally:
        contenedor.cerrar()
        log.info("AquaTerra Matrix cerrado limpiamente.")
