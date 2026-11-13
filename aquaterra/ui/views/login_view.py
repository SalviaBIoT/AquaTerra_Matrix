"""Pantalla de acceso con fondo paisajístico."""

from __future__ import annotations

import logging
from tkinter import Canvas
from typing import TYPE_CHECKING

import ttkbootstrap as ttk
from PIL import Image, ImageTk
from ttkbootstrap.constants import BOTH

from aquaterra import __autor__, __version__

if TYPE_CHECKING:
    from aquaterra.ui.app import AplicacionMatrix

log = logging.getLogger(__name__)
ANCHO, ALTO = 800, 600


class VistaLogin(ttk.Frame):
    def __init__(self, maestro, app: AplicacionMatrix):
        super().__init__(maestro)
        self.app = app
        self._imagen_fondo: ImageTk.PhotoImage | None = None  # referencia viva para Tk
        self._construir()

    def _construir(self) -> None:
        ruta = self.app.contenedor.config.ruta_assets / "paisajeriego.png"
        try:
            with Image.open(ruta) as original:
                self._imagen_fondo = ImageTk.PhotoImage(
                    original.resize((ANCHO, ALTO), Image.Resampling.LANCZOS), master=self
                )
        except OSError as exc:
            log.warning("No se pudo cargar el fondo %s: %s", ruta, exc)

        lienzo = Canvas(self, width=ANCHO, height=ALTO, highlightthickness=0, bg="#2b3e50")
        lienzo.pack(fill=BOTH, expand=True)
        if self._imagen_fondo:
            lienzo.create_image(0, 0, image=self._imagen_fondo, anchor="nw")

        lienzo.create_text(400, 50, text="AquaTerra Matrix", font=("Helvetica", 28, "bold"), fill="white")
        lienzo.create_text(400, 88, text="Administración Ecológica, Agrícola y Bio-IoT · Ecosistema TerraBit",
                           font=("Helvetica", 12), fill="white")
        lienzo.create_rectangle(250, 180, 550, 480, fill="#1a1a1a", stipple="gray50", outline="")

        lienzo.create_text(400, 210, text="Usuario:", font=("Helvetica", 12), fill="white")
        self.entrada_usuario = ttk.Entry(lienzo, font=("Helvetica", 12), width=25)
        lienzo.create_window(400, 240, window=self.entrada_usuario)

        lienzo.create_text(400, 290, text="Contraseña:", font=("Helvetica", 12), fill="white")
        self.entrada_clave = ttk.Entry(lienzo, font=("Helvetica", 12), show="•", width=25)
        lienzo.create_window(400, 320, window=self.entrada_clave)

        boton = ttk.Button(lienzo, text="INICIAR SESIÓN", bootstyle="success", width=20, command=self._ingresar)
        lienzo.create_window(400, 400, window=boton)

        lienzo.create_text(400, 560, text=f"v{__version__} · Core SQLite", font=("Arial", 10), fill="white")
        lienzo.create_text(400, 580, text=f"Arquitectura y desarrollo: {__autor__}", font=("Arial", 10), fill="white")

        # Usabilidad: Enter para enviar y foco inicial en el usuario.
        self.entrada_usuario.bind("<Return>", lambda _e: self.entrada_clave.focus_set())
        self.entrada_clave.bind("<Return>", lambda _e: self._ingresar())
        self.after_idle(self.entrada_usuario.focus_set)

    def _ingresar(self) -> None:
        usuario = self.app.ejecutar_accion(
            lambda: self.app.contenedor.auth.iniciar_sesion(self.entrada_usuario.get(), self.entrada_clave.get()),
            titulo_error="Error de acceso",
        )
        if usuario is None:
            self.entrada_clave.delete(0, "end")
            return
        self.app.al_autenticar(usuario)
