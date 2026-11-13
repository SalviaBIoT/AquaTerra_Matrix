"""CRUD de parcelas sobre ``ServicioParcelas``.

Cambios frente a v3.2:
- El ``iid`` de cada fila del Treeview ES el id de la parcela: la selección ya no
  depende de la posición en la tabla ni del nombre.
- "Eliminar" pasa a "Archivar" (eliminación lógica, fix DT-01).
- Crear y actualizar comparten validación de dominio (fix DT-03).
"""

from __future__ import annotations

from tkinter import messagebox
from typing import TYPE_CHECKING

import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, BOTTOM, CENTER, LEFT, RIGHT, VERTICAL, W, X, Y

from aquaterra.core.agronomia.hidrico import EstadoHumedad, clasificar_humedad
from aquaterra.core.domain import CULTIVOS_SOPORTADOS, Parcela, TipoSuelo

if TYPE_CHECKING:
    from aquaterra.ui.app import AplicacionMatrix

_COLUMNAS = (
    ("id", "ID", 50, CENTER),
    ("nombre", "Nombre Parcela", 180, W),
    ("cultivo", "Cultivo", 100, CENTER),
    ("area", "Área (m²)", 90, CENTER),
    ("humedad", "Humedad %", 90, CENTER),
    ("suelo", "Suelo", 100, CENTER),
    ("riego", "Riego Auto", 100, CENTER),
)


class VistaParcelas(ttk.Frame):
    def __init__(self, maestro, app: AplicacionMatrix):
        super().__init__(maestro)
        self.app = app
        self.servicio = app.contenedor.parcelas
        self.id_seleccionado: int | None = None
        self._parcelas: dict[int, Parcela] = {}
        self._construir()
        self._recargar_tabla()

    # ── Construcción ──────────────────────────────────────────────────────────
    def _construir(self) -> None:
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=3)
        self.rowconfigure(0, weight=1)

        form = ttk.Labelframe(self, text="Detalles de la Parcela", padding=20, bootstyle="info")
        form.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)

        self.var_nombre = ttk.StringVar()
        self.var_cultivo = ttk.StringVar(value=CULTIVOS_SOPORTADOS[0])
        self.var_area = ttk.StringVar()
        self.var_suelo = ttk.StringVar(value=TipoSuelo.FRANCO.value)
        self.var_riego = ttk.BooleanVar(value=False)
        self.var_humedad = ttk.DoubleVar(value=0)

        negrita = ("Helvetica", 10, "bold")
        ttk.Label(form, text="Nombre Parcela:", font=negrita).pack(fill=X, pady=(0, 5))
        ttk.Entry(form, textvariable=self.var_nombre).pack(fill=X, pady=(0, 15))

        ttk.Label(form, text="Tipo de Cultivo:", font=negrita).pack(fill=X, pady=(0, 5))
        ttk.Combobox(form, textvariable=self.var_cultivo, values=list(CULTIVOS_SOPORTADOS),
                     state="readonly").pack(fill=X, pady=(0, 15))

        ttk.Label(form, text="Área (m²):", font=negrita).pack(fill=X, pady=(0, 5))
        ttk.Entry(form, textvariable=self.var_area).pack(fill=X, pady=(0, 15))

        ttk.Separator(form).pack(fill=X, pady=5)
        ttk.Label(form, text="Tipo de Suelo:", font=negrita).pack(fill=X, pady=(10, 5))
        radios = ttk.Frame(form)
        radios.pack(fill=X, pady=(0, 15))
        for suelo in TipoSuelo:
            ttk.Radiobutton(radios, text=suelo.value, variable=self.var_suelo, value=suelo.value).pack(
                side=LEFT, padx=(0, 10))

        cabecera = ttk.Frame(form)
        cabecera.pack(fill=X, pady=(5, 0))
        ttk.Label(cabecera, text="Humedad del Suelo (%):", font=negrita).pack(side=LEFT)
        self.lbl_humedad = ttk.Label(cabecera, text="0 %", font=negrita, bootstyle="info")
        self.lbl_humedad.pack(side=RIGHT)
        ttk.Scale(form, from_=0, to=100, variable=self.var_humedad, bootstyle="info",
                  command=lambda _v: self._refrescar_etiqueta_humedad()).pack(fill=X, pady=(5, 15))

        ttk.Separator(form).pack(fill=X, pady=5)
        ttk.Checkbutton(form, text="Sistema de Riego Automático Activo", variable=self.var_riego,
                        bootstyle="round-toggle").pack(fill=X, pady=15)

        botones = ttk.Frame(form)
        botones.pack(fill=X, pady=10)
        botones.columnconfigure((0, 1), weight=1)
        self.btn_guardar = ttk.Button(botones, text="Guardar", bootstyle="success", command=self._guardar)
        self.btn_actualizar = ttk.Button(botones, text="Actualizar", bootstyle="info", command=self._actualizar)
        self.btn_limpiar = ttk.Button(botones, text="Limpiar", bootstyle="secondary", command=self._limpiar)
        self.btn_archivar = ttk.Button(botones, text="Archivar", bootstyle="danger", command=self._archivar)
        self.btn_guardar.grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        self.btn_actualizar.grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        self.btn_limpiar.grid(row=1, column=0, sticky="ew", padx=2, pady=2)
        self.btn_archivar.grid(row=1, column=1, sticky="ew", padx=2, pady=2)

        if not self.app.actor.es_admin:
            for boton in (self.btn_guardar, self.btn_actualizar, self.btn_archivar):
                boton.configure(state="disabled")

        ttk.Frame(form).pack(expand=True)
        ttk.Button(form, text="⬅ Volver al Menú Principal", bootstyle="secondary-outline", width=25,
                   command=self.app.mostrar_dashboard).pack(side=BOTTOM, anchor=W, pady=10)

        marco_tabla = ttk.Labelframe(self, text="Listado de Parcelas Activas", padding=10)
        marco_tabla.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
        self.tabla = ttk.Treeview(marco_tabla, columns=[c[0] for c in _COLUMNAS], show="headings",
                                  bootstyle="success")
        for clave, titulo, ancho, ancla in _COLUMNAS:
            self.tabla.heading(clave, text=titulo, anchor=ancla)
            self.tabla.column(clave, width=ancho, minwidth=40, anchor=ancla, stretch=clave != "id")
        self.tabla.tag_configure("critico", foreground="#d9534f")
        barra = ttk.Scrollbar(marco_tabla, orient=VERTICAL, command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=barra.set)
        barra.pack(side=RIGHT, fill=Y)
        self.tabla.pack(fill=BOTH, expand=True)
        self.tabla.bind("<<TreeviewSelect>>", self._al_seleccionar)
        self.tabla.bind("<Button-1>", self._al_clic_fondo)

    # ── Datos ─────────────────────────────────────────────────────────────────
    def _recargar_tabla(self) -> None:
        parcelas = self.app.ejecutar_accion(self.servicio.listar) or []
        self._parcelas = {p.id: p for p in parcelas}
        self.tabla.delete(*self.tabla.get_children())
        for p in parcelas:
            etiqueta = ("critico",) if clasificar_humedad(p.humedad_pct) is EstadoHumedad.CRITICO else ()
            self.tabla.insert("", "end", iid=str(p.id), tags=etiqueta, values=(
                p.id, p.nombre, p.cultivo, f"{p.area_m2:g}", f"{p.humedad_pct:.0f}",
                p.tipo_suelo.value, "Activo" if p.riego_auto else "Inactivo",
            ))

    def _campos_formulario(self) -> dict:
        return {
            "nombre": self.var_nombre.get(),
            "cultivo": self.var_cultivo.get(),
            "area": self.var_area.get(),
            "humedad": round(self.var_humedad.get()),
            "suelo": self.var_suelo.get(),
            "riego_auto": self.var_riego.get(),
        }

    def _refrescar_etiqueta_humedad(self) -> None:
        self.lbl_humedad.config(text=f"{round(self.var_humedad.get())} %")

    # ── Acciones ──────────────────────────────────────────────────────────────
    def _guardar(self) -> None:
        if self.app.ejecutar_accion(lambda: self.servicio.crear(self.app.actor, **self._campos_formulario())):
            messagebox.showinfo("Éxito", "Parcela registrada.", parent=self)
            self._limpiar()
            self._recargar_tabla()

    def _actualizar(self) -> None:
        if self.id_seleccionado is None:
            messagebox.showwarning("Atención", "Seleccione una parcela para editar.", parent=self)
            return
        pid = self.id_seleccionado
        if self.app.ejecutar_accion(lambda: self.servicio.actualizar(self.app.actor, pid, **self._campos_formulario())):
            messagebox.showinfo("Éxito", "Información actualizada.", parent=self)
            self._limpiar()
            self._recargar_tabla()

    def _archivar(self) -> None:
        if self.id_seleccionado is None:
            messagebox.showwarning("Atención", "Seleccione una parcela para archivar.", parent=self)
            return
        pid = self.id_seleccionado
        nombre = self._parcelas[pid].nombre
        if not messagebox.askyesno(
            "Confirmar archivo",
            f"¿Archivar la parcela #{pid} '{nombre}'?\n\nSu historial de riegos se conserva "
            "y el ID no será reutilizado.", parent=self,
        ):
            return
        if self.app.ejecutar_accion(lambda: self.servicio.archivar(self.app.actor, pid)):
            messagebox.showinfo("Éxito", f"Parcela #{pid} archivada.", parent=self)
            self._limpiar()
            self._recargar_tabla()

    def _limpiar(self) -> None:
        self.var_nombre.set("")
        self.var_area.set("")
        self.var_cultivo.set(CULTIVOS_SOPORTADOS[0])
        self.var_riego.set(False)
        self.var_suelo.set(TipoSuelo.FRANCO.value)
        self.var_humedad.set(0)
        self._refrescar_etiqueta_humedad()
        self.id_seleccionado = None
        if self.tabla.selection():
            self.tabla.selection_remove(self.tabla.selection())

    def _al_seleccionar(self, _evento=None) -> None:
        seleccion = self.tabla.selection()
        if not seleccion:
            return
        parcela = self._parcelas.get(int(seleccion[0]))
        if parcela is None:
            return
        self.id_seleccionado = parcela.id
        self.var_nombre.set(parcela.nombre)
        self.var_cultivo.set(parcela.cultivo)
        self.var_area.set(f"{parcela.area_m2:g}")
        self.var_humedad.set(parcela.humedad_pct)
        self._refrescar_etiqueta_humedad()
        self.var_suelo.set(parcela.tipo_suelo.value)
        self.var_riego.set(parcela.riego_auto)

    def _al_clic_fondo(self, evento) -> None:
        if self.tabla.identify_region(evento.x, evento.y) == "nothing":
            self._limpiar()
