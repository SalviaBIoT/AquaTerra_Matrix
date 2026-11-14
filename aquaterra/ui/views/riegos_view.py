"""Vista 4 — Riego, 5 Candados de Seguridad, Salud de Bomba e Incidencia en Suelo."""

from __future__ import annotations

from tkinter import messagebox
from typing import TYPE_CHECKING

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, LEFT, RIGHT, VERTICAL, W, X, Y
from ttkbootstrap.widgets import DateEntry

from aquaterra.core import tiempo
from aquaterra.core.domain import ModoVerificacionRiego, Parcela

if TYPE_CHECKING:
    from aquaterra.ui.app import AplicacionMatrix


class VistaRiego(ttk.Frame):
    """Orquesta riego manual, recomendación proactiva, 5 candados, salud de bomba e incidencia."""

    def __init__(self, maestro, app: AplicacionMatrix):
        super().__init__(maestro, padding=12)
        self.app = app
        self.var_umbral = ttk.IntVar(value=45)
        self.var_parcela = ttk.StringVar()
        self.var_litros = ttk.IntVar(value=50)
        self._por_etiqueta: dict[str, int] = {}
        self._construir()
        self._cargar_parcelas()

    def _construir(self) -> None:
        self.tabs = ttk.Notebook(self, bootstyle="info")
        self.tabs.pack(fill=BOTH, expand=True)

        self.tab_ejecucion = ttk.Frame(self.tabs, padding=10)
        self.tab_candados = ttk.Frame(self.tabs, padding=10)
        self.tab_historial = ttk.Frame(self.tabs, padding=10)

        self.tabs.add(self.tab_ejecucion, text=" 💧 Riego Manual & Programado ")
        self.tabs.add(self.tab_candados, text=" 🛡️ 5 Candados, Bomba & Incidencia ")
        self.tabs.add(self.tab_historial, text=" 📜 Cola Programada & Historial ")

        self._construir_tab_ejecucion()
        self._construir_tab_candados()
        self._construir_tab_historial()

    def _construir_tab_ejecucion(self) -> None:
        self.tab_ejecucion.columnconfigure((0, 1), weight=1)
        self.tab_ejecucion.rowconfigure(0, weight=1)

        izq = ttk.Frame(self.tab_ejecucion, padding=10)
        izq.grid(row=0, column=0, sticky="nsew")
        ttk.Label(
            izq,
            text="Seleccione Parcela (Riego Automático Activo):",
            font=("Segoe UI", 10, "bold"),
        ).pack(fill=X, anchor=W)
        self.combo = ttk.Combobox(izq, textvariable=self.var_parcela, state="readonly")
        self.combo.pack(fill=X, pady=(6, 16))
        self.combo.bind("<<ComboboxSelected>>", lambda _e: self._mostrar_info())

        marco_umbral = ttk.Labelframe(izq, text=" Condición de Disparo ", padding=16, bootstyle="info")
        marco_umbral.pack(fill=X)
        ttk.Label(
            marco_umbral, text="Activar si la humedad del suelo es menor a:", bootstyle="secondary"
        ).pack()
        self.lbl_umbral = ttk.Label(
            marco_umbral, text="45 %", font=("Segoe UI", 36, "bold"), bootstyle="info"
        )
        self.lbl_umbral.pack(pady=8)
        self.slider = ttk.Scale(
            marco_umbral,
            from_=0,
            to=100,
            variable=self.var_umbral,
            bootstyle="info",
            command=lambda _v: self.lbl_umbral.config(text=f"{round(self.var_umbral.get())} %"),
        )
        self.slider.pack(fill=X, pady=8)
        rango = ttk.Frame(marco_umbral)
        rango.pack(fill=X)
        ttk.Label(rango, text="0%").pack(side=LEFT)
        ttk.Label(rango, text="100%").pack(side=RIGHT)

        der = ttk.Frame(self.tab_ejecucion, padding=10)
        der.grid(row=0, column=1, sticky="nsew")
        self.lbl_info = ttk.Label(
            der,
            text="Seleccione una parcela...",
            font=("Segoe UI", 10),
            wraplength=420,
            justify=LEFT,
            bootstyle="secondary",
            padding=12,
        )
        self.lbl_info.pack(fill=X, pady=(0, 12))

        grupo = ttk.Labelframe(der, text=" Parámetros de Riego ", padding=14)
        grupo.pack(fill=X)
        ttk.Label(grupo, text="Fecha (ISO-8601):").pack(anchor=W)
        self.calendario = DateEntry(grupo, bootstyle="success", date_format="%Y-%m-%d")
        self.calendario.pack(fill=X, pady=(4, 10))
        ttk.Label(grupo, text="Hora (HH:MM, 24 h):").pack(anchor=W)
        self.entrada_hora = ttk.Entry(grupo)
        self.entrada_hora.insert(0, "06:00")
        self.entrada_hora.pack(fill=X, pady=(4, 10))
        ttk.Label(grupo, text="Cantidad de Agua (Litros):", font=("Segoe UI", 9, "bold")).pack(
            anchor=W
        )
        ttk.Spinbox(
            grupo, from_=1, to=5000, textvariable=self.var_litros, bootstyle="success"
        ).pack(fill=X, pady=(4, 6))

        acciones = ttk.Frame(der)
        acciones.pack(fill=X, pady=14)
        acciones.columnconfigure((0, 1), weight=1)
        self.btn_aplicar = ttk.Button(
            acciones, text="💧 APLICAR RIEGO AHORA", bootstyle="success", command=self._aplicar
        )
        self.btn_aplicar.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self.btn_programar = ttk.Button(
            acciones,
            text="🛡️ PROGRAMAR (5 CANDADOS)",
            bootstyle="info",
            command=self._programar_validado,
        )
        self.btn_programar.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        if not self.app.actor.es_admin:
            self.btn_aplicar.configure(state="disabled")
            self.btn_programar.configure(state="disabled")
            ttk.Label(
                der,
                text="Solo administradores pueden ejecutar o programar riegos.",
                bootstyle="warning",
                font=("Segoe UI", 9),
            ).pack(fill=X)

    def _construir_tab_candados(self) -> None:
        self.tab_candados.columnconfigure(0, weight=3)
        self.tab_candados.columnconfigure(1, weight=2)
        self.tab_candados.rowconfigure(0, weight=1)

        # Izquierda: Recomendación Proactiva + 5 Candados
        izq = ttk.Labelframe(
            self.tab_candados,
            text=" 🛡️ Evaluación Proactiva & 5 Candados de Seguridad ",
            padding=12,
            bootstyle="info",
        )
        izq.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self.var_recom = ttk.StringVar(value="Cargando recomendación agronómica...")
        ttk.Label(
            izq, textvariable=self.var_recom, font=("Segoe UI", 9), wraplength=540, justify=LEFT
        ).pack(fill=X, pady=(0, 8))

        cols = ("candado", "estado", "detalle")
        self.tabla_candados = ttk.Treeview(izq, columns=cols, show="headings", bootstyle="info", height=6)
        for col, tit, anch in (
            ("candado", "Candado Físico", 180),
            ("estado", "Veredicto", 105),
            ("detalle", "Diagnóstico", 290),
        ):
            self.tabla_candados.heading(col, text=tit, anchor=W)
            self.tabla_candados.column(col, width=anch, anchor=W)
        self.tabla_candados.tag_configure("ok", foreground="#10b981")
        self.tabla_candados.tag_configure("recorte", foreground="#f59e0b")
        self.tabla_candados.tag_configure("bloqueo", foreground="#ef4444")
        self.tabla_candados.pack(fill=BOTH, expand=True)

        ttk.Button(
            izq,
            text="🔄 Reevaluar 5 Candados",
            bootstyle="info-outline",
            command=self._evaluar_candados_y_bomba,
        ).pack(anchor=W, pady=(8, 0))

        # Derecha: Salud de Bomba & Post-evaluación ΔθA / ΔθB
        der = ttk.Labelframe(
            self.tab_candados,
            text=" 🔧 Salud de Bomba & Incidencia (ΔθA / ΔθB) ",
            padding=12,
            bootstyle="warning",
        )
        der.grid(row=0, column=1, sticky="nsew")

        self.var_bomba = ttk.StringVar(
            value="Actuador en modo SIN_SENSOR_ACTUADOR (listo para futura bomba + sensor vibración/caudal)."
        )
        ttk.Label(
            der, textvariable=self.var_bomba, font=("Segoe UI", 9), wraplength=350, justify=LEFT
        ).pack(fill=X, pady=(0, 10))

        ttk.Separator(der).pack(fill=X, pady=6)
        ttk.Label(der, text="Registrar Verificación Post-Riego:", font=("Segoe UI", 9, "bold")).pack(
            anchor=W, pady=(0, 6)
        )

        self.var_ev_id = ttk.StringVar()
        self.var_ha_antes = ttk.StringVar(value="32")
        self.var_ha_desp = ttk.StringVar(value="48")
        self.var_hb_antes = ttk.StringVar(value="40")
        self.var_hb_desp = ttk.StringVar(value="45")
        self.var_modo_verif = ttk.StringVar(value=ModoVerificacionRiego.SIN_SENSOR_ACTUADOR.value)

        grid_f = ttk.Frame(der)
        grid_f.pack(fill=X)
        grid_f.columnconfigure((0, 1), weight=1)
        campos = (
            ("ID Evento Riego:", self.var_ev_id, 0, 0),
            ("Modo Verificación:", None, 0, 1),
            ("Suelo A Antes (%):", self.var_ha_antes, 1, 0),
            ("Suelo A Después (%):", self.var_ha_desp, 1, 1),
            ("Suelo B Antes (%):", self.var_hb_antes, 2, 0),
            ("Suelo B Después (%):", self.var_hb_desp, 2, 1),
        )
        for etiq, var, f_idx, c_idx in campos:
            sub = ttk.Frame(grid_f, padding=2)
            sub.grid(row=f_idx, column=c_idx, sticky="ew")
            ttk.Label(sub, text=etiq, font=("Segoe UI", 8)).pack(anchor=W)
            if var is None:
                ttk.Combobox(
                    sub,
                    textvariable=self.var_modo_verif,
                    values=[m.value for m in ModoVerificacionRiego],
                    state="readonly",
                ).pack(fill=X)
            else:
                ttk.Entry(sub, textvariable=var).pack(fill=X)

        ttk.Button(
            der,
            text="✅ Evaluar Incidencia ΔθA / ΔθB",
            bootstyle="warning",
            command=self._registrar_incidencia,
        ).pack(fill=X, pady=(12, 0))

    def _construir_tab_historial(self) -> None:
        self.tab_historial.rowconfigure((0, 1), weight=1)
        self.tab_historial.columnconfigure(0, weight=1)

        m1 = ttk.Labelframe(
            self.tab_historial, text=" Cola de Riegos Programados ", padding=8, bootstyle="info"
        )
        m1.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        cols1 = ("id", "fecha", "litros", "apertura", "estado", "motivo")
        self.tabla_prog = ttk.Treeview(m1, columns=cols1, show="headings", bootstyle="info")
        for c, tit, anch in (
            ("id", "ID", 45),
            ("fecha", "Fecha Programada", 155),
            ("litros", "Litros", 70),
            ("apertura", "Apertura", 75),
            ("estado", "Estado", 145),
            ("motivo", "Motivo / Observación", 280),
        ):
            self.tabla_prog.heading(c, text=tit, anchor=W)
            self.tabla_prog.column(c, width=anch, anchor=W)
        s1 = ttk.Scrollbar(m1, orient=VERTICAL, command=self.tabla_prog.yview)
        self.tabla_prog.configure(yscrollcommand=s1.set)
        s1.pack(side=RIGHT, fill=Y)
        self.tabla_prog.pack(fill=BOTH, expand=True)

        m2 = ttk.Labelframe(
            self.tab_historial, text=" Historial de Riegos Ejecutados ", padding=8, bootstyle="success"
        )
        m2.grid(row=1, column=0, sticky="nsew")
        cols2 = ("id", "fecha", "litros", "hum_ini", "hum_fin", "origen")
        self.tabla_hist = ttk.Treeview(m2, columns=cols2, show="headings", bootstyle="success")
        for c, tit, anch in (
            ("id", "Evento ID", 75),
            ("fecha", "Timestamp ISO-8601", 175),
            ("litros", "Litros", 80),
            ("hum_ini", "Humedad Inicial", 110),
            ("hum_fin", "Humedad Final", 110),
            ("origen", "Origen", 100),
        ):
            self.tabla_hist.heading(c, text=tit, anchor=W)
            self.tabla_hist.column(c, width=anch, anchor=W)
        s2 = ttk.Scrollbar(m2, orient=VERTICAL, command=self.tabla_hist.yview)
        self.tabla_hist.configure(yscrollcommand=s2.set)
        s2.pack(side=RIGHT, fill=Y)
        self.tabla_hist.pack(fill=BOTH, expand=True)

    # ── Carga y Refresco ─────────────────────────────────────────────────────
    @staticmethod
    def _etiqueta(p: Parcela) -> str:
        return f"#{p.id} · {p.nombre}"

    def refrescar(self) -> None:
        self._cargar_parcelas()

    def _cargar_parcelas(self) -> None:
        parcelas = self.app.ejecutar_accion(
            lambda: self.app.contenedor.parcelas.listar(solo_riego_auto=True)
        ) or []
        self._por_etiqueta = {self._etiqueta(p): p.id for p in parcelas}
        self.combo["values"] = list(self._por_etiqueta)
        if parcelas:
            self.combo.current(0)
            self._mostrar_info()
        else:
            self.combo.set("Sin parcelas con riego automático")
            self.slider.configure(state="disabled")
            self.btn_aplicar.configure(state="disabled")
            self.btn_programar.configure(state="disabled")

    def _mostrar_info(self) -> None:
        pid = self._por_etiqueta.get(self.var_parcela.get())
        if pid is None:
            return
        p = self.app.ejecutar_accion(lambda: self.app.contenedor.parcelas.obtener(pid))
        if p:
            self.lbl_info.config(
                text=(
                    f"PARCELA: {p.nombre} (id {p.id})\n"
                    f"Cultivo: {p.cultivo} · Suelo: {p.tipo_suelo.value} · Área: {p.area_m2:g} m²\n"
                    f"Humedad actual: {p.humedad_pct:.1f} %"
                ),
                bootstyle="info",
            )
            self._evaluar_candados_y_bomba()
            self._recargar_tablas_parcela(pid)

    def _evaluar_candados_y_bomba(self) -> None:
        pid = self._por_etiqueta.get(self.var_parcela.get())
        if pid is None:
            return
        rec = self.app.ejecutar_accion(
            lambda: self.app.contenedor.control.recomendar_riego_parcela(
                pid, umbral_disparo_pct=float(round(self.var_umbral.get()))
            )
        )
        if rec is None:
            return

        tasa = (
            f"{rec.tasa_secado_pct_h:.2f} %/h" if rec.tasa_secado_pct_h is not None else "N/A"
        )
        estres = (
            f"{rec.horas_hasta_estres:.1f} h" if rec.horas_hasta_estres is not None else "N/A"
        )
        self.var_recom.set(
            f"Acción recomendada: {rec.accion.value.upper()} · Sugerido: {rec.litros_sugeridos:.1f} L "
            f"(Apertura {rec.apertura_sugerida_pct:.0f}%) · Tasa secado: {tasa} · Estrés en: {estres}\n"
            f"Justificación: {rec.justificacion}"
        )

        self.tabla_candados.delete(*self.tabla_candados.get_children())
        for c in rec.veredicto_seguridad.candados:
            if c.superado and not c.recorte_aplicado:
                est_txt, tag = "🟢 SUPERADO", "ok"
            elif c.superado and c.recorte_aplicado:
                est_txt, tag = "🟠 RECORTE", "recorte"
            else:
                est_txt, tag = "🔴 BLOQUEADO", "bloqueo"
            self.tabla_candados.insert(
                "", "end", tags=(tag,), values=(c.codigo.value, est_txt, c.detalle)
            )

        salud = self.app.contenedor.control.ultimo_salud_actuador(pid)
        if salud is None:
            self.var_bomba.set(
                "Estado actual: SIN_SENSOR_ACTUADOR (sin bomba/electroválvula conectada hoy).\n"
                "El Candado #5 ya está preparado para vibración RMS, corriente o caudal futuro."
            )
        else:
            self.var_bomba.set(
                f"Último diagnóstico actuador: {salud.diagnostico_mecanico.value.upper()}\n"
                f"Modo: {salud.modo_verificacion.value} · Registrado: {salud.registrado_en[:16]}"
            )

    def _recargar_tablas_parcela(self, pid: int) -> None:
        self.tabla_prog.delete(*self.tabla_prog.get_children())
        for pr in self.app.contenedor.control.listar_riegos_programados(pid):
            self.tabla_prog.insert(
                "",
                "end",
                values=(
                    pr.id,
                    pr.ts_programado_iso[:16].replace("T", " "),
                    f"{pr.litros_propuestos:.1f} L",
                    f"{pr.apertura_max_pct:.0f}%",
                    pr.estado.value,
                    pr.motivo_bloqueo or "Autorizado",
                ),
            )

        self.tabla_hist.delete(*self.tabla_hist.get_children())
        eventos = self.app.contenedor.control.listar_riegos_parcela(pid)
        if eventos and not self.var_ev_id.get().strip():
            self.var_ev_id.set(str(eventos[0].id))
        for ev in eventos:
            hi = f"{ev.humedad_inicial_pct:.1f}%" if ev.humedad_inicial_pct is not None else "—"
            hf = f"{ev.humedad_final_pct:.1f}%" if ev.humedad_final_pct is not None else "—"
            self.tabla_hist.insert(
                "",
                "end",
                values=(
                    ev.id,
                    ev.ts_iso[:19].replace("T", " "),
                    f"{ev.agua_litros:.1f} L",
                    hi,
                    hf,
                    ev.origen.value,
                ),
            )

    # ── Acciones ─────────────────────────────────────────────────────────────
    def _aplicar(self) -> None:
        pid = self._por_etiqueta.get(self.var_parcela.get())
        if pid is None:
            messagebox.showwarning("Atención", "Seleccione una parcela válida.", parent=self)
            return

        def caso_de_uso():
            fecha = self.calendario.get_date()
            return self.app.contenedor.riego.aplicar_riego(
                self.app.actor,
                parcela_id=pid,
                umbral_pct=round(self.var_umbral.get()),
                litros=self.var_litros.get(),
                fecha=fecha.date() if hasattr(fecha, "date") else fecha,
                hora=self.entrada_hora.get(),
            )

        resultado = self.app.ejecutar_accion(caso_de_uso)
        if resultado is None:
            return
        titulo = "Riego aplicado" if resultado.aplicado else "Riego no requerido"
        messagebox.showinfo(titulo, resultado.mensaje, parent=self)
        self._mostrar_info()
        self.app.notificar_cambio_datos(f"💧 {titulo} en parcela #{pid}", bootstyle="success")

    def _programar_validado(self) -> None:
        pid = self._por_etiqueta.get(self.var_parcela.get())
        if pid is None:
            return

        def caso():
            fecha = self.calendario.get_date()
            f_date = fecha.date() if hasattr(fecha, "date") else fecha
            momento = tiempo.combinar(f_date, tiempo.parsear_hora(self.entrada_hora.get()))
            return self.app.contenedor.control.programar_riego_validado(
                self.app.actor,
                parcela_id=pid,
                ts_programado_epoch=tiempo.a_epoch(momento),
                litros_solicitados=float(self.var_litros.get()),
            )

        res = self.app.ejecutar_accion(caso, titulo_error="No se pudo programar el riego")
        if res is None:
            return
        prog, veredicto = res
        if veredicto.autorizado:
            messagebox.showinfo(
                "Riego Programado (Autorizado)",
                f"Programación #{prog.id} autorizada: {prog.litros_propuestos:.1f} L "
                f"(apertura {prog.apertura_max_pct:.0f}%).",
                parent=self,
            )
        else:
            messagebox.showwarning(
                "Bloqueado por Candado de Seguridad",
                "Los candados bloquearon el riego programado:\n• "
                + "\n• ".join(veredicto.motivos_bloqueo),
                parent=self,
            )
        self._mostrar_info()

    def _registrar_incidencia(self) -> None:
        try:
            ev_id = int(self.var_ev_id.get().strip())
            ha_a = float(self.var_ha_antes.get())
            ha_d = float(self.var_ha_desp.get())
            hb_a = float(self.var_hb_antes.get()) if self.var_hb_antes.get().strip() else None
            hb_d = float(self.var_hb_desp.get()) if self.var_hb_desp.get().strip() else None
        except ValueError:
            messagebox.showwarning(
                "Datos inválidos",
                "Verifique que el ID de evento y las humedades sean numéricos.",
                parent=self,
            )
            return

        modo = ModoVerificacionRiego(self.var_modo_verif.get())
        res = self.app.ejecutar_accion(
            lambda: self.app.contenedor.control.registrar_verificacion_e_incidencia(
                evento_riego_id=ev_id,
                humedad_a_antes=ha_a,
                humedad_a_despues=ha_d,
                humedad_b_antes=hb_a,
                humedad_b_despues=hb_d,
                modo_verificacion=modo,
            )
        )
        if res is None:
            return
        salud, inc = res
        messagebox.showinfo(
            "Incidencia Evaluada",
            f"Efectividad en suelo: {inc.efectividad.value.upper()} (ΔA={inc.delta_a_pct:+.1f}%)\n"
            f"Diagnóstico bomba: {salud.diagnostico_mecanico.value}\n\n{inc.observaciones or ''}",
            parent=self,
        )
        self._mostrar_info()
