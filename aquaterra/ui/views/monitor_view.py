"""Monitor gráfico de humedad y consumo hídrico (resuelve DT-04: fuga de memoria).

v3.2 usaba ``plt.subplots()``: cada figura queda registrada en el gestor global
de ``pyplot`` (``Gcf``) y NUNCA se liberaba al cerrar la ventana, acumulando RAM
en cada apertura del monitor. Además ``plt.xticks()`` actuaba sobre "la figura
actual" global, no necesariamente la propia.

Ahora se usa la API orientada a objetos (``matplotlib.figure.Figure``), que no
se registra en ``pyplot``; y ``destroy()`` desmonta los lienzos y limpia las
figuras explícitamente para que el recolector de basura las libere.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import ttkbootstrap as ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from ttkbootstrap.constants import BOTH

from aquaterra.core.agronomia.hidrico import UMBRAL_CRITICO_PCT

if TYPE_CHECKING:
    from aquaterra.ui.app import AplicacionMatrix

_ROJO, _VERDE, _AZUL = "#d9534f", "#5cb85c", "#0275d8"


class VistaMonitor(ttk.Frame):
    def __init__(self, maestro, app: AplicacionMatrix):
        super().__init__(maestro)
        self.app = app
        self._lienzos: list[FigureCanvasTkAgg] = []
        self._construir()
        self._graficar_humedad()
        self._graficar_consumo()

    def _construir(self) -> None:
        self.columnconfigure((0, 1), weight=1)
        self.rowconfigure(0, weight=1)
        self.marco_izq = ttk.Labelframe(self, text="Estado Actual de Humedad del Suelo", padding=10, bootstyle="info")
        self.marco_izq.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.marco_der = ttk.Labelframe(self, text="Consumo Acumulado de Agua (Litros)", padding=10,
                                        bootstyle="success")
        self.marco_der.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        ttk.Button(self, text="Volver al Menú Principal", bootstyle="secondary-outline", width=25,
                   command=self.app.mostrar_dashboard).grid(row=1, column=0, columnspan=2, pady=15)

    def _incrustar(self, figura: Figure, maestro: ttk.Labelframe) -> None:
        lienzo = FigureCanvasTkAgg(figura, master=maestro)
        lienzo.draw()
        lienzo.get_tk_widget().pack(fill=BOTH, expand=True)
        self._lienzos.append(lienzo)

    def _graficar_humedad(self) -> None:
        datos = self.app.ejecutar_accion(self.app.contenedor.monitor.humedad_por_parcela) or []
        if not datos:
            ttk.Label(self.marco_izq, text="No hay parcelas activas.").pack(expand=True)
            return
        nombres, humedades = zip(*datos, strict=True)
        figura = Figure(figsize=(5, 4), dpi=100)
        eje = figura.add_subplot()
        colores = [_ROJO if h < UMBRAL_CRITICO_PCT else _VERDE for h in humedades]
        barras = eje.bar(nombres, humedades, color=colores)
        eje.axhline(UMBRAL_CRITICO_PCT, color=_ROJO, linestyle="--", linewidth=1,
                    label=f"Umbral crítico {UMBRAL_CRITICO_PCT:.0f} %")
        eje.set_ylim(0, 100)
        eje.set_ylabel("Humedad volumétrica relativa (%)")
        eje.set_title("Niveles de Humedad por Parcela", fontsize=10)
        eje.tick_params(axis="x", labelrotation=15, labelsize=8)
        eje.bar_label(barras, fmt="%.0f", padding=3)
        eje.legend(fontsize=7, loc="upper right")
        figura.tight_layout()
        self._incrustar(figura, self.marco_izq)

    def _graficar_consumo(self) -> None:
        datos = self.app.ejecutar_accion(self.app.contenedor.monitor.consumo_por_parcela) or []
        if not datos:
            ttk.Label(self.marco_der, text="No hay registros de riego aún.").pack(expand=True)
            return
        nombres, litros = zip(*datos, strict=True)
        figura = Figure(figsize=(5, 4), dpi=100)
        eje = figura.add_subplot()
        barras = eje.bar(nombres, litros, color=_AZUL)
        eje.set_ylabel("Litros totales")
        eje.set_title("Riego Total Acumulado por Parcela", fontsize=10)
        eje.tick_params(axis="x", labelrotation=15, labelsize=8)
        eje.bar_label(barras, fmt="%.0f", padding=3)
        figura.tight_layout()
        self._incrustar(figura, self.marco_der)

    def destroy(self) -> None:
        for lienzo in self._lienzos:
            lienzo.get_tk_widget().destroy()
            lienzo.figure.clear()
        self._lienzos.clear()
        super().destroy()
