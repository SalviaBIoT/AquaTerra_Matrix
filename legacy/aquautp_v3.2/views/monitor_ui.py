import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from models.data_manager import GestorDatos
import pandas as pd


class VentanaMonitor:
    def __init__(self, ventana_padre):
        self.padre = ventana_padre

        self.ventana = ttk.Toplevel(ventana_padre)
        self.ventana.title("Monitor y Gráficos - AquaUTP")
        self.ventana.geometry("1100x700")

        # Configuración del protocolo de cierre para retornar al menú principal correctamente
        self.ventana.protocol("WM_DELETE_WINDOW", self._al_cerrar_ventana)

        self.gestor = GestorDatos()

        self._configurar_interfaz()
        self._generar_graficos()

    def _configurar_interfaz(self):
        """Diseño y distribución de los paneles gráficos."""

        # Configuración de la cuadrícula principal
        self.ventana.columnconfigure(0, weight=1)
        self.ventana.columnconfigure(1, weight=1)
        self.ventana.rowconfigure(0, weight=1)  # Área de gráficos con expansión
        self.ventana.rowconfigure(1, weight=0)  # Área de botones fija

        # Panel Izquierdo: Visualización de humedad
        self.marco_izquierdo = ttk.Labelframe(self.ventana, text="Estado Actual de Humedad", padding=10,
                                              bootstyle="info")
        self.marco_izquierdo.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # Panel Derecho: Visualización de consumo
        self.marco_derecho = ttk.Labelframe(self.ventana, text="Consumo Acumulado de Agua (Litros)", padding=10,
                                            bootstyle="success")
        self.marco_derecho.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        # Botón de retorno
        boton_volver = ttk.Button(
            self.ventana,
            text="Volver al Menú Principal",
            bootstyle="secondary-outline",
            command=self._al_cerrar_ventana,
            width=25
        )
        boton_volver.grid(row=1, column=0, columnspan=2, pady=15)

    def _generar_graficos(self):
        """Método orquestador para la creación de las visualizaciones."""
        self._grafico_humedad_actual()
        self._grafico_consumo_agua()

    def _grafico_humedad_actual(self):
        """Generación del gráfico de barras para la humedad por parcela."""
        datos = self.gestor.cargar_parcelas()

        if datos is not None and not datos.empty:
            # Extracción de datos para los ejes
            nombres = datos['nombre'].tolist()
            humedades = datos['humedad'].tolist()

            # Configuración de la figura y ejes
            figura, eje = plt.subplots(figsize=(5, 4), dpi=100)

            # Lógica de colores: Rojo para niveles críticos (<40), Verde para niveles óptimos
            colores = ['#d9534f' if h < 40 else '#5cb85c' for h in humedades]

            barras = eje.bar(nombres, humedades, color=colores)

            # Ajustes estéticos
            eje.set_ylim(0, 100)
            eje.set_ylabel("Humedad (%)")
            eje.set_title("Niveles de Humedad en Tiempo Real", fontsize=10)

            # Rotación de etiquetas para mejorar legibilidad
            plt.xticks(rotation=15, ha='right', fontsize=8)

            # Etiquetas de valor sobre las barras
            eje.bar_label(barras, padding=3)

            plt.tight_layout()

            # Integración del gráfico en la interfaz Tkinter
            lienzo = FigureCanvasTkAgg(figura, master=self.marco_izquierdo)
            lienzo.draw()
            lienzo.get_tk_widget().pack(fill=BOTH, expand=True)

        else:
            # Mensaje en caso de no haber datos
            ttk.Label(self.marco_izquierdo, text="No hay datos de parcelas disponibles.").pack(expand=True)

    def _grafico_consumo_agua(self):
        """Generación del gráfico horizontal de consumo acumulado."""
        historial = self.gestor.cargar_historial_riegos()

        if historial:
            # Conversión a DataFrame para facilitar el agrupamiento
            df_riegos = pd.DataFrame(historial)

            # Sumatoria de litros por nombre de parcela
            consumo_por_parcela = df_riegos.groupby('nombre_parcela')['agua_litros'].sum()

            # Preparación de datos
            nombres = consumo_por_parcela.index.tolist()
            litros = consumo_por_parcela.values.tolist()

            # Configuración de la figura
            figura, eje = plt.subplots(figsize=(5, 4), dpi=100)

            # Gráfico de barras horizontales
            barras = eje.bar(nombres, litros, color='#0275d8')

            eje.set_xlabel("Litros Totales", fontsize=8, color="green")
            eje.set_title("Riego Total Acumulado por Parcela", fontsize=8, color="green")
            eje.bar_label(barras, padding=3)

            plt.tight_layout()

            # Integración del gráfico
            lienzo = FigureCanvasTkAgg(figura, master=self.marco_derecho)
            lienzo.draw()
            lienzo.get_tk_widget().pack(fill=BOTH, expand=True)

        else:
            ttk.Label(self.marco_derecho, text="No hay registros de riego aún.").pack(expand=True)

    def _al_cerrar_ventana(self):
        self.ventana.destroy()
        self.padre.deiconify()