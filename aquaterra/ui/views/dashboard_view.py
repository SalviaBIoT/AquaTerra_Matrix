"""Panel de control principal (menú de módulos)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, LEFT, RIGHT, X

if TYPE_CHECKING:
    from aquaterra.ui.app import AplicacionMatrix


class VistaDashboard(ttk.Frame):
    def __init__(self, maestro, app: AplicacionMatrix):
        super().__init__(maestro)
        self.app = app
        self._construir()

    def _construir(self) -> None:
        usuario = self.app.actor
        encabezado = ttk.Frame(self, padding=20)
        encabezado.pack(fill=X)
        ttk.Label(encabezado, text=f"Bienvenido, {usuario.nombre}", font=("Helvetica", 16)).pack(side=LEFT)
        ttk.Label(encabezado, text=f"  rol: {usuario.rol.value}", bootstyle="secondary").pack(side=LEFT)
        ttk.Button(encabezado, text="Cerrar Sesión", bootstyle="danger-outline",
                   command=self.app.cerrar_sesion).pack(side=RIGHT)
        ttk.Separator(self).pack(fill=X, padx=20)

        menu = ttk.Frame(self, padding=40)
        menu.pack(expand=True, fill=BOTH)
        for i in range(2):
            menu.columnconfigure(i, weight=1)
            menu.rowconfigure(i, weight=1)

        botones = [
            ("GESTIONAR PARCELAS", "primary", self.app.mostrar_parcelas),
            ("PROGRAMAR RIEGO", "info", self.app.mostrar_riego),
            ("MONITOR Y GRÁFICOS", "success", self.app.mostrar_monitor),
            ("SALIR DEL SISTEMA", "danger", self.app.salir),
        ]
        for indice, (texto, estilo, accion) in enumerate(botones):
            ttk.Button(menu, text=texto, bootstyle=estilo, command=accion).grid(
                row=indice // 2, column=indice % 2, padx=10, pady=10, sticky="nsew"
            )
