"""Pantalla de acceso v5.0 con identidad Bio-IoT TerraBit, tema dual y salida segura."""

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
ANCHO, ALTO = 900, 640


class VistaLogin(ttk.Frame):
    """Vista inicial de autenticación sobre clave PBKDF2-SHA256."""

    def __init__(self, maestro, app: AplicacionMatrix):
        super().__init__(maestro)
        self.app = app
        self._imagen_fondo: ImageTk.PhotoImage | None = None
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

        lienzo = Canvas(self, width=ANCHO, height=ALTO, highlightthickness=0, bg="#0b0f14")
        lienzo.pack(fill=BOTH, expand=True)
        if self._imagen_fondo:
            lienzo.create_image(0, 0, image=self._imagen_fondo, anchor="nw")

        lienzo.create_text(
            450, 56, text="AQUATERRA MATRIX", font=("Segoe UI", 30, "bold"), fill="#f1f5f9"
        )
        lienzo.create_text(
            450,
            96,
            text="Centro de Mando Agronómico, Ecológico y Bio-IoT · Ecosistema TerraBit",
            font=("Segoe UI", 11),
            fill="#cbd5e1",
        )

        # Tarjeta translúcida central
        lienzo.create_rectangle(
            275, 155, 625, 515, fill="#0b0f14", stipple="gray75", outline="#10b981", width=2
        )

        lienzo.create_text(
            450, 192, text="Acceso Operativo Híbrido", font=("Segoe UI", 14, "bold"), fill="#10b981"
        )
        lienzo.create_text(
            450, 215, text="SQLite3 WAL Local-First · PBKDF2-SHA256", font=("Segoe UI", 9), fill="#94a3b8"
        )

        lienzo.create_text(450, 250, text="Usuario", font=("Segoe UI", 10, "bold"), fill="#f1f5f9")
        self.entrada_usuario = ttk.Entry(lienzo, font=("Segoe UI", 11), width=28)
        lienzo.create_window(450, 278, window=self.entrada_usuario)

        lienzo.create_text(450, 322, text="Contraseña", font=("Segoe UI", 10, "bold"), fill="#f1f5f9")
        self.entrada_clave = ttk.Entry(lienzo, font=("Segoe UI", 11), show="•", width=28)
        lienzo.create_window(450, 350, window=self.entrada_clave)

        btn_login = ttk.Button(
            lienzo,
            text="🔓 INICIAR SESIÓN",
            bootstyle="success",
            width=26,
            command=self._ingresar,
        )
        lienzo.create_window(450, 408, window=btn_login)

        btn_tema = ttk.Button(
            lienzo,
            text="☀️/🌙 Tema",
            bootstyle="secondary-outline",
            width=12,
            command=self.app.alternar_tema,
        )
        lienzo.create_window(382, 464, window=btn_tema)

        btn_salir = ttk.Button(
            lienzo,
            text="⏻ Salir",
            bootstyle="danger-outline",
            width=12,
            command=self.app.salir,
        )
        lienzo.create_window(518, 464, window=btn_salir)

        lienzo.create_text(
            450,
            584,
            text=f"v{__version__} · Core SQLite3 WAL + IA Híbrida + Gateway nRF24L01+",
            font=("Segoe UI", 9),
            fill="#cbd5e1",
        )
        lienzo.create_text(
            450,
            606,
            text=f"Arquitectura y desarrollo: {__autor__}",
            font=("Segoe UI", 9),
            fill="#94a3b8",
        )

        self.entrada_usuario.bind("<Return>", lambda _e: self.entrada_clave.focus_set())
        self.entrada_clave.bind("<Return>", lambda _e: self._ingresar())
        self.after_idle(self.entrada_usuario.focus_set)

    def _ingresar(self) -> None:
        usuario = self.app.ejecutar_accion(
            lambda: self.app.contenedor.auth.iniciar_sesion(
                self.entrada_usuario.get(), self.entrada_clave.get()
            ),
            titulo_error="Error de acceso",
        )
        if usuario is None:
            self.entrada_clave.delete(0, "end")
            return
        self.app.al_autenticar(usuario)
