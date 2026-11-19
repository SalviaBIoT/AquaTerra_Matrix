"""Vista 6 — Gateway USB-Serial (nRF24L01+ PA+LNA / LoRa), Escáner MicroSD y Reparador RTC."""

from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, LEFT, RIGHT, VERTICAL, W, X, Y

if TYPE_CHECKING:
    from aquaterra.ui.app import AplicacionMatrix


class VistaHardware(ttk.Frame):
    """Ingesta física de campo: antena USB-Serial, tarjetas MicroSD y reparación de reloj RTC."""

    def __init__(self, maestro, app: AplicacionMatrix):
        super().__init__(maestro, padding=12)
        self.app = app
        self._puertos_map: dict[str, str] = {}
        self._archivos_detectados: dict[str, Path] = {}

        self.var_puerto = ttk.StringVar()
        self.var_baud = ttk.IntVar(value=115200)
        self.var_dir_scan = ttk.StringVar(value=str(Path.cwd()))
        self.var_log_radio = ttk.StringVar(
            value="Listo para recibir tramas compactas nRF24L01+ (2.4 GHz) o LoRa."
        )
        self._construir()
        self.refrescar()

    def _construir(self) -> None:
        self.tabs = ttk.Notebook(self, bootstyle="info")
        self.tabs.pack(fill=BOTH, expand=True)

        self.tab_radio = ttk.Frame(self.tabs, padding=10)
        self.tab_sd = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(self.tab_radio, text=" 📻 Gateway Radio nRF24L01+ / LoRa ")
        self.tabs.add(self.tab_sd, text=" 💾 Escáner MicroSD, Eventos & RTC ")

        self._construir_tab_radio()
        self._construir_tab_sd()

    def _construir_tab_radio(self) -> None:
        m_com = ttk.Labelframe(
            self.tab_radio,
            text=" 🔌 Receptor ESP32 Gateway conectado por USB-Serial ",
            padding=12,
            bootstyle="success",
        )
        m_com.pack(fill=X, pady=(0, 10))

        fila = ttk.Frame(m_com)
        fila.pack(fill=X)
        ttk.Label(fila, text="Puerto COM:", font=("Segoe UI", 9, "bold")).pack(side=LEFT, padx=(0, 6))
        self.combo_com = ttk.Combobox(fila, textvariable=self.var_puerto, state="readonly", width=34)
        self.combo_com.pack(side=LEFT, padx=(0, 8))
        ttk.Label(fila, text="Baudrate:").pack(side=LEFT, padx=(0, 4))
        ttk.Combobox(
            fila,
            textvariable=self.var_baud,
            values=[9600, 57600, 115200, 230400],
            state="readonly",
            width=10,
        ).pack(side=LEFT, padx=(0, 8))
        ttk.Button(
            fila, text="🔄 Buscar Puertos", bootstyle="secondary-outline", command=self._cargar_puertos
        ).pack(side=LEFT, padx=(0, 6))
        ttk.Button(
            fila,
            text="📡 Leer Lote USB-Serial",
            bootstyle="success",
            command=self._leer_serial,
        ).pack(side=RIGHT)

        m_sim = ttk.Labelframe(
            self.tab_radio,
            text=" 📨 Decodificador Directo nRF24L01+ (32 bytes aire → Derivación VPD) ",
            padding=12,
            bootstyle="info",
        )
        m_sim.pack(fill=BOTH, expand=True)

        ttk.Label(
            m_sim,
            text="Formato compacto: NRF24|<device_label>|<var1=val1,var2=val2,...> (o JSON TerraBit Frame v1)",
            font=("Segoe UI", 9),
            bootstyle="secondary",
        ).pack(anchor=W, pady=(0, 6))

        self.txt_tramas = ttk.Text(m_sim, height=8, wrap="none")
        self.txt_tramas.pack(fill=BOTH, expand=True, pady=(0, 8))
        self.txt_tramas.insert(
            "1.0",
            "NRF24|inbeersa-nodo01|temperatura_interna=29.4,humedad_interna=75.0,temperatura_externa=21.2,actividad_pir=1,lluvia_evento=0\n"
            "NRF24|terrabit-nodointi|suelo_a=68.5,suelo_b=84.2,temp_aire=20.4,hum_aire=78.5,temp_raiz=21.0\n",
        )

        barra_sim = ttk.Frame(m_sim)
        barra_sim.pack(fill=X)
        ttk.Label(
            barra_sim, textvariable=self.var_log_radio, font=("Segoe UI", 9), bootstyle="info"
        ).pack(side=LEFT)
        ttk.Button(
            barra_sim,
            text="⚡ Decodificar e Ingerir en SQLite",
            bootstyle="primary",
            command=self._ingerir_buffer_radio,
        ).pack(side=RIGHT)

    def _construir_tab_sd(self) -> None:
        self.tab_sd.rowconfigure(1, weight=1)
        self.tab_sd.columnconfigure(0, weight=1)

        m_dir = ttk.Labelframe(
            self.tab_sd, text=" 📁 Escaneo de Tarjeta MicroSD / Carpeta de Campo ", padding=10, bootstyle="warning"
        )
        m_dir.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ttk.Entry(m_dir, textvariable=self.var_dir_scan, width=54).pack(
            side=LEFT, fill=X, expand=True, padx=(0, 6)
        )
        ttk.Button(
            m_dir, text="📂 Examinar", bootstyle="secondary-outline", command=self._elegir_carpeta
        ).pack(side=LEFT, padx=3)
        ttk.Button(
            m_dir, text="🔍 Escanear Carpeta", bootstyle="warning", command=self._escanear_carpeta
        ).pack(side=LEFT, padx=3)
        ttk.Button(
            m_dir, text="💿 Escanear Unidades SD (D:..H:)", bootstyle="info-outline", command=self._escanear_unidades
        ).pack(side=LEFT, padx=3)

        cuerpo = ttk.Frame(self.tab_sd)
        cuerpo.grid(row=1, column=0, sticky="nsew")
        cuerpo.columnconfigure((0, 1), weight=1)
        cuerpo.rowconfigure(0, weight=1)

        m_arch = ttk.Labelframe(cuerpo, text=" Archivos Detectados ", padding=8, bootstyle="info")
        m_arch.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        cols_a = ("archivo", "familia", "tamano")
        self.tabla_arch = ttk.Treeview(m_arch, columns=cols_a, show="headings", bootstyle="info")
        for c, tit, anch in (
            ("archivo", "Archivo", 190),
            ("familia", "Tipo Inferido", 125),
            ("tamano", "Tamaño", 85),
        ):
            self.tabla_arch.heading(c, text=tit, anchor=W)
            self.tabla_arch.column(c, width=anch, anchor=W)
        sa = ttk.Scrollbar(m_arch, orient=VERTICAL, command=self.tabla_arch.yview)
        self.tabla_arch.configure(yscrollcommand=sa.set)
        sa.pack(side=RIGHT, fill=Y)
        self.tabla_arch.pack(fill=BOTH, expand=True, pady=(0, 8))

        bar_a = ttk.Frame(m_arch)
        bar_a.pack(fill=X)
        ttk.Button(
            bar_a,
            text="📥 Importar a Estación Activa",
            bootstyle="success",
            command=self._importar_archivo_seleccionado,
        ).pack(side=LEFT, padx=(0, 6))
        ttk.Button(
            bar_a,
            text="🔧 Reparar Reloj RTC (calidad=2)",
            bootstyle="danger-outline",
            command=self._reparar_rtc,
        ).pack(side=RIGHT)

        m_ev = ttk.Labelframe(
            cuerpo, text=" Eventos Recientes de la Estación ", padding=8, bootstyle="secondary"
        )
        m_ev.grid(row=0, column=1, sticky="nsew")
        cols_e = ("fecha", "tipo", "detalle")
        self.tabla_ev = ttk.Treeview(m_ev, columns=cols_e, show="headings", bootstyle="secondary")
        for c, tit, anch in (
            ("fecha", "Marca Temporal", 145),
            ("tipo", "Tipo Evento", 125),
            ("detalle", "Detalle / Archivo", 190),
        ):
            self.tabla_ev.heading(c, text=tit, anchor=W)
            self.tabla_ev.column(c, width=anch, anchor=W)
        se = ttk.Scrollbar(m_ev, orient=VERTICAL, command=self.tabla_ev.yview)
        self.tabla_ev.configure(yscrollcommand=se.set)
        se.pack(side=RIGHT, fill=Y)
        self.tabla_ev.pack(fill=BOTH, expand=True)

    # ── Acciones ─────────────────────────────────────────────────────────────
    def refrescar(self) -> None:
        self._cargar_puertos()
        self._cargar_eventos_estacion()

    def al_cambiar_estacion(self) -> None:
        self._cargar_eventos_estacion()

    def _cargar_puertos(self) -> None:
        puertos = self.app.contenedor.sincronizacion.puertos_serial_disponibles()
        self._puertos_map = {desc: dev for dev, desc in puertos}
        valores = list(self._puertos_map.keys())
        self.combo_com["values"] = valores
        if valores:
            self.combo_com.current(0)
        else:
            self.combo_com.set("Sin puertos USB-Serial detectados")

    def _leer_serial(self) -> None:
        puerto = self._puertos_map.get(self.var_puerto.get())
        if not puerto:
            messagebox.showwarning(
                "Puerto Serial",
                "No hay ningún puerto COM válido seleccionado.",
                parent=self,
            )
            return
        res = self.app.ejecutar_accion(
            lambda: self.app.contenedor.sincronizacion.leer_puerto_serial_lote(
                puerto, baudrate=int(self.var_baud.get())
            ),
            titulo_error="Error de lectura USB-Serial",
        )
        if res is None:
            return
        total = sum(r.lecturas_insertadas for r in res)
        self.var_log_radio.set(
            f"📻 {puerto}: {len(res)} tramas decodificadas · +{total} lecturas insertadas."
        )
        self.app.notificar_cambio_datos(
            f"📻 Gateway {puerto}: +{total} lecturas radio", bootstyle="success"
        )

    def _ingerir_buffer_radio(self) -> None:
        lineas = [ln.strip() for ln in self.txt_tramas.get("1.0", "end").splitlines() if ln.strip()]
        if not lineas:
            return
        res = self.app.ejecutar_accion(
            lambda: self.app.contenedor.sincronizacion.ingerir_lote_lineas_gateway(lineas)
        )
        if res is None:
            return
        recibidas = sum(r.lecturas_recibidas for r in res)
        insertadas = sum(r.lecturas_insertadas for r in res)
        self.var_log_radio.set(
            f"✅ {len(res)} tramas válidas · {recibidas} métricas derivadas (incl. VPD/delta_temp) · "
            f"+{insertadas} lecturas nuevas en SQLite."
        )
        self.app.notificar_cambio_datos(
            f"📻 Ingesta radio: +{insertadas} lecturas", bootstyle="success"
        )

    def _elegir_carpeta(self) -> None:
        carpeta = filedialog.askdirectory(parent=self, title="Seleccione carpeta o unidad MicroSD")
        if carpeta:
            self.var_dir_scan.set(carpeta)
            self._escanear_carpeta()

    def _escanear_carpeta(self) -> None:
        self._poblar_archivos([Path(self.var_dir_scan.get())])

    def _escanear_unidades(self) -> None:
        unidades = [Path(f"{letra}:\\") for letra in "DEFGH" if Path(f"{letra}:\\").exists()]
        if not unidades:
            messagebox.showinfo(
                "Unidades Extraíbles",
                "No se detectaron unidades D:..H:. Puede seleccionar una carpeta manualmente.",
                parent=self,
            )
            return
        self._poblar_archivos(unidades)

    def _poblar_archivos(self, rutas: list[Path]) -> None:
        self.tabla_arch.delete(*self.tabla_arch.get_children())
        self._archivos_detectados.clear()
        hallados = self.app.contenedor.radar.detectar_archivos_estacion(rutas)
        for idx, item in enumerate(hallados):
            iid = str(idx)
            self._archivos_detectados[iid] = item.ruta_archivo
            self.tabla_arch.insert(
                "",
                "end",
                iid=iid,
                values=(
                    item.ruta_archivo.name,
                    item.tipo_estacion_inferido.value,
                    f"{item.tamano_bytes / 1024:.1f} KB",
                ),
            )
        if not hallados:
            messagebox.showinfo(
                "Escáner MicroSD",
                "No se encontraron archivos CSV/JSONL reconocidos de estaciones SalviaBIoT en la ruta indicada.",
                parent=self,
            )

    def _importar_archivo_seleccionado(self) -> None:
        est_id = self.app.estacion_activa_id
        sel = self.tabla_arch.selection()
        if est_id is None or not sel:
            messagebox.showwarning(
                "Importar Archivo",
                "Seleccione una estación arriba y un archivo detectado en la tabla.",
                parent=self,
            )
            return
        ruta = self._archivos_detectados[sel[0]]
        res = self.app.ejecutar_accion(
            lambda: self.app.contenedor.radar.importar_archivo_estacion(est_id, ruta),
            titulo_error="Error al importar archivo",
        )
        if res is not None:
            messagebox.showinfo(
                "Importación Exitosa",
                f"Archivo: {res.archivo_origen.name}\n"
                f"Lecturas nuevas: {res.lecturas_nuevas}\nEventos nuevos: {res.eventos_nuevos}",
                parent=self,
            )
            self._cargar_eventos_estacion()
            self.app.notificar_cambio_datos(
                f"💾 MicroSD: +{res.lecturas_nuevas} lecturas importadas", bootstyle="success"
            )

    def _reparar_rtc(self) -> None:
        est_id = self.app.estacion_activa_id
        if est_id is None:
            return
        n = self.app.ejecutar_accion(
            lambda: self.app.contenedor.sincronizacion.reparar_rtc_estacion(self.app.actor, est_id),
            titulo_error="Error al reparar RTC",
        )
        if n is not None:
            messagebox.showinfo(
                "Reparación RTC Completada",
                f"Se reconstruyeron {n} marcas temporales RTC corruptas (marcadas con calidad=2).",
                parent=self,
            )
            self.app.notificar_cambio_datos(f"🔧 RTC reparado ({n} lecturas)", bootstyle="info")

    def _cargar_eventos_estacion(self) -> None:
        self.tabla_ev.delete(*self.tabla_ev.get_children())
        est_id = self.app.estacion_activa_id
        if est_id is None:
            return
        for ev in self.app.contenedor.radar.listar_eventos_estacion(est_id, limite=40):
            det = ev.valor_texto or (Path(ev.archivo_ruta).name if ev.archivo_ruta else "—")
            self.tabla_ev.insert(
                "", "end", values=(ev.ts_iso[:19].replace("T", " "), ev.tipo_evento, det)
            )
