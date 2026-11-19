"""Vista 1 — Radar Priorizado de Estaciones, Pulso 24h y Clima Open-Meteo."""

from __future__ import annotations

import threading
from tkinter import messagebox
from typing import TYPE_CHECKING

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, LEFT, RIGHT, VERTICAL, W, X, Y

from aquaterra.core import tiempo
from aquaterra.core.analitica import NivelSeveridadPulso
from aquaterra.ui.tema import crear_tarjeta_kpi

if TYPE_CHECKING:
    from aquaterra.ui.app import AplicacionMatrix


_ETIQUETA_SEVERIDAD = {
    NivelSeveridadPulso.CRITICO: ("🔴 CRITICO", "critico"),
    NivelSeveridadPulso.ATENCION: ("🟠 ATENCION", "atencion"),
    NivelSeveridadPulso.OPTIMO: ("🟢 OPTIMO", "optimo"),
    NivelSeveridadPulso.SIN_DATOS: ("⚪ SIN_DATOS", "sin_datos"),
}


class VistaDashboard(ttk.Frame):
    """Centro de Mando principal: Radar multi-estación, Pulso 24h y caché meteorológico."""

    def __init__(self, maestro, app: AplicacionMatrix):
        super().__init__(maestro, padding=14)
        self.app = app
        self._radar_por_id: dict[int, object] = {}
        self._construir()
        self.refrescar()

    def _construir(self) -> None:
        # ── 1. Banner de Narrativa Ejecutiva 24h ──────────────────────────────
        banner = ttk.Labelframe(
            self,
            text=" 🧠 Síntesis Ejecutiva 24h de la Estación Activa ",
            padding=12,
            bootstyle="success",
        )
        banner.pack(fill=X, pady=(0, 10))

        self.var_narrativa = ttk.StringVar(
            value="Seleccione una estación para inspeccionar su Pulso 24h o generar el análisis con IA."
        )
        ttk.Label(
            banner,
            textvariable=self.var_narrativa,
            font=("Segoe UI", 10),
            wraplength=920,
            justify=LEFT,
        ).pack(side=LEFT, fill=X, expand=True, padx=(0, 12))

        acciones_banner = ttk.Frame(banner)
        acciones_banner.pack(side=RIGHT)
        self.btn_narrar_ia = ttk.Button(
            acciones_banner,
            text="🧠 Analizar 24h con IA",
            bootstyle="primary",
            command=self._narrar_con_ia_async,
        )
        self.btn_narrar_ia.pack(fill=X, pady=(0, 4))
        ttk.Button(
            acciones_banner,
            text="📋 Copiar Boletín",
            bootstyle="secondary-outline",
            command=self._copiar_boletin,
        ).pack(fill=X)

        # ── 2. Fila de Tarjetas KPI ───────────────────────────────────────────
        kpi_fila = ttk.Frame(self)
        kpi_fila.pack(fill=X, pady=(0, 10))
        for i in range(4):
            kpi_fila.columnconfigure(i, weight=1)

        c1, self.lbl_kpi_estaciones, self.lbl_kpi_estaciones_sub = crear_tarjeta_kpi(
            kpi_fila, "Estaciones SalviaBIoT", "0", "Estaciones registradas", bootstyle="primary"
        )
        c1.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        c2, self.lbl_kpi_criticas, self.lbl_kpi_criticas_sub = crear_tarjeta_kpi(
            kpi_fila, "Alertas Radar", "0", "Priorizadas por severidad", bootstyle="danger"
        )
        c2.grid(row=0, column=1, sticky="nsew", padx=6)

        c3, self.lbl_kpi_completitud, self.lbl_kpi_completitud_sub = crear_tarjeta_kpi(
            kpi_fila, "Completitud 24h", "—", "Estación seleccionada", bootstyle="info"
        )
        c3.grid(row=0, column=2, sticky="nsew", padx=6)

        c4, self.lbl_kpi_clima, self.lbl_kpi_clima_sub = crear_tarjeta_kpi(
            kpi_fila, "Pronóstico Lluvia 24h", "—", "Caché Open-Meteo UTP", bootstyle="success"
        )
        c4.grid(row=0, column=3, sticky="nsew", padx=(6, 0))

        # ── 3. Cuerpo Dividido: Radar (Izquierda) + Pulso & Clima (Derecha) ──
        cuerpo = ttk.Frame(self)
        cuerpo.pack(fill=BOTH, expand=True)
        cuerpo.columnconfigure(0, weight=5)
        cuerpo.columnconfigure(1, weight=6)
        cuerpo.rowconfigure(0, weight=1)

        # Panel izquierdo: Radar Priorizado
        marco_radar = ttk.Labelframe(
            cuerpo,
            text=" 📡 Radar de Estaciones (CRÍTICO → ATENCIÓN → ÓPTIMO) ",
            padding=10,
            bootstyle="info",
        )
        marco_radar.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        barra_radar = ttk.Frame(marco_radar)
        barra_radar.pack(fill=X, pady=(0, 8))
        ttk.Button(
            barra_radar,
            text="🌱 Sembrar Estaciones Base",
            bootstyle="success-outline",
            command=self._sembrar_nodos_base,
        ).pack(side=LEFT, padx=(0, 6))
        ttk.Button(
            barra_radar,
            text="📈 Ver Gráficas del Nodo",
            bootstyle="info-outline",
            command=self.app.mostrar_monitor,
        ).pack(side=RIGHT)

        cols_radar = ("estado", "codigo", "tipo", "alertas", "comp", "ultimo")
        self.tabla_radar = ttk.Treeview(
            marco_radar, columns=cols_radar, show="headings", bootstyle="info"
        )
        for c, tit, anch in (
            ("estado", "Estado", 105),
            ("codigo", "Código", 130),
            ("tipo", "Familia", 100),
            ("alertas", "Alertas", 60),
            ("comp", "24h %", 65),
            ("ultimo", "Último dato", 125),
        ):
            self.tabla_radar.heading(c, text=tit, anchor=W)
            self.tabla_radar.column(c, width=anch, anchor=W)
        self.tabla_radar.tag_configure("critico", foreground="#ef4444")
        self.tabla_radar.tag_configure("atencion", foreground="#f59e0b")
        self.tabla_radar.tag_configure("optimo", foreground="#10b981")
        self.tabla_radar.tag_configure("sin_datos", foreground="#94a3b8")

        scroll_r = ttk.Scrollbar(marco_radar, orient=VERTICAL, command=self.tabla_radar.yview)
        self.tabla_radar.configure(yscrollcommand=scroll_r.set)
        scroll_r.pack(side=RIGHT, fill=Y)
        self.tabla_radar.pack(fill=BOTH, expand=True)
        self.tabla_radar.bind("<<TreeviewSelect>>", self._al_seleccionar_radar)

        # Panel derecho: Variables 24h + Clima Open-Meteo
        der = ttk.Frame(cuerpo)
        der.grid(row=0, column=1, sticky="nsew")
        der.rowconfigure(0, weight=3)
        der.rowconfigure(1, weight=2)
        der.columnconfigure(0, weight=1)

        marco_vars = ttk.Labelframe(
            der, text=" 📊 Pulso 24h de Sensores (Estación Activa) ", padding=10, bootstyle="primary"
        )
        marco_vars.grid(row=0, column=0, sticky="nsew", pady=(0, 8))

        cols_var = ("variable", "ultimo", "media", "rango", "tendencia", "muestras")
        self.tabla_vars = ttk.Treeview(
            marco_vars, columns=cols_var, show="headings", bootstyle="primary"
        )
        for c, tit, anch in (
            ("variable", "Variable", 145),
            ("ultimo", "Último", 85),
            ("media", "Media 24h", 85),
            ("rango", "Mín / Máx", 115),
            ("tendencia", "Tendencia", 95),
            ("muestras", "Muestras", 70),
        ):
            self.tabla_vars.heading(c, text=tit, anchor=W)
            self.tabla_vars.column(c, width=anch, anchor=W)
        scroll_v = ttk.Scrollbar(marco_vars, orient=VERTICAL, command=self.tabla_vars.yview)
        self.tabla_vars.configure(yscrollcommand=scroll_v.set)
        scroll_v.pack(side=RIGHT, fill=Y)
        self.tabla_vars.pack(fill=BOTH, expand=True)

        marco_clima = ttk.Labelframe(
            der,
            text=" 🌦️ Pronóstico Horario Local (Caché Open-Meteo) ",
            padding=10,
            bootstyle="warning",
        )
        marco_clima.grid(row=1, column=0, sticky="nsew")

        cols_clima = ("hora", "temp", "hum", "prob", "lluvia", "et0")
        self.tabla_clima = ttk.Treeview(
            marco_clima, columns=cols_clima, show="headings", bootstyle="warning"
        )
        for c, tit, anch in (
            ("hora", "Hora Local", 140),
            ("temp", "Temp °C", 75),
            ("hum", "HR %", 70),
            ("prob", "Prob. Lluvia", 85),
            ("lluvia", "Lluvia mm", 85),
            ("et0", "ET0 mm", 75),
        ):
            self.tabla_clima.heading(c, text=tit, anchor=W)
            self.tabla_clima.column(c, width=anch, anchor=W)
        scroll_c = ttk.Scrollbar(marco_clima, orient=VERTICAL, command=self.tabla_clima.yview)
        self.tabla_clima.configure(yscrollcommand=scroll_c.set)
        scroll_c.pack(side=RIGHT, fill=Y)
        self.tabla_clima.pack(fill=BOTH, expand=True)

    # ── Carga de Datos ───────────────────────────────────────────────────────
    def refrescar(self) -> None:
        radar = self.app.contenedor.radar.listar_radar_priorizado()
        self._radar_por_id = {e.estacion.id: e for e in radar}
        self.tabla_radar.delete(*self.tabla_radar.get_children())

        criticas = 0
        atenciones = 0
        for entrada in radar:
            est = entrada.estacion
            if entrada.severidad is NivelSeveridadPulso.CRITICO:
                criticas += 1
            elif entrada.severidad is NivelSeveridadPulso.ATENCION:
                atenciones += 1

            etiq_txt, tag = _ETIQUETA_SEVERIDAD[entrada.severidad]
            ultimo_txt = (
                tiempo.a_iso(tiempo.desde_epoch(entrada.ultimo_ts_epoch))[:16].replace("T", " ")
                if entrada.ultimo_ts_epoch
                else "Sin datos"
            )
            self.tabla_radar.insert(
                "",
                "end",
                iid=str(est.id),
                tags=(tag,),
                values=(
                    etiq_txt,
                    est.codigo,
                    est.tipo.value,
                    entrada.alertas_activas,
                    f"{entrada.completitud_24h_pct:.0f}%",
                    ultimo_txt,
                ),
            )

        self.lbl_kpi_estaciones.configure(text=str(len(radar)))
        parcelas = self.app.contenedor.parcelas.listar()
        self.lbl_kpi_estaciones_sub.configure(text=f"{len(parcelas)} parcelas activas vinculadas")
        self.lbl_kpi_criticas.configure(text=str(criticas))
        self.lbl_kpi_criticas_sub.configure(text=f"{atenciones} en atención preventiva")

        if radar and self.app.estacion_activa_id not in self._radar_por_id:
            self.app.estacion_activa_id = radar[0].estacion.id
            if self.app._shell is not None:
                self.app._shell.seleccionar_estacion(
                    self.app.estacion_activa_id, notificar_vista=False
                )

        est_id_str = str(self.app.estacion_activa_id) if self.app.estacion_activa_id is not None else ""
        if est_id_str and est_id_str in self.tabla_radar.get_children():
            self.tabla_radar.selection_set(est_id_str)

        self._cargar_detalle_estacion_activa()

    def al_cambiar_estacion(self) -> None:
        est_id_str = str(self.app.estacion_activa_id) if self.app.estacion_activa_id is not None else ""
        if est_id_str and est_id_str in self.tabla_radar.get_children():
            self.tabla_radar.selection_set(est_id_str)
        self._cargar_detalle_estacion_activa()

    def _cargar_detalle_estacion_activa(self) -> None:
        self.tabla_vars.delete(*self.tabla_vars.get_children())
        self.tabla_clima.delete(*self.tabla_clima.get_children())

        est_id = self.app.estacion_activa_id
        if est_id is None:
            self.lbl_kpi_completitud.configure(text="—")
            self.lbl_kpi_completitud_sub.configure(text="Registre o siembre estaciones")
            self.lbl_kpi_clima.configure(text="0.0 mm")
            self.lbl_kpi_clima_sub.configure(text="Sin estación activa")
            self.var_narrativa.set(
                "No hay estaciones registradas aún. Pulse '🌱 Sembrar Estaciones Base' para crear "
                "terrabit-nodointi e inbeersa-nodo01 (UTP Pereira), o importe un CSV/JSONL en Hardware."
            )
            return

        pulso = self.app.contenedor.pulso.obtener_pulso_24h(est_id)
        self.lbl_kpi_completitud.configure(text=f"{pulso.completitud_global_pct:.0f}%")
        self.lbl_kpi_completitud_sub.configure(
            text=f"{pulso.codigo_estacion} · {len(pulso.variables)} variables"
        )

        alertas_txt = (
            " | ".join(pulso.alertas_detectadas)
            if pulso.alertas_detectadas
            else "Sin alertas críticas detectadas."
        )
        self.var_narrativa.set(
            f"[{pulso.nombre_estacion}] Estado {pulso.severidad.value.upper()} — "
            f"{pulso.diagnostico_determinista} ({alertas_txt})"
        )

        for nombre_var in sorted(pulso.variables):
            rv = pulso.variables[nombre_var]
            uni = f" {rv.unidad}" if rv.unidad else ""
            self.tabla_vars.insert(
                "",
                "end",
                values=(
                    nombre_var,
                    f"{rv.ultimo_valor:.2f}{uni}",
                    f"{rv.media_24h:.2f}{uni}",
                    f"{rv.min_24h:.1f} / {rv.max_24h:.1f}",
                    rv.tendencia.value,
                    rv.muestras,
                ),
            )

        pronostico = self.app.contenedor.sincronizacion.listar_pronostico_estacion(est_id, horas=24)
        lluvia_acum = round(sum(p.lluvia_mm or 0.0 for p in pronostico), 1)
        prob_max = max((p.lluvia_prob_pct or 0.0 for p in pronostico), default=0.0)
        self.lbl_kpi_clima.configure(text=f"{lluvia_acum:.1f} mm")
        self.lbl_kpi_clima_sub.configure(
            text=f"Prob. máx {prob_max:.0f}% ({len(pronostico)}h en caché)"
        )
        for pt in pronostico[:24]:
            self.tabla_clima.insert(
                "",
                "end",
                values=(
                    pt.ts_objetivo_iso[:16].replace("T", " "),
                    f"{pt.temp_c:.1f}" if pt.temp_c is not None else "—",
                    f"{pt.hum_relativa_pct:.0f}%" if pt.hum_relativa_pct is not None else "—",
                    f"{pt.lluvia_prob_pct:.0f}%" if pt.lluvia_prob_pct is not None else "—",
                    f"{pt.lluvia_mm:.2f}" if pt.lluvia_mm is not None else "—",
                    f"{pt.et0_mm:.2f}" if pt.et0_mm is not None else "—",
                ),
            )

    # ── Acciones ─────────────────────────────────────────────────────────────
    def _al_seleccionar_radar(self, _evento=None) -> None:
        sel = self.tabla_radar.selection()
        if not sel:
            return
        est_id = int(sel[0])
        if self.app._shell is not None:
            self.app._shell.seleccionar_estacion(est_id, notificar_vista=False)
        else:
            self.app.estacion_activa_id = est_id
        self._cargar_detalle_estacion_activa()

    def _sembrar_nodos_base(self) -> None:
        estaciones = self.app.ejecutar_accion(
            self.app.contenedor.sincronizacion.asegurar_estaciones_terrabit_base
        )
        if estaciones is not None:
            self.app.notificar_cambio_datos(
                f"🌱 Estaciones base SalviaBIoT aseguradas ({len(estaciones)} estaciones UTP Pereira)",
                bootstyle="success",
            )
            self.refrescar()

    def _narrar_con_ia_async(self) -> None:
        est_id = self.app.estacion_activa_id
        if est_id is None:
            return
        self.btn_narrar_ia.configure(state="disabled")
        self.var_narrativa.set("⏳ Consultando al Orquestador IA sobre el Pulso 24h...")

        def _tarea() -> None:
            try:
                msg, prov = self.app.contenedor.copiloto.narrar_pulso_24h(est_id)
                self.after(0, lambda m=msg, p=prov: self._al_narrar(m, p))
            except Exception as exc:
                self.after(0, lambda e=exc: self._al_fallar_narrar(e))

        threading.Thread(target=_tarea, name="AquaTerra-Narrar24h", daemon=True).start()

    def _al_narrar(self, mensaje: str, proveedor: str) -> None:
        if not self.winfo_exists():
            return
        self.btn_narrar_ia.configure(state="normal")
        self.var_narrativa.set(mensaje)
        if self.app._shell is not None:
            self.app._shell.publicar_estado(
                f"🧠 Narrativa 24h generada por {proveedor}", bootstyle="success"
            )

    def _al_fallar_narrar(self, exc: Exception) -> None:
        if not self.winfo_exists():
            return
        self.btn_narrar_ia.configure(state="normal")
        self.var_narrativa.set(f"Aviso IA: {exc}")

    def _copiar_boletin(self) -> None:
        texto = self.var_narrativa.get()
        self.clipboard_clear()
        self.clipboard_append(texto)
        messagebox.showinfo("Portapapeles", "Boletín ejecutivo copiado al portapapeles.", parent=self)
