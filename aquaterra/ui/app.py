"""Controlador principal de la interfaz (*App Shell* sobre ventana raíz única, DT-05a).

v5.0 evoluciona las ventanas sueltas a un marco de mando persistente
(``AppShell``) con ``Top Command Bar``, ``Sidebar``, ``Workspace`` central y
``Status Footer``, conservando una sola raíz ``Tk`` y un único ``mainloop()``.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable
from tkinter import messagebox

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH

from aquaterra import __version__
from aquaterra.application.contenedor import Contenedor, construir_contenedor
from aquaterra.core.domain import ErrorDominio, Usuario
from aquaterra.ui.shell import AppShell
from aquaterra.ui.tema import (
    TEMA_CLARO,
    TEMA_OSCURO,
    configurar_estilos_shell,
    registrar_temas_aquaterra,
)

log = logging.getLogger(__name__)


class AplicacionMatrix:
    """Orquestador de la ventana única y ciclo de vida de las 7 vistas v5.0."""

    def __init__(self, contenedor: Contenedor):
        self.contenedor = contenedor
        self.usuario: Usuario | None = None
        self.estacion_activa_id: int | None = None
        self._ruta_actual: str = "dashboard"
        self._shell: AppShell | None = None
        self._vista: ttk.Frame | None = None

        # ttkbootstrap valida `themename` en Window.__init__ antes de registrar temas propios:
        # arrancamos sobre "bootstrap-dark" y registramos inmediatamente `aquaterra-dark/light`.
        self.raiz = ttk.Window(themename="bootstrap-dark")
        try:
            registrar_temas_aquaterra(self.raiz.style)
            tema_inicial = contenedor.config.tema_ui
            if tema_inicial not in set(self.raiz.style.theme_names()):
                tema_inicial = TEMA_OSCURO
            self.raiz.style.theme_use(tema_inicial)
            configurar_estilos_shell(self.raiz.style)
            self.raiz.protocol("WM_DELETE_WINDOW", self.salir)
            self.raiz.minsize(960, 620)
            self.mostrar_login()
        except Exception:
            with contextlib.suppress(Exception):
                self.raiz.destroy()
            raise

    # ── Navegación ────────────────────────────────────────────────────────────
    def _asegurar_shell(self) -> AppShell:
        if self._shell is None or not self._shell.winfo_exists():
            if self._vista is not None:
                self._vista.destroy()
                self._vista = None
            self._shell = AppShell(self.raiz, self)
            self._shell.pack(fill=BOTH, expand=True)
            self.raiz.geometry("1360x820")
            self.raiz.resizable(True, True)
        return self._shell

    def _montar_en_shell(
        self,
        clave_ruta: str,
        fabrica: Callable[[ttk.Frame], ttk.Frame],
        titulo: str,
    ) -> None:
        shell = self._asegurar_shell()
        if self._vista is not None:
            self._vista.destroy()
            self._vista = None
        self._ruta_actual = clave_ruta
        self.raiz.title(f"{titulo} — AquaTerra Matrix v{__version__}")
        shell.marcar_vista_activa(clave_ruta)
        self._vista = fabrica(shell.workspace)
        self._vista.pack(fill=BOTH, expand=True)

    def mostrar_login(self) -> None:
        from aquaterra.ui.views.login_view import VistaLogin

        if self._vista is not None:
            self._vista.destroy()
            self._vista = None
        if self._shell is not None:
            self._shell.destroy()
            self._shell = None

        self._ruta_actual = "login"
        self.raiz.title(f"Acceso — AquaTerra Matrix v{__version__}")
        self.raiz.geometry("900x640")
        self.raiz.resizable(False, False)
        self._vista = VistaLogin(self.raiz, self)
        self._vista.pack(fill=BOTH, expand=True)

    def mostrar_dashboard(self) -> None:
        from aquaterra.ui.views.dashboard_view import VistaDashboard

        self._montar_en_shell(
            "dashboard",
            lambda padre: VistaDashboard(padre, self),
            "Radar & Pulso 24h",
        )

    def mostrar_monitor(self) -> None:
        from aquaterra.ui.views.monitor_view import VistaMonitor

        self._montar_en_shell(
            "monitor",
            lambda padre: VistaMonitor(padre, self),
            "Telemetría Multi-Nodo",
        )

    def mostrar_parcelas(self) -> None:
        from aquaterra.ui.views.parcelas_view import VistaParcelas

        self._montar_en_shell(
            "parcelas",
            lambda padre: VistaParcelas(padre, self),
            "Parcelas & Cultivos",
        )

    def mostrar_riego(self) -> None:
        from aquaterra.ui.views.riegos_view import VistaRiego

        self._montar_en_shell(
            "riego",
            lambda padre: VistaRiego(padre, self),
            "Control, 5 Candados & Riego",
        )

    def mostrar_copiloto(self) -> None:
        from aquaterra.ui.views.copiloto_view import VistaCopiloto

        self._montar_en_shell(
            "copiloto",
            lambda padre: VistaCopiloto(padre, self),
            "Copiloto IA & Calibración",
        )

    def mostrar_hardware(self) -> None:
        from aquaterra.ui.views.hardware_view import VistaHardware

        self._montar_en_shell(
            "hardware",
            lambda padre: VistaHardware(padre, self),
            "Gateway Radio nRF24L01+ & MicroSD",
        )

    def mostrar_configuracion(self) -> None:
        from aquaterra.ui.views.config_view import VistaConfiguracion

        self._montar_en_shell(
            "config",
            lambda padre: VistaConfiguracion(padre, self),
            "Nodos, Conectores & Usuarios",
        )

    def recargar_ruta_actual(self) -> None:
        mapa = {
            "login": self.mostrar_login,
            "dashboard": self.mostrar_dashboard,
            "monitor": self.mostrar_monitor,
            "parcelas": self.mostrar_parcelas,
            "riego": self.mostrar_riego,
            "copiloto": self.mostrar_copiloto,
            "hardware": self.mostrar_hardware,
            "config": self.mostrar_configuracion,
        }
        accion = mapa.get(self._ruta_actual, self.mostrar_dashboard)
        accion()

    # ── Tema Dual (Obsidian Bio-Tech <-> Field Daylight) ─────────────────────
    def alternar_tema(self) -> str:
        actual = self.raiz.style.theme_use()
        nuevo = TEMA_CLARO if actual != TEMA_CLARO else TEMA_OSCURO
        self.raiz.style.theme_use(nuevo)
        configurar_estilos_shell(self.raiz.style)
        if self._shell is not None and self._shell.winfo_exists():
            self._shell.refrescar_estado()
        if self._ruta_actual in ("monitor", "dashboard"):
            # Redibuja lienzos Matplotlib o tarjetas con la nueva paleta cromática
            self.recargar_ruta_actual()
        return nuevo

    def notificar_cambio_datos(self, mensaje: str = "", *, bootstyle: str = "info") -> None:
        if self._shell is not None and self._shell.winfo_exists():
            self._shell.recargar_estaciones()
            self._shell.refrescar_estado()
            if mensaje:
                self._shell.publicar_estado(mensaje, bootstyle=bootstyle)

    # ── Sesión ────────────────────────────────────────────────────────────────
    def al_autenticar(self, usuario: Usuario) -> None:
        self.usuario = usuario
        estaciones = self.contenedor.radar.listar_estaciones()
        self.estacion_activa_id = estaciones[0].id if estaciones else None
        self.mostrar_dashboard()

    def cerrar_sesion(self) -> None:
        self.usuario = None
        self.estacion_activa_id = None
        self.contenedor.sincronizacion.detener_worker_segundo_plano()
        self.mostrar_login()

    @property
    def actor(self) -> Usuario:
        if self.usuario is None:
            raise RuntimeError("No hay sesión activa.")
        return self.usuario

    # ── Utilidades de vista ───────────────────────────────────────────────────
    def ejecutar_accion(
        self, accion: Callable[[], object], *, titulo_error: str = "Operación no realizada"
    ):
        """Ejecuta un caso de uso mostrando errores de dominio de forma amigable."""
        try:
            return accion()
        except ErrorDominio as error:
            messagebox.showerror(titulo_error, str(error), parent=self.raiz)
        except Exception:
            log.exception("Fallo inesperado en la interfaz")
            messagebox.showerror(
                "Error interno",
                "Ocurrió un error inesperado. Revise el log.",
                parent=self.raiz,
            )
        return None

    def salir(self) -> None:
        self.contenedor.sincronizacion.detener_worker_segundo_plano()
        if self._vista is not None:
            self._vista.destroy()
            self._vista = None
        if self._shell is not None:
            self._shell.destroy()
            self._shell = None
        self.raiz.destroy()

    def ejecutar(self) -> None:
        self.raiz.mainloop()


def ejecutar() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    contenedor = construir_contenedor()
    try:
        AplicacionMatrix(contenedor).ejecutar()
    finally:
        contenedor.cerrar()
        log.info("AquaTerra Matrix cerrado limpiamente.")
