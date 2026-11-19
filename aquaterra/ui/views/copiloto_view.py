"""Vista 5 — Copiloto Agronómico IA Híbrido, Calibración Auditada y Rollback."""

from __future__ import annotations

import threading
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, LEFT, RIGHT, VERTICAL, W, X, Y

from aquaterra.core.copiloto import CATALOGO_COTAS_CALIBRACION

if TYPE_CHECKING:
    from aquaterra.ui.app import AplicacionMatrix


class VistaCopiloto(ttk.Frame):
    """Consola IA conectada a ``CalibrationCopilotService`` con 1-clic Aplicar y Rollback."""

    def __init__(self, maestro, app: AplicacionMatrix):
        super().__init__(maestro, padding=12)
        self.app = app
        self._parcela_por_etiqueta: dict[str, int | None] = {"Sin parcela específica": None}
        self._ultima_interaccion_id: int | None = None
        self._consultando = False

        self.var_parcela = ttk.StringVar(value="Sin parcela específica")
        self.var_estado_ia = ttk.StringVar(value="Listo para diagnosticar (Gemini / Ollama / Reglas).")
        self._construir()
        self.refrescar()

    def _construir(self) -> None:
        self.columnconfigure(0, weight=5)
        self.columnconfigure(1, weight=6)
        self.rowconfigure(0, weight=1)

        # ── Columna Izquierda: Consulta, Prompts Rápidos e Historial ─────────
        izq = ttk.Frame(self)
        izq.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        izq.rowconfigure(2, weight=1)
        izq.columnconfigure(0, weight=1)

        m_ctx = ttk.Labelframe(izq, text=" 🧠 Consulta al Copiloto IA ", padding=12, bootstyle="primary")
        m_ctx.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ttk.Label(m_ctx, text="Contexto de Parcela (opcional):", font=("Segoe UI", 9, "bold")).pack(
            anchor=W
        )
        self.combo_parcela = ttk.Combobox(m_ctx, textvariable=self.var_parcela, state="readonly")
        self.combo_parcela.pack(fill=X, pady=(4, 8))
        self.combo_parcela.bind("<<ComboboxSelected>>", lambda _e: self._recargar_calibracion_e_historial())

        prompts = ttk.Frame(m_ctx)
        prompts.pack(fill=X, pady=(0, 6))
        for txt, msg in (
            ("📊 Diagnóstico 24h", "Analiza el pulso de las últimas 24 horas y dime si ves riesgos."),
            (
                "💧 Ajuste por sobrerriego",
                "En el último riego nos pasamos con el agua, ¿qué ajuste de calibración recomiendas?",
            ),
            ("🐝 Revisar nido InBeersa", "Evalúa la homeostasis térmica y humedad del nido e indica alertas."),
        ):
            ttk.Button(
                prompts,
                text=txt,
                bootstyle="secondary-outline",
                command=lambda q=msg: self._poner_prompt(q),
            ).pack(side=LEFT, padx=(0, 4))

        self.txt_pregunta = ttk.Text(m_ctx, height=4, wrap="word")
        self.txt_pregunta.pack(fill=X, pady=(0, 8))
        self.txt_pregunta.insert(
            "1.0", "Analiza el estado actual de la estación y sugiere calibración segura si aplica."
        )

        self.btn_consultar = ttk.Button(
            m_ctx,
            text="🚀 Consultar Copiloto Híbrido",
            bootstyle="primary",
            command=self._consultar_async,
        )
        self.btn_consultar.pack(fill=X)

        m_hist = ttk.Labelframe(
            izq, text=" 💬 Historial de Consultas e Interacciones ", padding=8, bootstyle="secondary"
        )
        m_hist.grid(row=2, column=0, sticky="nsew")
        cols_h = ("id", "prov", "pregunta", "aplicada")
        self.tabla_hist = ttk.Treeview(m_hist, columns=cols_h, show="headings", bootstyle="secondary")
        for c, tit, anch in (
            ("id", "ID", 40),
            ("prov", "Proveedor IA", 125),
            ("pregunta", "Consulta", 230),
            ("aplicada", "Calibración", 85),
        ):
            self.tabla_hist.heading(c, text=tit, anchor=W)
            self.tabla_hist.column(c, width=anch, anchor=W)
        sh = ttk.Scrollbar(m_hist, orient=VERTICAL, command=self.tabla_hist.yview)
        self.tabla_hist.configure(yscrollcommand=sh.set)
        sh.pack(side=RIGHT, fill=Y)
        self.tabla_hist.pack(fill=BOTH, expand=True)

        # ── Columna Derecha: Propuesta Auditada + Calibración & Rollback ─────
        der = ttk.Frame(self)
        der.grid(row=0, column=1, sticky="nsew")
        der.rowconfigure(1, weight=1)
        der.columnconfigure(0, weight=1)

        m_diag = ttk.Labelframe(
            der, text=" 📋 Diagnóstico y Gobierno Humano ", padding=12, bootstyle="success"
        )
        m_diag.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ttk.Label(
            m_diag, textvariable=self.var_estado_ia, font=("Segoe UI", 9, "bold"), bootstyle="info"
        ).pack(anchor=W, pady=(0, 6))

        self.txt_diagnostico = ttk.Text(m_diag, height=7, wrap="word", state="disabled")
        self.txt_diagnostico.pack(fill=X, pady=(0, 8))

        acciones_gov = ttk.Frame(m_diag)
        acciones_gov.pack(fill=X)
        self.btn_aplicar = ttk.Button(
            acciones_gov,
            text="✅ Aplicar Calibración (1 clic)",
            bootstyle="success",
            state="disabled",
            command=self._aplicar_propuesta,
        )
        self.btn_aplicar.pack(side=LEFT, padx=(0, 6))
        ttk.Button(
            acciones_gov,
            text="⏪ Rollback Versión Anterior",
            bootstyle="warning-outline",
            command=self._rollback,
        ).pack(side=LEFT, padx=(0, 6))
        ttk.Button(
            acciones_gov,
            text="📦 Exportar Dataset .jsonl",
            bootstyle="info-outline",
            command=self._exportar_jsonl,
        ).pack(side=RIGHT)

        m_diff = ttk.Labelframe(
            der,
            text=" ⚖️ Tabla Diff Auditada (Cotas Físicas Anti-Alucinación) ",
            padding=10,
            bootstyle="info",
        )
        m_diff.grid(row=1, column=0, sticky="nsew")
        cols_d = ("param", "actual", "propuesto", "cota")
        self.tabla_diff = ttk.Treeview(m_diff, columns=cols_d, show="headings", bootstyle="info")
        for c, tit, anch in (
            ("param", "Parámetro Calibración", 180),
            ("actual", "Valor Actual", 110),
            ("propuesto", "Propuesto Seguro", 125),
            ("cota", "Rango Físico Permitido", 170),
        ):
            self.tabla_diff.heading(c, text=tit, anchor=W)
            self.tabla_diff.column(c, width=anch, anchor=W)
        self.tabla_diff.tag_configure("cambio", foreground="#10b981")
        sd = ttk.Scrollbar(m_diff, orient=VERTICAL, command=self.tabla_diff.yview)
        self.tabla_diff.configure(yscrollcommand=sd.set)
        sd.pack(side=RIGHT, fill=Y)
        self.tabla_diff.pack(fill=BOTH, expand=True)

    # ── Carga de Contexto ────────────────────────────────────────────────────
    def al_cambiar_estacion(self) -> None:
        self._recargar_calibracion_e_historial()

    def refrescar(self) -> None:
        self._parcela_por_etiqueta = {"Sin parcela específica": None}
        for p in self.app.contenedor.parcelas.listar():
            self._parcela_por_etiqueta[f"#{p.id} · {p.nombre} ({p.cultivo})"] = p.id
        self.combo_parcela["values"] = list(self._parcela_por_etiqueta.keys())
        if self.var_parcela.get() not in self._parcela_por_etiqueta:
            self.var_parcela.set("Sin parcela específica")
        self._recargar_calibracion_e_historial()

    def _recargar_calibracion_e_historial(self) -> None:
        est_id = self.app.estacion_activa_id
        par_id = self._parcela_por_etiqueta.get(self.var_parcela.get())

        version, params = self.app.contenedor.copiloto.obtener_calibracion_efectiva(
            estacion_id=est_id, parcela_id=par_id
        )
        self._poblar_diff(params, {})
        self.var_estado_ia.set(f"Calibración activa vigente: v{version} ({len(params)} parámetros)")

        self.tabla_hist.delete(*self.tabla_hist.get_children())
        for inter in self.app.contenedor.copiloto.listar_historial_conversaciones(
            estacion_id=est_id, parcela_id=par_id
        ):
            resumen_p = (
                inter.mensaje_usuario[:52] + "..."
                if len(inter.mensaje_usuario) > 52
                else inter.mensaje_usuario
            )
            self.tabla_hist.insert(
                "",
                "end",
                values=(
                    inter.id,
                    inter.proveedor_ia,
                    resumen_p,
                    f"v{inter.calibracion_aplicada_id}" if inter.calibracion_aplicada_id else "No",
                ),
            )

    def _poblar_diff(
        self, actuales: dict[str, object], propuestos: dict[str, float]
    ) -> None:
        self.tabla_diff.delete(*self.tabla_diff.get_children())
        claves = sorted(
            set(actuales.keys()) | set(propuestos.keys()) | set(CATALOGO_COTAS_CALIBRACION.keys())
        )
        for k in claves:
            cota = CATALOGO_COTAS_CALIBRACION.get(k)
            val_act = actuales.get(k, cota.valor_por_defecto if cota else "—")
            val_prop = propuestos.get(k)
            rango = (
                f"[{cota.minimo:g} .. {cota.maximo:g}] {cota.unidad} (±{cota.delta_max_por_paso:g})"
                if cota
                else "Parámetro libre"
            )
            tag = ("cambio",) if val_prop is not None else ()
            self.tabla_diff.insert(
                "",
                "end",
                tags=tag,
                values=(
                    k,
                    str(val_act),
                    f"{val_prop:g}" if val_prop is not None else "— (sin cambio)",
                    rango,
                ),
            )

    def _poner_prompt(self, texto: str) -> None:
        self.txt_pregunta.delete("1.0", "end")
        self.txt_pregunta.insert("1.0", texto)

    def _escribir_diagnostico(self, texto: str) -> None:
        self.txt_diagnostico.configure(state="normal")
        self.txt_diagnostico.delete("1.0", "end")
        self.txt_diagnostico.insert("1.0", texto)
        self.txt_diagnostico.configure(state="disabled")

    # ── Consulta Async & Calibración ─────────────────────────────────────────
    def _consultar_async(self) -> None:
        if self._consultando:
            return
        pregunta = self.txt_pregunta.get("1.0", "end").strip()
        if not pregunta:
            return

        est_id = self.app.estacion_activa_id
        par_id = self._parcela_por_etiqueta.get(self.var_parcela.get())
        if est_id is None and par_id is None:
            messagebox.showinfo(
                "Contexto requerido",
                "Seleccione primero una estación en la barra superior o una parcela.",
                parent=self,
            )
            return

        self._consultando = True
        self.btn_consultar.configure(state="disabled")
        self.btn_aplicar.configure(state="disabled")
        self.var_estado_ia.set("⏳ Consultando al Orquestador IA (Gemini / Ollama / Reglas)...")

        def _tarea() -> None:
            try:
                res = self.app.contenedor.copiloto.consultar_copiloto(
                    pregunta,
                    estacion_id=est_id,
                    parcela_id=par_id,
                    usuario_id=self.app.actor.id,
                    aplicar_ajustes=False,
                )
                self.after(0, lambda r=res: self._al_responder(r))
            except Exception as exc:
                self.after(0, lambda e=exc: self._al_fallar(e))

        threading.Thread(target=_tarea, name="AquaTerra-CopilotoIA", daemon=True).start()

    def _al_responder(self, res) -> None:
        if not self.winfo_exists():
            return
        self._consultando = False
        self.btn_consultar.configure(state="normal")
        self._ultima_interaccion_id = res.interaccion.id

        p = res.propuesta
        aud = res.auditoria
        self.var_estado_ia.set(
            f"Proveedor: {p.proveedor_ia} · Confianza: {p.confianza:.0%} · Interacción #{res.interaccion.id}"
        )

        lineas = [
            f"DIAGNÓSTICO TÉCNICO:\n{p.diagnostico_tecnico}",
            f"\nJUSTIFICACIÓN AGRONÓMICA:\n{p.justificacion_agronomica}",
        ]
        if aud.advertencias_seguridad:
            lineas.append("\nADVERTENCIAS DE AUDITORÍA:\n• " + "\n• ".join(aud.advertencias_seguridad))
        self._escribir_diagnostico("\n".join(lineas))

        est_id = self.app.estacion_activa_id
        par_id = self._parcela_por_etiqueta.get(self.var_parcela.get())
        _, actuales = self.app.contenedor.copiloto.obtener_calibracion_efectiva(
            estacion_id=est_id, parcela_id=par_id
        )
        self._poblar_diff(actuales, p.ajustes_propuestos)
        if p.ajustes_propuestos and self.app.actor.es_admin:
            self.btn_aplicar.configure(state="normal")
        self._recargar_calibracion_e_historial()

    def _al_fallar(self, exc: Exception) -> None:
        if not self.winfo_exists():
            return
        self._consultando = False
        self.btn_consultar.configure(state="normal")
        self.var_estado_ia.set(f"Error al consultar Copiloto: {exc}")

    def _aplicar_propuesta(self) -> None:
        if self._ultima_interaccion_id is None:
            return
        ver = self.app.ejecutar_accion(
            lambda: self.app.contenedor.copiloto.aplicar_ajustes_interaccion(
                self._ultima_interaccion_id, autor_id=self.app.actor.id
            )
        )
        if ver is not None:
            messagebox.showinfo(
                "Calibración Aplicada",
                f"Nueva versión activa v{ver.version} guardada con trazabilidad.\nMotivo: {ver.motivo}",
                parent=self,
            )
            self.btn_aplicar.configure(state="disabled")
            self._recargar_calibracion_e_historial()

    def _rollback(self) -> None:
        est_id = self.app.estacion_activa_id
        par_id = self._parcela_por_etiqueta.get(self.var_parcela.get())
        ver = self.app.ejecutar_accion(
            lambda: self.app.contenedor.copiloto.revertir_calibracion(
                estacion_id=est_id, parcela_id=par_id, autor_id=self.app.actor.id
            ),
            titulo_error="Rollback no disponible",
        )
        if ver is not None:
            messagebox.showinfo(
                "Rollback Exitoso",
                f"Calibración revertida limpiamente a nueva versión activa v{ver.version}.",
                parent=self,
            )
            self._recargar_calibracion_e_historial()

    def _exportar_jsonl(self) -> None:
        ruta = filedialog.asksaveasfilename(
            parent=self,
            title="Exportar Dataset SFT (.jsonl)",
            defaultextension=".jsonl",
            initialfile="salviabiot_mandarino_sft.jsonl",
            filetypes=[("JSON Lines", "*.jsonl")],
        )
        if not ruta:
            return
        n = self.app.ejecutar_accion(
            lambda: self.app.contenedor.copiloto.exportar_dataset_entrenamiento_jsonl(Path(ruta))
        )
        if n is not None:
            messagebox.showinfo(
                "Dataset SFT Exportado",
                f"Se exportaron {n} ejemplos de entrenamiento a:\n{ruta}",
                parent=self,
            )
