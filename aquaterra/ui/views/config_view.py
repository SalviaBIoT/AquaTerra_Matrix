"""Vista 7 — Configuración de Conectores Híbridos, Estaciones IoT GPS y Usuarios."""

from __future__ import annotations

from tkinter import messagebox
from typing import TYPE_CHECKING

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, LEFT, RIGHT, VERTICAL, W, X, Y

from aquaterra.core.domain import Rol, TipoEstacion
from aquaterra.infrastructure.clima import (
    ALTITUD_UTP_PEREIRA_M,
    LATITUD_UTP_PEREIRA,
    LONGITUD_UTP_PEREIRA,
)

if TYPE_CHECKING:
    from aquaterra.ui.app import AplicacionMatrix


class VistaConfiguracion(ttk.Frame):
    """Administración gráfica completa para el cliente final (cero edición de consola)."""

    def __init__(self, maestro, app: AplicacionMatrix):
        super().__init__(maestro, padding=12)
        self.app = app
        self._construir()
        self.refrescar()

    def _construir(self) -> None:
        self.tabs = ttk.Notebook(self, bootstyle="primary")
        self.tabs.pack(fill=BOTH, expand=True)

        self.tab_conectores = ttk.Frame(self.tabs, padding=12)
        self.tab_nodos = ttk.Frame(self.tabs, padding=12)
        self.tab_usuarios = ttk.Frame(self.tabs, padding=12)

        self.tabs.add(self.tab_conectores, text=" 🔌 Conectores, IA Híbrida & Notificaciones ")
        self.tabs.add(self.tab_nodos, text=" 📡 Nodos IoT & Coordenadas GPS ")
        self.tabs.add(self.tab_usuarios, text=" 👥 Usuarios & Roles ")

        self._construir_tab_conectores()
        self._construir_tab_nodos()
        self._construir_tab_usuarios()

    def _construir_tab_conectores(self) -> None:
        cfg_ia = self.app.contenedor.copiloto.orquestador.config
        sinc = self.app.contenedor.sincronizacion

        self.var_ubidots = ttk.StringVar(value=sinc.ubidots._token)
        self.var_ia_prov = ttk.StringVar(value=cfg_ia.proveedor_preferido)
        self.var_ollama_url = ttk.StringVar(value=cfg_ia.ollama_base_url)
        self.var_ollama_mod = ttk.StringVar(value=cfg_ia.ollama_modelo)
        self.var_gemini_key = ttk.StringVar(value=cfg_ia.gemini_api_key or "")
        self.var_gemini_mod = ttk.StringVar(value=cfg_ia.gemini_modelo)
        self.var_webhook = ttk.StringVar(value=sinc.notificador._webhook_url)
        self.var_tg_token = ttk.StringVar(value=sinc.notificador._tg_token)
        self.var_tg_chat = ttk.StringVar(value=sinc.notificador._tg_chat_id)
        self.var_guardar_env = ttk.BooleanVar(value=False)

        marco = ttk.Labelframe(
            self.tab_conectores,
            text=" ⚙️ Parámetros en Vivo (Ubidots · Gemini/Ollama · n8n WhatsApp · Telegram) ",
            padding=14,
            bootstyle="info",
        )
        marco.pack(fill=X, pady=(0, 10))
        marco.columnconfigure((0, 1), weight=1)

        campos = (
            ("Token Ubidots Industrial (UBIDOTS_TOKEN):", self.var_ubidots, True, 0, 0),
            ("Proveedor IA Preferido (auto / gemini / ollama / local_reglas):", None, False, 0, 1),
            ("URL Servidor Ollama Local o LAN (AQUATERRA_OLLAMA_URL):", self.var_ollama_url, False, 1, 0),
            ("Modelo Ollama (ej. qwen2.5:3b / qwen2.5:0.5b):", self.var_ollama_mod, False, 1, 1),
            ("API Key Google AI Studio (GEMINI_API_KEY):", self.var_gemini_key, True, 2, 0),
            ("Modelo Gemini Cloud:", self.var_gemini_mod, False, 2, 1),
            ("Webhook n8n para WhatsApp / Notion (AQUATERRA_WEBHOOK_URL):", self.var_webhook, False, 3, 0),
            ("Telegram Bot Token (AQUATERRA_TELEGRAM_BOT_TOKEN):", self.var_tg_token, True, 3, 1),
            ("Telegram Chat ID destino (AQUATERRA_TELEGRAM_CHAT_ID):", self.var_tg_chat, False, 4, 0),
        )
        for etiq, var, oculto, f_idx, c_idx in campos:
            celda = ttk.Frame(marco, padding=4)
            celda.grid(row=f_idx, column=c_idx, sticky="ew")
            ttk.Label(celda, text=etiq, font=("Segoe UI", 8, "bold")).pack(anchor=W)
            if var is None:
                ttk.Combobox(
                    celda,
                    textvariable=self.var_ia_prov,
                    values=["auto", "ollama", "gemini", "local_reglas"],
                    state="readonly",
                ).pack(fill=X)
            else:
                ttk.Entry(celda, textvariable=var, show="•" if oculto else "").pack(fill=X)

        opciones = ttk.Frame(self.tab_conectores)
        opciones.pack(fill=X, pady=6)
        ttk.Checkbutton(
            opciones,
            text="Guardar también en archivo .env local del equipo (ignorado por Git)",
            variable=self.var_guardar_env,
            bootstyle="round-toggle",
        ).pack(side=LEFT)

        barra = ttk.Frame(self.tab_conectores, padding=(0, 8))
        barra.pack(fill=X)
        self.btn_guardar_cfg = ttk.Button(
            barra,
            text="💾 Aplicar Conectores en Caliente",
            bootstyle="success",
            command=self._guardar_conectores,
        )
        self.btn_guardar_cfg.pack(side=LEFT, padx=(0, 8))

        ttk.Button(
            barra,
            text="🔥 Precalentar GPU Ollama",
            bootstyle="primary-outline",
            command=self._precalentar_ollama,
        ).pack(side=LEFT, padx=(0, 8))

        self.btn_worker = ttk.Button(
            barra,
            text="⚡ Activar Worker Auto-Sync (15 min)",
            bootstyle="info-outline",
            command=self._toggle_worker,
        )
        self.btn_worker.pack(side=LEFT)

        if not self.app.actor.es_admin:
            self.btn_guardar_cfg.configure(state="disabled")

    def _construir_tab_nodos(self) -> None:
        self.tab_nodos.columnconfigure(0, weight=2)
        self.tab_nodos.columnconfigure(1, weight=3)
        self.tab_nodos.rowconfigure(0, weight=1)

        form = ttk.Labelframe(
            self.tab_nodos, text=" ➕ Registrar Nueva Estación IoT ", padding=14, bootstyle="success"
        )
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self.var_est_codigo = ttk.StringVar()
        self.var_est_nombre = ttk.StringVar()
        self.var_est_tipo = ttk.StringVar(value=TipoEstacion.TERRABIT_INTI.value)
        self.var_est_lat = ttk.StringVar(value=str(LATITUD_UTP_PEREIRA))
        self.var_est_lon = ttk.StringVar(value=str(LONGITUD_UTP_PEREIRA))
        self.var_est_alt = ttk.StringVar(value=str(ALTITUD_UTP_PEREIRA_M))

        for tit, var in (
            ("Código / Device Label (ej. terrabit-nodo02):", self.var_est_codigo),
            ("Nombre Descriptivo:", self.var_est_nombre),
        ):
            ttk.Label(form, text=tit, font=("Segoe UI", 9, "bold")).pack(anchor=W, pady=(2, 2))
            ttk.Entry(form, textvariable=var).pack(fill=X, pady=(0, 8))

        ttk.Label(form, text="Familia / Ecosistema:", font=("Segoe UI", 9, "bold")).pack(anchor=W)
        ttk.Combobox(
            form,
            textvariable=self.var_est_tipo,
            values=[t.value for t in TipoEstacion],
            state="readonly",
        ).pack(fill=X, pady=(2, 8))

        geo = ttk.Frame(form)
        geo.pack(fill=X, pady=(0, 10))
        geo.columnconfigure((0, 1, 2), weight=1)
        for col_i, (tit, var) in enumerate(
            (
                ("Latitud:", self.var_est_lat),
                ("Longitud:", self.var_est_lon),
                ("Altitud (m):", self.var_est_alt),
            )
        ):
            c = ttk.Frame(geo, padding=2)
            c.grid(row=0, column=col_i, sticky="ew")
            ttk.Label(c, text=tit, font=("Segoe UI", 8)).pack(anchor=W)
            ttk.Entry(c, textvariable=var).pack(fill=X)

        self.btn_reg_est = ttk.Button(
            form, text="📡 Registrar Estación", bootstyle="success", command=self._registrar_estacion
        )
        self.btn_reg_est.pack(fill=X, pady=(6, 6))
        if not self.app.actor.es_admin:
            self.btn_reg_est.configure(state="disabled")

        m_list = ttk.Labelframe(
            self.tab_nodos, text=" Estaciones Registradas ", padding=10, bootstyle="info"
        )
        m_list.grid(row=0, column=1, sticky="nsew")
        cols = ("id", "codigo", "nombre", "tipo", "coords")
        self.tabla_nodos = ttk.Treeview(m_list, columns=cols, show="headings", bootstyle="info")
        for c, tit, anch in (
            ("id", "ID", 40),
            ("codigo", "Código", 130),
            ("nombre", "Nombre", 150),
            ("tipo", "Familia", 105),
            ("coords", "GPS (Lat, Lon, Alt)", 170),
        ):
            self.tabla_nodos.heading(c, text=tit, anchor=W)
            self.tabla_nodos.column(c, width=anch, anchor=W)
        sn = ttk.Scrollbar(m_list, orient=VERTICAL, command=self.tabla_nodos.yview)
        self.tabla_nodos.configure(yscrollcommand=sn.set)
        sn.pack(side=RIGHT, fill=Y)
        self.tabla_nodos.pack(fill=BOTH, expand=True)

    def _construir_tab_usuarios(self) -> None:
        self.tab_usuarios.columnconfigure(0, weight=2)
        self.tab_usuarios.columnconfigure(1, weight=3)
        self.tab_usuarios.rowconfigure(0, weight=1)

        form = ttk.Labelframe(
            self.tab_usuarios, text=" 👤 Alta de Cuenta (PBKDF2-SHA256) ", padding=14, bootstyle="warning"
        )
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self.var_u_login = ttk.StringVar()
        self.var_u_nombre = ttk.StringVar()
        self.var_u_clave = ttk.StringVar()
        self.var_u_rol = ttk.StringVar(value=Rol.OPERADOR.value)

        for tit, var, oculto in (
            ("Usuario (login):", self.var_u_login, False),
            ("Nombre completo:", self.var_u_nombre, False),
            ("Contraseña inicial:", self.var_u_clave, True),
        ):
            ttk.Label(form, text=tit, font=("Segoe UI", 9, "bold")).pack(anchor=W, pady=(2, 2))
            ttk.Entry(form, textvariable=var, show="•" if oculto else "").pack(fill=X, pady=(0, 8))

        ttk.Label(form, text="Rol de Acceso:", font=("Segoe UI", 9, "bold")).pack(anchor=W)
        ttk.Combobox(
            form, textvariable=self.var_u_rol, values=[r.value for r in Rol], state="readonly"
        ).pack(fill=X, pady=(2, 12))

        self.btn_crear_usr = ttk.Button(
            form, text="➕ Crear Usuario", bootstyle="warning", command=self._crear_usuario
        )
        self.btn_crear_usr.pack(fill=X)
        if not self.app.actor.es_admin:
            self.btn_crear_usr.configure(state="disabled")

        m_u = ttk.Labelframe(
            self.tab_usuarios, text=" Cuentas del Sistema ", padding=10, bootstyle="secondary"
        )
        m_u.grid(row=0, column=1, sticky="nsew")
        cols = ("id", "usuario", "nombre", "rol", "activo")
        self.tabla_usuarios = ttk.Treeview(m_u, columns=cols, show="headings", bootstyle="secondary")
        for c, tit, anch in (
            ("id", "ID", 45),
            ("usuario", "Usuario", 120),
            ("nombre", "Nombre Completo", 190),
            ("rol", "Rol", 95),
            ("activo", "Estado", 85),
        ):
            self.tabla_usuarios.heading(c, text=tit, anchor=W)
            self.tabla_usuarios.column(c, width=anch, anchor=W)
        su = ttk.Scrollbar(m_u, orient=VERTICAL, command=self.tabla_usuarios.yview)
        self.tabla_usuarios.configure(yscrollcommand=su.set)
        su.pack(side=RIGHT, fill=Y)
        self.tabla_usuarios.pack(fill=BOTH, expand=True)

    # ── Carga & Acciones ─────────────────────────────────────────────────────
    def refrescar(self) -> None:
        self._refrescar_boton_worker()

        self.tabla_nodos.delete(*self.tabla_nodos.get_children())
        for e in self.app.contenedor.radar.listar_estaciones():
            coords = (
                f"{e.latitud:.4f}, {e.longitud:.4f} ({e.altitud_m or 0:.0f}m)"
                if e.latitud is not None and e.longitud is not None
                else "Sin GPS"
            )
            self.tabla_nodos.insert(
                "", "end", values=(e.id, e.codigo, e.nombre, e.tipo.value, coords)
            )

        self.tabla_usuarios.delete(*self.tabla_usuarios.get_children())
        for u in self.app.contenedor.auth.listar_usuarios():
            self.tabla_usuarios.insert(
                "",
                "end",
                values=(u.id, u.usuario, u.nombre, u.rol.value, "Activo" if u.activo else "Inactivo"),
            )

    def _refrescar_boton_worker(self) -> None:
        if self.app.contenedor.sincronizacion.worker_activo:
            self.btn_worker.configure(text="⏸️ Pausar Worker Auto-Sync", bootstyle="warning-outline")
        else:
            self.btn_worker.configure(text="⚡ Activar Worker Auto-Sync (15 min)", bootstyle="info-outline")

    def _guardar_conectores(self) -> None:
        res = self.app.ejecutar_accion(
            lambda: self.app.contenedor.sincronizacion.reconfigurar_conectores(
                self.app.actor,
                ubidots_token=self.var_ubidots.get(),
                ia_proveedor=self.var_ia_prov.get(),
                ia_ollama_url=self.var_ollama_url.get(),
                ia_ollama_modelo=self.var_ollama_mod.get(),
                ia_gemini_key=self.var_gemini_key.get(),
                ia_gemini_modelo=self.var_gemini_mod.get(),
                webhook_n8n_url=self.var_webhook.get(),
                telegram_bot_token=self.var_tg_token.get(),
                telegram_chat_id=self.var_tg_chat.get(),
                guardar_en_env_local=bool(self.var_guardar_env.get()),
            )
        )
        if res is not None:
            self.app.notificar_cambio_datos("⚙️ Conectores reconfigurados en caliente", bootstyle="success")
            messagebox.showinfo(
                "Conectores Actualizados",
                f"Proveedor IA activo: {res['ia_proveedor']}\n"
                f"Ubidots configurado: {'Sí' if res['ubidots_configurado'] else 'No'}\n"
                f"Canales notificación: {', '.join(res['canales_notificacion']) or 'Ninguno'}",
                parent=self,
            )

    def _precalentar_ollama(self) -> None:
        self.app.contenedor.copiloto.orquestador.precalentar_ollama_async()
        self.app.notificar_cambio_datos(
            "🔥 Precalentando modelo Ollama en GPU en segundo plano...", bootstyle="info"
        )

    def _toggle_worker(self) -> None:
        sinc = self.app.contenedor.sincronizacion
        if sinc.worker_activo:
            sinc.detener_worker_segundo_plano()
            self.app.notificar_cambio_datos("⏸️ Worker en segundo plano detenido", bootstyle="warning")
        else:
            sinc.iniciar_worker_segundo_plano(intervalo_segundos=900.0, precalentar_ollama=True)
            self.app.notificar_cambio_datos("⚡ Worker Auto-Sync 15 min iniciado", bootstyle="success")
        self._refrescar_boton_worker()

    def _registrar_estacion(self) -> None:
        def caso():
            return self.app.contenedor.sincronizacion.registrar_estacion(
                self.app.actor,
                codigo=self.var_est_codigo.get(),
                nombre=self.var_est_nombre.get(),
                tipo=TipoEstacion(self.var_est_tipo.get()),
                latitud=float(self.var_est_lat.get()),
                longitud=float(self.var_est_lon.get()),
                altitud_m=float(self.var_est_alt.get()),
            )

        est = self.app.ejecutar_accion(caso, titulo_error="No se pudo registrar la estación")
        if est is not None:
            self.var_est_codigo.set("")
            self.var_est_nombre.set("")
            self.refrescar()
            self.app.notificar_cambio_datos(
                f"📡 Estación '{est.codigo}' registrada", bootstyle="success"
            )

    def _crear_usuario(self) -> None:
        nuevo = self.app.ejecutar_accion(
            lambda: self.app.contenedor.auth.crear_usuario(
                self.app.actor,
                usuario=self.var_u_login.get(),
                nombre=self.var_u_nombre.get(),
                clave=self.var_u_clave.get(),
                rol=Rol(self.var_u_rol.get()),
            ),
            titulo_error="No se pudo crear el usuario",
        )
        if nuevo is not None:
            self.var_u_login.set("")
            self.var_u_nombre.set("")
            self.var_u_clave.set("")
            self.refrescar()
            messagebox.showinfo(
                "Usuario Creado",
                f"Cuenta '{nuevo.usuario}' ({nuevo.rol.value}) creada con hash PBKDF2-SHA256.",
                parent=self,
            )
