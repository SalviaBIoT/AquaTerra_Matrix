"""Programación y ejecución manual de riego sobre ``ServicioRiego``.

- Las parcelas se identifican por id (v3.2 usaba el nombre como llave del combo).
- La fecha se captura como objeto ``date`` (``DateEntry.get_date()``), no como el
  texto dependiente del locale que producía ``11/27/25`` en v3.2.
"""

from __future__ import annotations

from tkinter import messagebox
from typing import TYPE_CHECKING

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTTOM, LEFT, RIGHT, W, X
from ttkbootstrap.widgets import DateEntry

from aquaterra.core.domain import Parcela

if TYPE_CHECKING:
    from aquaterra.ui.app import AplicacionMatrix


class VistaRiego(ttk.Frame):
    def __init__(self, maestro, app: AplicacionMatrix):
        super().__init__(maestro)
        self.app = app
        self.var_umbral = ttk.IntVar(value=45)
        self.var_parcela = ttk.StringVar()
        self.var_litros = ttk.IntVar(value=50)
        self._por_etiqueta: dict[str, int] = {}
        self._construir()
        self._cargar_parcelas()

    def _construir(self) -> None:
        self.columnconfigure((0, 1), weight=1)
        self.rowconfigure(0, weight=1)

        izq = ttk.Frame(self, padding=20)
        izq.grid(row=0, column=0, sticky="nsew")
        ttk.Label(izq, text="Seleccione Parcela (Riego Automático Activo):",
                  font=("Helvetica", 11, "bold")).pack(fill=X, anchor=W)
        self.combo = ttk.Combobox(izq, textvariable=self.var_parcela, state="readonly", font=("Helvetica", 10))
        self.combo.pack(fill=X, pady=(5, 20))
        self.combo.bind("<<ComboboxSelected>>", lambda _e: self._mostrar_info())

        marco_umbral = ttk.Labelframe(izq, text="Condición de Disparo", padding=20, bootstyle="info")
        marco_umbral.pack(fill=X)
        ttk.Label(marco_umbral, text="Activar si la humedad del suelo es menor a:", bootstyle="secondary").pack()
        self.lbl_umbral = ttk.Label(marco_umbral, text="45 %", font=("Helvetica", 40, "bold"), bootstyle="info")
        self.lbl_umbral.pack(pady=10)
        self.slider = ttk.Scale(marco_umbral, from_=0, to=100, variable=self.var_umbral, bootstyle="info",
                                command=lambda _v: self.lbl_umbral.config(text=f"{round(self.var_umbral.get())} %"))
        self.slider.pack(fill=X, pady=10)
        rango = ttk.Frame(marco_umbral)
        rango.pack(fill=X)
        ttk.Label(rango, text="0%").pack(side=LEFT)
        ttk.Label(rango, text="100%").pack(side=RIGHT)

        ttk.Frame(izq).pack(expand=True)
        ttk.Button(izq, text="⬅ Volver al Menú Principal", bootstyle="secondary-outline", width=25,
                   command=self.app.mostrar_dashboard).pack(side=BOTTOM, anchor=W, pady=10)

        der = ttk.Frame(self, padding=20)
        der.grid(row=0, column=1, sticky="nsew")
        self.lbl_info = ttk.Label(der, text="Seleccione una parcela...", font=("Arial", 11), wraplength=380,
                                  justify=LEFT, bootstyle="@secondary", padding=15)
        self.lbl_info.pack(fill=X, pady=(0, 20))

        grupo = ttk.Labelframe(der, text="Parámetros de Riego", padding=15)
        grupo.pack(fill=X)
        ttk.Label(grupo, text="Fecha (ISO-8601):").pack(anchor=W)
        self.calendario = DateEntry(grupo, bootstyle="success", date_format="%Y-%m-%d")
        self.calendario.pack(fill=X, pady=(5, 10))
        ttk.Label(grupo, text="Hora (HH:MM, 24 h):").pack(anchor=W)
        self.entrada_hora = ttk.Entry(grupo)
        self.entrada_hora.insert(0, "06:00")
        self.entrada_hora.pack(fill=X, pady=(5, 10))
        ttk.Label(grupo, text="Cantidad de Agua (Litros):", font=("Helvetica", 10, "bold")).pack(anchor=W)
        ttk.Spinbox(grupo, from_=1, to=5000, textvariable=self.var_litros, bootstyle="success").pack(
            fill=X, pady=(5, 5))

        self.btn_aplicar = ttk.Button(der, text="APLICAR RIEGO AHORA", bootstyle="success", command=self._aplicar)
        self.btn_aplicar.pack(fill=X, pady=20)
        if not self.app.actor.es_admin:
            self.btn_aplicar.configure(state="disabled")
            ttk.Label(der, text="Solo administradores pueden ejecutar riegos.", bootstyle="warning",
                      font=("Arial", 9)).pack(fill=X)

    @staticmethod
    def _etiqueta(p: Parcela) -> str:
        return f"#{p.id} · {p.nombre}"

    def _cargar_parcelas(self) -> None:
        parcelas = self.app.ejecutar_accion(
            lambda: self.app.contenedor.parcelas.listar(solo_riego_auto=True)) or []
        self._por_etiqueta = {self._etiqueta(p): p.id for p in parcelas}
        self.combo["values"] = list(self._por_etiqueta)
        if parcelas:
            self.combo.current(0)
            self._mostrar_info()
        else:
            self.combo.set("Sin parcelas con riego automático")
            self.slider.configure(state="disabled")
            self.btn_aplicar.configure(state="disabled")

    def _mostrar_info(self) -> None:
        pid = self._por_etiqueta.get(self.var_parcela.get())
        if pid is None:
            return
        p = self.app.ejecutar_accion(lambda: self.app.contenedor.parcelas.obtener(pid))
        if p:
            self.lbl_info.config(
                text=f"PARCELA: {p.nombre}  (id {p.id})\nCultivo: {p.cultivo} · Suelo: {p.tipo_suelo.value}\n"
                     f"Humedad actual: {p.humedad_pct:.0f} %",
                bootstyle="@info",
            )

    def _aplicar(self) -> None:
        pid = self._por_etiqueta.get(self.var_parcela.get())
        if pid is None:
            messagebox.showwarning("Atención", "Seleccione una parcela válida.", parent=self)
            return

        def caso_de_uso():
            fecha = self.calendario.get_date()
            return self.app.contenedor.riego.aplicar_riego(
                self.app.actor, parcela_id=pid, umbral_pct=round(self.var_umbral.get()),
                litros=self.var_litros.get(), fecha=fecha.date() if hasattr(fecha, "date") else fecha,
                hora=self.entrada_hora.get(),
            )

        resultado = self.app.ejecutar_accion(caso_de_uso)
        if resultado is None:
            return
        titulo = "Riego aplicado" if resultado.aplicado else "Riego no requerido"
        messagebox.showinfo(titulo, resultado.mensaje, parent=self)
        self._mostrar_info()
