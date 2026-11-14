"""Marco de Mando Persistente (*App Shell*) para AquaTerra Matrix v5.0.

Unifica en una sola ventana raíz:
1. ``Top Command Bar``: selector global de estación, búsqueda inteligente
   (``Ctrl+K``), píldoras de conectividad Online/Offline y acciones rápidas
   (Sincronizar, Notificar 24h, Exportar ``.xlsx``, Conmutar Tema).
2. ``Sidebar`` lateral: navegación de las 7 secciones operativas, badge de
   alertas críticas y pie fijo de sesión (``Cerrar Sesión`` / ``Salir``).
3. ``Workspace`` central: contenedor donde se montan/desmontan las vistas
   sin fugas de memoria ni ventanas huérfanas (``DT-04`` / ``DT-05a``).
4. ``Status Footer``: estado SQLite WAL, worker en segundo plano y última sync.
"""

from __future__ import annotations

import contextlib
import logging
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, BOTTOM, LEFT, RIGHT, VERTICAL, W, X, Y

from aquaterra import __version__

if TYPE_CHECKING:
    from aquaterra.ui.app import AplicacionMatrix

log = logging.getLogger(__name__)


class AppShell(ttk.Frame):
    """Chasis principal persistente tras la autenticación."""

    def __init__(self, maestro, app: AplicacionMatrix):
        super().__init__(maestro)
        self.app = app
        self._botones_nav: dict[str, ttk.Button] = {}
        self._estacion_por_etiqueta: dict[str, int] = {}
        self._etiqueta_por_estacion: dict[int, str] = {}
        self._sincronizando = False

        self.var_estacion = ttk.StringVar()
        self.var_busqueda = ttk.StringVar()
        self.var_estado_footer = ttk.StringVar(value="Listo · Modo Híbrido Local-First activo")

        self._construir()
        self.recargar_estaciones()
        self.refrescar_estado()

    def _construir(self) -> None:
        # ── 1. Top Command Bar ───────────────────────────────────────────────
        self.topbar = ttk.Frame(self, padding=(12, 8))
        self.topbar.pack(side="top", fill=X)

        izq_top = ttk.Frame(self.topbar)
        izq_top.pack(side=LEFT, fill=X, expand=True)

        ttk.Label(izq_top, text="📡 Estación:", font=("Segoe UI", 9, "bold")).pack(
            side=LEFT, padx=(0, 6)
        )
        self.combo_estacion = ttk.Combobox(
            izq_top,
            textvariable=self.var_estacion,
            state="readonly",
            width=28,
        )
        self.combo_estacion.pack(side=LEFT, padx=(0, 12))
        self.combo_estacion.bind("<<ComboboxSelected>>", self._al_cambiar_combo_estacion)

        self.entrada_busqueda = ttk.Entry(
            izq_top, textvariable=self.var_busqueda, width=26
        )
        self.entrada_busqueda.pack(side=LEFT, padx=(0, 4))
        self.entrada_busqueda.bind("<Return>", lambda _e: self._ejecutar_busqueda())
        self.btn_buscar = ttk.Button(
            izq_top,
            text="🔍 Buscar",
            bootstyle="secondary-outline",
            command=self._ejecutar_busqueda,
        )
        self.btn_buscar.pack(side=LEFT, padx=(0, 12))

        # Píldoras de conectividad Online/Offline
        self.pildoras = ttk.Frame(izq_top)
        self.pildoras.pack(side=LEFT, padx=(0, 8))
        self.lbl_pill_ubidots = ttk.Label(
            self.pildoras, text=" ☁️ Ubidots ", bootstyle="secondary", padding=(6, 2)
        )
        self.lbl_pill_ubidots.pack(side=LEFT, padx=2)
        self.lbl_pill_clima = ttk.Label(
            self.pildoras, text=" 🌦️ Clima ", bootstyle="secondary", padding=(6, 2)
        )
        self.lbl_pill_clima.pack(side=LEFT, padx=2)
        self.lbl_pill_ia = ttk.Label(
            self.pildoras, text=" 🧠 IA ", bootstyle="info", padding=(6, 2)
        )
        self.lbl_pill_ia.pack(side=LEFT, padx=2)
        self.lbl_pill_radio = ttk.Label(
            self.pildoras, text=" 📻 Radio ", bootstyle="secondary", padding=(6, 2)
        )
        self.lbl_pill_radio.pack(side=LEFT, padx=2)

        # Acciones rápidas a la derecha
        der_top = ttk.Frame(self.topbar)
        der_top.pack(side=RIGHT)
        self.btn_sync = ttk.Button(
            der_top,
            text="🔄 Sync",
            bootstyle="info-outline",
            command=self._sincronizar_async,
        )
        self.btn_sync.pack(side=LEFT, padx=3)
        self.btn_notificar = ttk.Button(
            der_top,
            text="📲 Notificar 24h",
            bootstyle="success-outline",
            command=self._notificar_24h_async,
        )
        self.btn_notificar.pack(side=LEFT, padx=3)
        self.btn_excel = ttk.Button(
            der_top,
            text="📊 Excel .xlsx",
            bootstyle="warning-outline",
            command=self._exportar_xlsx,
        )
        self.btn_excel.pack(side=LEFT, padx=3)
        self.btn_tema = ttk.Button(
            der_top,
            text="☀️/🌙",
            bootstyle="secondary-outline",
            width=6,
            command=self.app.alternar_tema,
        )
        self.btn_tema.pack(side=LEFT, padx=(3, 0))

        ttk.Separator(self).pack(side="top", fill=X)

        # ── 2. Status Footer (empaquetado antes del cuerpo para fijarlo abajo) ─
        ttk.Separator(self).pack(side=BOTTOM, fill=X)
        self.footer = ttk.Frame(self, padding=(12, 4))
        self.footer.pack(side=BOTTOM, fill=X)
        self.lbl_footer_izq = ttk.Label(
            self.footer,
            text=f"SQLite3 WAL · AquaTerra Matrix v{__version__}",
            font=("Segoe UI", 8),
            style="ShellStatus.TLabel",
        )
        self.lbl_footer_izq.pack(side=LEFT)
        self.lbl_footer_der = ttk.Label(
            self.footer,
            textvariable=self.var_estado_footer,
            font=("Segoe UI", 8, "bold"),
            bootstyle="info",
        )
        self.lbl_footer_der.pack(side=RIGHT)

        # ── 3. Cuerpo Principal: Sidebar + Workspace ─────────────────────────
        cuerpo = ttk.Frame(self)
        cuerpo.pack(side="top", fill=BOTH, expand=True)

        self.sidebar = ttk.Frame(cuerpo, width=232, padding=12, style="Sidebar.TFrame")
        self.sidebar.pack(side=LEFT, fill=Y)
        self.sidebar.pack_propagate(False)

        ttk.Label(
            self.sidebar,
            text="AQUATERRA MATRIX",
            font=("Segoe UI", 12, "bold"),
            style="SidebarBrand.TLabel",
        ).pack(anchor=W, pady=(4, 0))
        ttk.Label(
            self.sidebar,
            text="Ecosistema Bio-IoT TerraBit",
            font=("Segoe UI", 8),
            style="SidebarMuted.TLabel",
        ).pack(anchor=W, pady=(0, 8))
        ttk.Separator(self.sidebar).pack(fill=X, pady=(0, 10))

        rutas: tuple[tuple[str, str, object], ...] = (
            ("dashboard", "📡  1. Radar & Pulso 24h", self.app.mostrar_dashboard),
            ("monitor", "📈  2. Telemetría Multi-Nodo", self.app.mostrar_monitor),
            ("parcelas", "🌱  3. Parcelas & Cultivos", self.app.mostrar_parcelas),
            ("riego", "💧  4. Riego, Candados & Bomba", self.app.mostrar_riego),
            ("copiloto", "🧠  5. Copiloto IA & Calibración", self.app.mostrar_copiloto),
            ("hardware", "📻  6. Radio nRF24 & MicroSD", self.app.mostrar_hardware),
            ("config", "⚙️  7. Nodos, Conectores & Users", self.app.mostrar_configuracion),
        )
        for clave, etiqueta, accion in rutas:
            btn = ttk.Button(
                self.sidebar,
                text=etiqueta,
                bootstyle="secondary-outline",
                command=accion,
            )
            btn.pack(fill=X, pady=3, ipady=4)
            self._botones_nav[clave] = btn

        # Pie de sesión fijo al fondo del Sidebar
        pie_sidebar = ttk.Frame(self.sidebar, style="Sidebar.TFrame")
        pie_sidebar.pack(side=BOTTOM, fill=X, pady=(10, 0))
        ttk.Separator(pie_sidebar).pack(fill=X, pady=(0, 8))

        usuario = self.app.actor
        ttk.Label(
            pie_sidebar,
            text=f"👤 {usuario.nombre}",
            font=("Segoe UI", 9, "bold"),
            style="SidebarBrand.TLabel",
        ).pack(anchor=W)
        ttk.Label(
            pie_sidebar,
            text=f"Rol activo: {usuario.rol.value.upper()}",
            font=("Segoe UI", 8),
            style="SidebarMuted.TLabel",
        ).pack(anchor=W, pady=(0, 8))

        ttk.Button(
            pie_sidebar,
            text="🔒 Cerrar Sesión",
            bootstyle="warning-outline",
            command=self.app.cerrar_sesion,
        ).pack(fill=X, pady=(0, 4))
        ttk.Button(
            pie_sidebar,
            text="⏻ Salir del Sistema",
            bootstyle="danger",
            command=self.app.salir,
        ).pack(fill=X)

        ttk.Separator(cuerpo, orient=VERTICAL).pack(side=LEFT, fill=Y)

        # Workspace central
        self.workspace = ttk.Frame(cuerpo)
        self.workspace.pack(side=LEFT, fill=BOTH, expand=True)

        # Atajo global Ctrl+K para ir directo al buscador inteligente
        self.app.raiz.bind("<Control-k>", self._foco_busqueda)

    # ── Navegación & Selección Global de Estación ────────────────────────────
    def _foco_busqueda(self, _evento=None) -> None:
        if self.winfo_exists():
            self.entrada_busqueda.focus_set()
            self.entrada_busqueda.select_range(0, "end")

    def marcar_vista_activa(self, clave: str) -> None:
        for k, btn in self._botones_nav.items():
            btn.configure(bootstyle="success" if k == clave else "secondary-outline")

    def recargar_estaciones(self) -> None:
        """Sincroniza el ComboBox superior con las estaciones registradas en SQLite."""
        estaciones = self.app.contenedor.radar.listar_estaciones()
        self._estacion_por_etiqueta.clear()
        self._etiqueta_por_estacion.clear()
        valores: list[str] = []
        for est in estaciones:
            et = f"[{est.id}] {est.codigo} · {est.nombre}"
            self._estacion_por_etiqueta[et] = est.id
            self._etiqueta_por_estacion[est.id] = et
            valores.append(et)

        self.combo_estacion["values"] = valores
        if not estaciones:
            self.app.estacion_activa_id = None
            self.var_estacion.set("Sin estaciones registradas")
            return

        if self.app.estacion_activa_id not in self._etiqueta_por_estacion:
            self.app.estacion_activa_id = estaciones[0].id
        self.var_estacion.set(self._etiqueta_por_estacion[self.app.estacion_activa_id])

    def seleccionar_estacion(self, estacion_id: int, *, notificar_vista: bool = True) -> None:
        if estacion_id in self._etiqueta_por_estacion:
            self.app.estacion_activa_id = estacion_id
            self.var_estacion.set(self._etiqueta_por_estacion[estacion_id])
            if notificar_vista and self.app._vista is not None:
                al_cambiar = getattr(self.app._vista, "al_cambiar_estacion", None)
                if callable(al_cambiar):
                    al_cambiar()

    def _al_cambiar_combo_estacion(self, _evento=None) -> None:
        est_id = self._estacion_por_etiqueta.get(self.var_estacion.get())
        if est_id is None:
            return
        self.app.estacion_activa_id = est_id
        if self.app._vista is not None:
            al_cambiar = getattr(self.app._vista, "al_cambiar_estacion", None)
            if callable(al_cambiar):
                al_cambiar()

    # ── Píldoras de Estado Híbrido (Online/Offline) ──────────────────────────
    def refrescar_estado(self) -> None:
        estado = self.app.contenedor.sincronizacion.resumen_estado_conectividad(
            verificar_ollama=False
        )
        ubidots_ok = bool(estado["ubidots_configurado"])
        clima_pts = int(estado["clima_puntos_cache"])
        ia_prov = str(estado["ia_proveedor"]).upper()
        ia_mod = (
            str(estado["ia_ollama_modelo"])
            if ia_prov == "OLLAMA"
            else (str(estado["ia_gemini_modelo"]) if ia_prov == "GEMINI" else ia_prov)
        )
        puertos = list(estado["puertos_serial"])
        worker = "Activo" if estado["worker_activo"] else "Manual"
        lecturas = int(estado["lecturas_totales"])
        ultima_sync = estado["ultima_sync_iso"] or "sin sync de red"

        self.lbl_pill_ubidots.configure(
            text=" ☁️ Ubidots: Listo " if ubidots_ok else " ☁️ Ubidots: Sin Token ",
            bootstyle="success" if ubidots_ok else "secondary",
        )
        self.lbl_pill_clima.configure(
            text=f" 🌦️ Clima: {clima_pts}h " if clima_pts > 0 else " 🌦️ Clima: Sin caché ",
            bootstyle="info" if clima_pts > 0 else "warning",
        )
        self.lbl_pill_ia.configure(
            text=f" 🧠 IA: {ia_mod} ",
            bootstyle="primary" if ia_prov != "LOCAL_REGLAS" else "secondary",
        )
        self.lbl_pill_radio.configure(
            text=f" 📻 Radio: {len(puertos)} COM " if puertos else " 📻 Radio: Sin COM ",
            bootstyle="success" if puertos else "secondary",
        )

        # Badge de alertas críticas en botón Radar
        radar = self.app.contenedor.radar.listar_radar_priorizado()
        criticas = sum(1 for r in radar if r.severidad.value == "critico")
        if "dashboard" in self._botones_nav:
            etiqueta = (
                f"📡  1. Radar ({criticas} ⚠️)"
                if criticas > 0
                else "📡  1. Radar & Pulso 24h"
            )
            self._botones_nav["dashboard"].configure(text=etiqueta)

        self.lbl_footer_izq.configure(
            text=(
                f"SQLite3 WAL · {lecturas} lecturas · Worker: {worker} · "
                f"Última sync: {ultima_sync} · v{__version__}"
            )
        )

    def publicar_estado(self, mensaje: str, *, bootstyle: str = "info") -> None:
        if not self.winfo_exists():
            return
        self.var_estado_footer.set(mensaje)
        self.lbl_footer_der.configure(bootstyle=bootstyle)

    # ── Acciones Globales del Top Command Bar ────────────────────────────────
    def _sincronizar_async(self) -> None:
        if self._sincronizando:
            return
        self._sincronizando = True
        self.btn_sync.configure(state="disabled")
        self.publicar_estado("⏳ Sincronizando Ubidots y Open-Meteo...", bootstyle="warning")

        def _tarea() -> None:
            try:
                res = self.app.contenedor.sincronizacion.sincronizar_todo_hibrido(dias_clima=2)
                self.after(0, lambda r=res: self._al_terminar_sync(r))
            except Exception as exc:
                self.after(0, lambda e=exc: self._al_fallar_sync(e))

        threading.Thread(target=_tarea, name="AquaTerra-ManualSync", daemon=True).start()

    def _al_terminar_sync(self, res) -> None:
        if not self.winfo_exists():
            return
        self._sincronizando = False
        self.btn_sync.configure(state="normal")
        nuevas_ub = sum(u.lecturas_nuevas_insertadas for u in res.ubidots)
        horas_cl = sum(c.puntos_guardados for c in res.clima)
        if res.online:
            self.publicar_estado(
                f"🟢 Sync OK: +{nuevas_ub} lecturas Ubidots · {horas_cl}h clima Open-Meteo",
                bootstyle="success",
            )
        else:
            self.publicar_estado(
                f"🟡 Modo Offline ({res.aviso or 'sin conexión'}); operando con caché SQLite local",
                bootstyle="warning",
            )
        self.recargar_estaciones()
        self.refrescar_estado()
        if self.app._vista is not None:
            refrescar = getattr(self.app._vista, "refrescar", None)
            if callable(refrescar):
                refrescar()

    def _al_fallar_sync(self, exc: Exception) -> None:
        if not self.winfo_exists():
            return
        self._sincronizando = False
        self.btn_sync.configure(state="normal")
        self.publicar_estado(f"🔴 Aviso de sincronización: {exc}", bootstyle="danger")

    def _notificar_24h_async(self) -> None:
        est_id = self.app.estacion_activa_id
        if est_id is None:
            messagebox.showinfo(
                "Notificar 24h",
                "Registre o seleccione primero una estación para generar su boletín 24h.",
                parent=self,
            )
            return

        canales = self.app.contenedor.sincronizacion.notificador.canales_configurados
        self.btn_notificar.configure(state="disabled")
        self.publicar_estado("⏳ Generando boletín ejecutivo 24h...", bootstyle="info")

        def _tarea() -> None:
            try:
                msg, envios = self.app.contenedor.sincronizacion.notificar_pulso_24h_estacion(est_id)
                self.after(0, lambda m=msg, ev=envios: self._al_terminar_notificacion(m, ev, canales))
            except Exception as exc:
                self.after(0, lambda e=exc: self._al_fallar_notificacion(e))

        threading.Thread(target=_tarea, name="AquaTerra-Notify24h", daemon=True).start()

    def _al_terminar_notificacion(self, mensaje: str, envios, canales) -> None:
        if not self.winfo_exists():
            return
        self.btn_notificar.configure(state="normal")
        exitosos = [e.canal for e in envios if e.enviado]
        if exitosos:
            self.publicar_estado(
                f"📲 Boletín 24h enviado vía {', '.join(exitosos)}", bootstyle="success"
            )
            messagebox.showinfo(
                "Reporte 24h Enviado",
                f"Enviado por: {', '.join(exitosos)}\n\n{mensaje}",
                parent=self,
            )
        else:
            aviso = (
                "No hay Webhook n8n ni Bot de Telegram configurados en Conectores.\n\n"
                if not canales
                else "No fue posible entregar por red en este momento.\n\n"
            )
            self.publicar_estado("🟡 Boletín generado localmente (sin canal remoto)", bootstyle="warning")
            messagebox.showinfo(
                "Boletín Ejecutivo 24h (Vista Previa Local)",
                f"{aviso}{mensaje}",
                parent=self,
            )

    def _al_fallar_notificacion(self, exc: Exception) -> None:
        if not self.winfo_exists():
            return
        self.btn_notificar.configure(state="normal")
        self.publicar_estado(f"🔴 Error al notificar: {exc}", bootstyle="danger")

    def _exportar_xlsx(self) -> None:
        est_id = self.app.estacion_activa_id
        if est_id is None:
            messagebox.showinfo(
                "Exportar Excel",
                "Seleccione o registre una estación antes de exportar el libro .xlsx.",
                parent=self,
            )
            return
        est = self.app.contenedor.radar.obtener_estacion(est_id)
        ruta = filedialog.asksaveasfilename(
            parent=self,
            title="Exportar Reporte Ejecutivo (.xlsx)",
            defaultextension=".xlsx",
            initialfile=f"reporte_{est.codigo}.xlsx",
            filetypes=[("Libro de Excel", "*.xlsx")],
        )
        if not ruta:
            return
        destino = self.app.ejecutar_accion(
            lambda: self.app.contenedor.exportacion.exportar_xlsx_estacion(est_id, Path(ruta)),
            titulo_error="Error al exportar .xlsx",
        )
        if destino is not None:
            self.publicar_estado(f"📊 Excel exportado: {Path(destino).name}", bootstyle="success")
            messagebox.showinfo(
                "Exportación Exitosa",
                f"Libro Excel multi-hoja generado en:\n{destino}",
                parent=self,
            )

    def _ejecutar_busqueda(self) -> None:
        consulta = self.var_busqueda.get().strip()
        if not consulta:
            messagebox.showinfo(
                "Búsqueda Inteligente",
                "Escriba un término (ej. 'riego', 'critico', 'calibracion', 'umbral').",
                parent=self,
            )
            return
        resultado = self.app.ejecutar_accion(
            lambda: self.app.contenedor.copiloto.buscar_inteligente_bitacora(consulta, limite=30),
            titulo_error="Error en búsqueda inteligente",
        )
        if resultado is None:
            return

        modal = ttk.Toplevel(self.app.raiz)
        modal.title(f"Resultados para '{resultado.consulta}' ({resultado.total_hallazgos})")
        modal.geometry("860x420")
        modal.transient(self.app.raiz)

        marco = ttk.Frame(modal, padding=12)
        marco.pack(fill=BOTH, expand=True)
        ttk.Label(
            marco,
            text=f"🔍 {resultado.total_hallazgos} coincidencias encontradas para \"{resultado.consulta}\"",
            font=("Segoe UI", 11, "bold"),
            bootstyle="info",
        ).pack(anchor=W, pady=(0, 8))

        cols = ("categoria", "titulo", "detalle", "fecha")
        tabla = ttk.Treeview(marco, columns=cols, show="headings", bootstyle="info")
        for col, tit, anch in (
            ("categoria", "Categoría", 120),
            ("titulo", "Resumen", 220),
            ("detalle", "Detalle Técnico", 340),
            ("fecha", "Marca Temporal", 150),
        ):
            tabla.heading(col, text=tit, anchor=W)
            tabla.column(col, width=anch, anchor=W)
        for item in resultado.items:
            tabla.insert(
                "",
                "end",
                values=(item.categoria, item.titulo, item.detalle, item.ts_iso or "—"),
            )
        scroll = ttk.Scrollbar(marco, orient=VERTICAL, command=tabla.yview)
        tabla.configure(yscrollcommand=scroll.set)
        scroll.pack(side=RIGHT, fill=Y)
        tabla.pack(fill=BOTH, expand=True)

    def destroy(self) -> None:
        with contextlib.suppress(Exception):
            self.app.raiz.unbind("<Control-k>")
        super().destroy()
