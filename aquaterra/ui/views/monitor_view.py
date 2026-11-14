"""Vista 2 — Telemetría Multi-Nodo Adaptativa, Correlación Bivariada y Parcelas (DT-04).

Todas las gráficas se construyen con la API orientada a objetos de Matplotlib
(``matplotlib.figure.Figure``), se estilizan con ``paleta_activa`` y se liberan
explícitamente en ``_limpiar_lienzos()`` / ``destroy()`` para mantener cero fugas.
"""

from __future__ import annotations

import contextlib
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING

import ttkbootstrap as ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.dates import DateFormatter
from matplotlib.figure import Figure
from ttkbootstrap.constants import BOTH, LEFT, RIGHT, W, X

from aquaterra.core.agronomia.hidrico import UMBRAL_CRITICO_PCT
from aquaterra.core.domain import TipoEstacion
from aquaterra.ui.tema import estilizar_figura, paleta_activa

if TYPE_CHECKING:
    from aquaterra.ui.app import AplicacionMatrix

_VENTANAS_HORAS: dict[str, int] = {
    "Últimas 6h": 6,
    "Últimas 24h": 24,
    "Últimos 7 días": 168,
    "Todo el historial": 0,
}


class VistaMonitor(ttk.Frame):
    """Laboratorio visual multi-estación + comparativo de parcelas y consumo hídrico."""

    def __init__(self, maestro, app: AplicacionMatrix):
        super().__init__(maestro, padding=12)
        self.app = app
        self._lienzos: list[FigureCanvasTkAgg] = []
        self.var_ventana = ttk.StringVar(value="Últimas 24h")
        self.var_x = ttk.StringVar()
        self.var_y = ttk.StringVar()
        self.var_corr = ttk.StringVar(
            value="Seleccione dos variables de la estación para calcular Pearson r."
        )
        self._construir()
        self.refrescar()

    def _construir(self) -> None:
        # ── Barra de herramientas superior ───────────────────────────────────
        barra = ttk.Frame(self)
        barra.pack(fill=X, pady=(0, 8))

        ttk.Label(barra, text="Ventana Temporal:", font=("Segoe UI", 9, "bold")).pack(
            side=LEFT, padx=(0, 6)
        )
        self.combo_ventana = ttk.Combobox(
            barra,
            textvariable=self.var_ventana,
            values=list(_VENTANAS_HORAS.keys()),
            state="readonly",
            width=18,
        )
        self.combo_ventana.pack(side=LEFT, padx=(0, 8))
        self.combo_ventana.bind("<<ComboboxSelected>>", lambda _e: self.refrescar())

        ttk.Button(
            barra, text="🔄 Actualizar Gráficas", bootstyle="info-outline", command=self.refrescar
        ).pack(side=LEFT, padx=4)

        ttk.Button(
            barra,
            text="📄 Exportar Serie (.csv)",
            bootstyle="success-outline",
            command=self._exportar_csv,
        ).pack(side=RIGHT)

        # ── Notebook de 3 Pestañas Científicas ───────────────────────────────
        self.tabs = ttk.Notebook(self, bootstyle="info")
        self.tabs.pack(fill=BOTH, expand=True)

        self.tab_nodo = ttk.Frame(self.tabs, padding=8)
        self.tab_parcelas = ttk.Frame(self.tabs, padding=8)
        self.tab_corr = ttk.Frame(self.tabs, padding=8)

        self.tabs.add(self.tab_nodo, text=" 📡 Telemetría Adaptativa del Nodo ")
        self.tabs.add(self.tab_parcelas, text=" 🌱 Parcelas & Consumo Hídrico ")
        self.tabs.add(self.tab_corr, text=" 🔬 Correlación Bivariada (Pearson r) ")

        # Tab 2: Parcelas (layout side-by-side clásico mejorado)
        self.tab_parcelas.columnconfigure((0, 1), weight=1)
        self.tab_parcelas.rowconfigure(0, weight=1)
        self.marco_hum = ttk.Labelframe(
            self.tab_parcelas, text="Estado Actual de Humedad del Suelo", padding=8, bootstyle="info"
        )
        self.marco_hum.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.marco_con = ttk.Labelframe(
            self.tab_parcelas,
            text="Consumo Acumulado de Agua (Litros)",
            padding=8,
            bootstyle="success",
        )
        self.marco_con.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        # Tab 3: Correlación bivariada
        ctrl_corr = ttk.Frame(self.tab_corr, padding=(0, 0, 0, 8))
        ctrl_corr.pack(fill=X)
        ttk.Label(ctrl_corr, text="Variable X:", font=("Segoe UI", 9, "bold")).pack(side=LEFT)
        self.combo_x = ttk.Combobox(ctrl_corr, textvariable=self.var_x, state="readonly", width=22)
        self.combo_x.pack(side=LEFT, padx=(6, 12))
        ttk.Label(ctrl_corr, text="Variable Y:", font=("Segoe UI", 9, "bold")).pack(side=LEFT)
        self.combo_y = ttk.Combobox(ctrl_corr, textvariable=self.var_y, state="readonly", width=22)
        self.combo_y.pack(side=LEFT, padx=(6, 12))
        ttk.Button(
            ctrl_corr, text="Calcular Correlación r", bootstyle="primary", command=self._graficar_correlacion
        ).pack(side=LEFT)
        ttk.Label(self.tab_corr, textvariable=self.var_corr, font=("Segoe UI", 9), bootstyle="info").pack(
            anchor=W, pady=(0, 6)
        )
        self.marco_corr = ttk.Labelframe(
            self.tab_corr, text="Diagrama de Dispersión X vs Y", padding=8, bootstyle="primary"
        )
        self.marco_corr.pack(fill=BOTH, expand=True)

    # ── Ciclo de Vida Limpio de Lienzos (DT-04) ──────────────────────────────
    def _limpiar_marco(self, marco: ttk.Frame) -> None:
        for hijo in list(marco.winfo_children()):
            hijo.destroy()

    def _limpiar_lienzos(self) -> None:
        for lienzo in self._lienzos:
            with contextlib.suppress(Exception):
                lienzo.get_tk_widget().destroy()
            with contextlib.suppress(Exception):
                lienzo.figure.clear()
        self._lienzos.clear()
        for marco in (self.tab_nodo, self.marco_hum, self.marco_con, self.marco_corr):
            self._limpiar_marco(marco)

    def _incrustar(self, figura: Figure, maestro: ttk.Frame) -> None:
        lienzo = FigureCanvasTkAgg(figura, master=maestro)
        lienzo.draw()
        lienzo.get_tk_widget().pack(fill=BOTH, expand=True)
        self._lienzos.append(lienzo)

    # ── Render Principal ─────────────────────────────────────────────────────
    def al_cambiar_estacion(self) -> None:
        self.refrescar()

    def refrescar(self) -> None:
        self._limpiar_lienzos()
        self._graficar_nodo_adaptativo()
        self._graficar_humedad_parcelas()
        self._graficar_consumo_parcelas()
        self._poblar_combos_correlacion()

    def _fechas(self, pares: list[tuple[int, float]]) -> tuple[list[datetime], list[float]]:
        return [datetime.fromtimestamp(ts) for ts, _ in pares], [v for _, v in pares]

    def _graficar_nodo_adaptativo(self) -> None:
        est_id = self.app.estacion_activa_id
        if est_id is None:
            ttk.Label(
                self.tab_nodo,
                text="Sin estación activa. Siembre o registre una estación en Radar o Configuración.",
            ).pack(expand=True)
            return

        horas = _VENTANAS_HORAS.get(self.var_ventana.get(), 24)
        est, _piso, _techo, series, _uni = self.app.contenedor.pulso.obtener_series_ventana(
            est_id, horas=horas
        )
        if not series:
            ttk.Label(
                self.tab_nodo,
                text=f"La estación '{est.codigo}' aún no tiene lecturas en la ventana seleccionada.",
            ).pack(expand=True)
            return

        pal = paleta_activa(self.app.raiz.style)
        fig = Figure(figsize=(9.5, 5.2), dpi=100)
        ax1 = fig.add_subplot(211)
        ax2 = fig.add_subplot(212, sharex=ax1)
        estilizar_figura(fig, [ax1, ax2], pal)

        tipo = est.tipo
        if tipo is TipoEstacion.INBEERSA:
            if "temperatura_interna" in series:
                x, y = self._fechas(series["temperatura_interna"])
                ax1.plot(x, y, color=pal.warning, linewidth=2, label="Temp. Interna (°C)")
                ax1.axhspan(28.0, 32.0, color=pal.success, alpha=0.14, label="Homeostasis (28-32 °C)")
            if "temperatura_externa" in series:
                x, y = self._fechas(series["temperatura_externa"])
                ax1.plot(x, y, color=pal.info, linestyle="--", linewidth=1.4, label="Temp. Externa (°C)")
            ax1.set_title(f"{est.nombre} ({est.codigo}) — Termorregulación del Nido")
            ax1.set_ylabel("°C")

            if "humedad_interna" in series:
                x, y = self._fechas(series["humedad_interna"])
                ax2.plot(x, y, color=pal.info, linewidth=1.8, label="Humedad Interna (%)")
            if "vpd_nido" in series:
                x, y = self._fechas(series["vpd_nido"])
                ax2_r = ax2.twinx()
                ax2_r.plot(x, y, color=pal.danger, linestyle=":", linewidth=1.6, label="VPD Nido (kPa)")
                ax2_r.tick_params(colors=pal.danger, labelsize=8)
                ax2_r.set_ylabel("kPa", color=pal.danger)
            ax2.set_ylabel("HR %")

        elif tipo is TipoEstacion.SIGATOKA:
            for clave, col, eti in (
                ("foliar_humedad_pct", pal.info, "Humectación Foliar (%)"),
                ("hum_aire", pal.primary, "HR Aire (%)"),
            ):
                if clave in series:
                    x, y = self._fechas(series[clave])
                    ax1.plot(x, y, color=col, linewidth=1.8, label=eti)
            ax1.set_title(f"{est.nombre} ({est.codigo}) — Riesgo Fúngico & Humectación")
            ax1.set_ylabel("%")
            if "temp_aire" in series:
                x, y = self._fechas(series["temp_aire"])
                ax2.plot(x, y, color=pal.warning, linewidth=1.8, label="Temp. Aire (°C)")
            if "lluvia_mm_min" in series:
                x, y = self._fechas(series["lluvia_mm_min"])
                ax2.bar(x, y, width=0.01, color=pal.info, alpha=0.6, label="Lluvia (mm/min)")
            ax2.set_ylabel("°C / mm")

        elif tipo is TipoEstacion.CONSERVACION:
            for clave, col, eti in (
                ("humedad_turba_a", pal.success, "Turba A (%)"),
                ("humedad_turba_b", pal.info, "Turba B (%)"),
            ):
                if clave in series:
                    x, y = self._fechas(series[clave])
                    ax1.plot(x, y, color=col, linewidth=1.8, label=eti)
            ax1.set_title(f"{est.nombre} ({est.codigo}) — Hidrología de Páramo / Turbera")
            ax1.set_ylabel("%")
            if "nivel_freatico_cm" in series:
                x, y = self._fechas(series["nivel_freatico_cm"])
                ax2.plot(x, y, color=pal.primary, linewidth=1.8, label="Nivel Freático (cm)")
            if "radiacion_solar_wm2" in series:
                x, y = self._fechas(series["radiacion_solar_wm2"])
                ax2_r = ax2.twinx()
                ax2_r.plot(x, y, color=pal.warning, alpha=0.7, label="Radiación (W/m²)")
                ax2_r.tick_params(colors=pal.warning, labelsize=8)
            ax2.set_ylabel("cm")

        else:  # TERRABIT_INTI / OTRO
            for clave, col, eti in (
                ("suelo_a", pal.success, "Suelo A — Zona Radicular (%)"),
                ("suelo_b", pal.info, "Suelo B — Drenaje Profundo (%)"),
            ):
                if clave in series:
                    x, y = self._fechas(series[clave])
                    ax1.plot(x, y, color=col, linewidth=2.0, label=eti)
            ax1.axhline(
                UMBRAL_CRITICO_PCT,
                color=pal.danger,
                linestyle="--",
                linewidth=1,
                label=f"Umbral Crítico ({UMBRAL_CRITICO_PCT:.0f}%)",
            )
            ax1.set_ylim(0, 105)
            ax1.set_title(f"{est.nombre} ({est.codigo}) — Perfil Hídrico de Suelo & Microclima")
            ax1.set_ylabel("Humedad (%)")

            for clave, col, eti in (
                ("temp_aire", pal.warning, "Temp. Aire (°C)"),
                ("temp_raiz", pal.danger, "Temp. Raíz (°C)"),
            ):
                if clave in series:
                    x, y = self._fechas(series[clave])
                    ax2.plot(x, y, color=col, linewidth=1.7, label=eti)
            if "vpd" in series:
                x, y = self._fechas(series["vpd"])
                ax2_r = ax2.twinx()
                ax2_r.plot(x, y, color=pal.primary, linestyle=":", linewidth=1.6, label="VPD (kPa)")
                ax2_r.tick_params(colors=pal.primary, labelsize=8)
                ax2_r.set_ylabel("VPD (kPa)", color=pal.primary)
            ax2.set_ylabel("Temp (°C)")

        ax2.xaxis.set_major_formatter(DateFormatter("%m-%d %H:%M"))
        for ax in (ax1, ax2):
            handles, _labels = ax.get_legend_handles_labels()
            if handles:
                ax.legend(fontsize=8, loc="upper left", framealpha=0.35)
        fig.autofmt_xdate(rotation=15)
        fig.tight_layout()
        self._incrustar(fig, self.tab_nodo)

    def _graficar_humedad_parcelas(self) -> None:
        datos = self.app.ejecutar_accion(self.app.contenedor.monitor.humedad_por_parcela) or []
        if not datos:
            ttk.Label(self.marco_hum, text="No hay parcelas activas.").pack(expand=True)
            return
        pal = paleta_activa(self.app.raiz.style)
        nombres, humedades = zip(*datos, strict=True)
        fig = Figure(figsize=(5, 4), dpi=100)
        eje = fig.add_subplot()
        estilizar_figura(fig, eje, pal)
        colores = [pal.danger if h < UMBRAL_CRITICO_PCT else pal.success for h in humedades]
        barras = eje.bar(nombres, humedades, color=colores)
        eje.axhline(
            UMBRAL_CRITICO_PCT,
            color=pal.danger,
            linestyle="--",
            linewidth=1,
            label=f"Umbral crítico {UMBRAL_CRITICO_PCT:.0f} %",
        )
        eje.set_ylim(0, 105)
        eje.set_ylabel("Humedad volumétrica relativa (%)")
        eje.set_title("Niveles de Humedad por Parcela", fontsize=10)
        eje.tick_params(axis="x", labelrotation=15, labelsize=8)
        eje.bar_label(barras, fmt="%.0f", padding=3, color=pal.fg)
        eje.legend(fontsize=7, loc="upper right")
        fig.tight_layout()
        self._incrustar(fig, self.marco_hum)

    def _graficar_consumo_parcelas(self) -> None:
        datos = self.app.ejecutar_accion(self.app.contenedor.monitor.consumo_por_parcela) or []
        if not datos:
            ttk.Label(self.marco_con, text="No hay registros de riego aún.").pack(expand=True)
            return
        pal = paleta_activa(self.app.raiz.style)
        nombres, litros = zip(*datos, strict=True)
        fig = Figure(figsize=(5, 4), dpi=100)
        eje = fig.add_subplot()
        estilizar_figura(fig, eje, pal)
        barras = eje.bar(nombres, litros, color=pal.info)
        eje.set_ylabel("Litros totales")
        eje.set_title("Riego Total Acumulado por Parcela", fontsize=10)
        eje.tick_params(axis="x", labelrotation=15, labelsize=8)
        eje.bar_label(barras, fmt="%.0f", padding=3, color=pal.fg)
        fig.tight_layout()
        self._incrustar(fig, self.marco_con)

    def _poblar_combos_correlacion(self) -> None:
        est_id = self.app.estacion_activa_id
        if est_id is None:
            self.combo_x["values"] = []
            self.combo_y["values"] = []
            return
        horas = _VENTANAS_HORAS.get(self.var_ventana.get(), 24)
        _est, _p, _t, series, _u = self.app.contenedor.pulso.obtener_series_ventana(
            est_id, horas=horas
        )
        vars_disp = sorted(series.keys())
        self.combo_x["values"] = vars_disp
        self.combo_y["values"] = vars_disp
        if len(vars_disp) >= 2:
            if self.var_x.get() not in vars_disp:
                self.var_x.set(vars_disp[0])
            if self.var_y.get() not in vars_disp or self.var_y.get() == self.var_x.get():
                self.var_y.set(vars_disp[1])

    def _graficar_correlacion(self) -> None:
        est_id = self.app.estacion_activa_id
        vx, vy = self.var_x.get(), self.var_y.get()
        if est_id is None or not vx or not vy:
            return
        horas = _VENTANAS_HORAS.get(self.var_ventana.get(), 24)
        _est, piso, techo, series, _u = self.app.contenedor.pulso.obtener_series_ventana(
            est_id, horas=horas
        )
        res = self.app.contenedor.pulso.comparar_variables(
            est_id, vx, vy, desde_epoch=piso, hasta_epoch=techo
        )
        r_txt = f"{res.pearson_r:.3f}" if res.pearson_r is not None else "N/A"
        self.var_corr.set(
            f"Pearson r({vx}, {vy}) = {r_txt} · Pares alineados: {res.pares_alineados} · {res.interpretacion}"
        )

        # Limpia solo el marco de correlación reutilizando la gráfica previa si existía
        for hijo in list(self.marco_corr.winfo_children()):
            hijo.destroy()
        sx = series.get(vx, [])
        sy = series.get(vy, [])
        if not sx or not sy:
            ttk.Label(self.marco_corr, text="Sin suficientes muestras alineadas.").pack(expand=True)
            return

        xs, ys = [], []
        idx_y = 0
        sy_ord = sorted(sy)
        for tx, val_x in sorted(sx):
            while idx_y + 1 < len(sy_ord) and abs(sy_ord[idx_y + 1][0] - tx) <= abs(
                sy_ord[idx_y][0] - tx
            ):
                idx_y += 1
            if abs(sy_ord[idx_y][0] - tx) <= 300:
                xs.append(val_x)
                ys.append(sy_ord[idx_y][1])

        if not xs:
            ttk.Label(self.marco_corr, text="No hubo pares dentro de ±300 s.").pack(expand=True)
            return

        pal = paleta_activa(self.app.raiz.style)
        fig = Figure(figsize=(6.5, 4), dpi=100)
        ax = fig.add_subplot()
        estilizar_figura(fig, ax, pal)
        ax.scatter(xs, ys, color=pal.success, alpha=0.8, s=26)
        ax.set_xlabel(vx)
        ax.set_ylabel(vy)
        ax.set_title(f"Correlación {vx} vs {vy} (r = {r_txt})")
        fig.tight_layout()
        self._incrustar(fig, self.marco_corr)

    def _exportar_csv(self) -> None:
        est_id = self.app.estacion_activa_id
        if est_id is None:
            return
        est = self.app.contenedor.radar.obtener_estacion(est_id)
        ruta = filedialog.asksaveasfilename(
            parent=self,
            title="Exportar serie agregada (.csv)",
            defaultextension=".csv",
            initialfile=f"serie_{est.codigo}.csv",
            filetypes=[("CSV UTF-8", "*.csv")],
        )
        if not ruta:
            return
        destino = self.app.ejecutar_accion(
            lambda: self.app.contenedor.exportacion.exportar_csv_estacion(est_id, Path(ruta))
        )
        if destino is not None:
            messagebox.showinfo("CSV Exportado", f"Archivo guardado en:\n{destino}", parent=self)

    def destroy(self) -> None:
        self._limpiar_lienzos()
        super().destroy()
