import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import messagebox
from models.data_manager import GestorDatos


class VentanaParcelas:
    def __init__(self, ventana_padre, rol_usuario):
        self.padre = ventana_padre
        self.rol_usuario = rol_usuario

        self.ventana = ttk.Toplevel(ventana_padre)
        self.ventana.title("Gestión de Parcelas - AquaUTP")
        self.ventana.geometry("1100x650")

        self.gestor = GestorDatos()
        self.id_seleccionado = None

        self.ventana.protocol("WM_DELETE_WINDOW", self._al_cerrar_ventana)

        self._configurar_interfaz()
        self._cargar_datos_tabla()

    def _configurar_interfaz(self):
        """Construcción visual optimizada."""

        self.ventana.columnconfigure(0, weight=1)  # Panel Izquierdo
        self.ventana.columnconfigure(1, weight=3)  # Panel Derecho (Más ancho para la tabla)
        self.ventana.rowconfigure(0, weight=1)

        # === PANEL IZQUIERDO: FORMULARIO ===
        marco_formulario = ttk.Labelframe(self.ventana, text="Detalles de la Parcela", padding=20, bootstyle="info")
        marco_formulario.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)

        # Variables de Control
        self.var_nombre = ttk.StringVar()
        self.var_cultivo = ttk.StringVar()
        self.var_area = ttk.StringVar()
        self.var_suelo = ttk.StringVar(value="Franco")
        self.var_riego = ttk.BooleanVar(value=False)
        self.var_humedad = ttk.IntVar(value=0)

        # --- CAMPOS ---
        ttk.Label(marco_formulario, text="Nombre Parcela:", font=("Helvetica", 10, "bold")).pack(fill=X, pady=(0, 5))
        ttk.Entry(marco_formulario, textvariable=self.var_nombre).pack(fill=X, pady=(0, 15))

        ttk.Label(marco_formulario, text="Tipo de Cultivo:", font=("Helvetica", 10, "bold")).pack(fill=X, pady=(0, 5))
        combo_cultivo = ttk.Combobox(
            marco_formulario,
            textvariable=self.var_cultivo,
            values=["Maiz", "Tomate", "Fresas", "Hortalizas", "Flores"],
            state="readonly"
        )
        combo_cultivo.pack(fill=X, pady=(0, 15))
        combo_cultivo.current(0)

        ttk.Label(marco_formulario, text="Área (m²):", font=("Helvetica", 10, "bold")).pack(fill=X, pady=(0, 5))
        ttk.Entry(marco_formulario, textvariable=self.var_area).pack(fill=X, pady=(0, 15))

        # --- SUELO ---
        ttk.Separator(marco_formulario).pack(fill=X, pady=5)
        ttk.Label(marco_formulario, text="Tipo de Suelo:", font=("Helvetica", 10, "bold")).pack(fill=X, pady=(10, 5))

        marco_radios = ttk.Frame(marco_formulario)
        marco_radios.pack(fill=X, pady=(0, 15))
        ttk.Radiobutton(marco_radios, text="Franco", variable=self.var_suelo, value="Franco").pack(side=LEFT,
                                                                                                   padx=(0, 10))
        ttk.Radiobutton(marco_radios, text="Arenoso", variable=self.var_suelo, value="Arenoso").pack(side=LEFT, padx=10)
        ttk.Radiobutton(marco_radios, text="Arcilloso", variable=self.var_suelo, value="Arcilloso").pack(side=LEFT,
                                                                                                         padx=10)

        # --- HUMEDAD ---
        header_humedad = ttk.Frame(marco_formulario)
        header_humedad.pack(fill=X, pady=(5, 0))
        ttk.Label(header_humedad, text="Humedad Inicial (%):", font=("Helvetica", 10, "bold")).pack(side=LEFT)
        self.lbl_valor_humedad = ttk.Label(header_humedad, text="0 %", font=("Helvetica", 10, "bold"), bootstyle="info")
        self.lbl_valor_humedad.pack(side=RIGHT)

        self.slider_humedad = ttk.Scale(
            marco_formulario,
            from_=0,
            to=100,
            variable=self.var_humedad,
            command=self._actualizar_etiqueta_humedad,
            bootstyle="info"
        )
        self.slider_humedad.pack(fill=X, pady=(5, 15))

        # --- RIEGO AUTO ---
        ttk.Separator(marco_formulario).pack(fill=X, pady=5)
        ttk.Checkbutton(
            marco_formulario,
            text="Sistema de Riego Automático Activo",
            variable=self.var_riego,
            onvalue=True,
            offvalue=False,
            bootstyle="round-toggle"
        ).pack(fill=X, pady=15)

        # --- BOTONES DE ACCIÓN (Reorganizados) ---
        marco_botones = ttk.Frame(marco_formulario)
        marco_botones.pack(fill=X, pady=10)
        marco_botones.columnconfigure(0, weight=1)
        marco_botones.columnconfigure(1, weight=1)

        # Botón Guardar
        self.btn_guardar = ttk.Button(marco_botones, text="Guardar", bootstyle="success", command=self._accion_guardar)
        self.btn_guardar.grid(row=0, column=0, sticky="ew", padx=2, pady=2)

        # Botón Actualizar
        self.btn_actualizar = ttk.Button(marco_botones, text="Actualizar", bootstyle="info",
                                         command=self._accion_actualizar)
        self.btn_actualizar.grid(row=0, column=1, sticky="ew", padx=2, pady=2)

        # Botón Limpiar (Este no necesita restricción, así que puede quedarse igual o asignarse también)
        self.btn_limpiar = ttk.Button(marco_botones, text="Limpiar", bootstyle="secondary",
                                      command=self._accion_limpiar)
        self.btn_limpiar.grid(row=1, column=0, sticky="ew", padx=2, pady=2)

        # Botón Eliminar
        self.btn_eliminar = ttk.Button(marco_botones, text="Eliminar", bootstyle="danger",
                                       command=self._accion_eliminar)
        self.btn_eliminar.grid(row=1, column=1, sticky="ew", padx=2, pady=2)

        if self.rol_usuario != "admin":
            self.btn_guardar.configure(state="disabled")
            self.btn_actualizar.configure(state="disabled")
            self.btn_eliminar.configure(state="disabled")

        # --- BOTÓN VOLVER (Abajo a la Izquierda) ---
        ttk.Frame(marco_formulario).pack(expand=True)

        ttk.Button(
            marco_formulario,
            text="⬅ Volver al Menú Principal",
            bootstyle="secondary-outline",
            command=self._al_cerrar_ventana,
            width=25
        ).pack(side=BOTTOM, anchor=W, pady=10)

        # === PANEL DERECHO: TABLA ===
        marco_tabla = ttk.Labelframe(self.ventana, text="Listado de Parcelas", padding=10, bootstyle="default")
        marco_tabla.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)

        columnas = ("id", "nombre", "cultivo", "area", "humedad", "suelo", "riego")
        self.tabla = ttk.Treeview(
            marco_tabla,
            columns=columnas,
            show="headings",
            bootstyle="success"
        )

        # --- CONFIGURACIÓN OPTIMIZADA DE COLUMNAS ---
        # 1. Encabezados centrados para que se vean alineados
        self.tabla.heading("id", text="ID", anchor=CENTER)
        self.tabla.heading("nombre", text="Nombre Parcela", anchor=W)  # Nombre a la izquierda
        self.tabla.heading("cultivo", text="Cultivo", anchor=CENTER)
        self.tabla.heading("area", text="Área (m²)", anchor=CENTER)
        self.tabla.heading("humedad", text="Humedad %", anchor=CENTER)
        self.tabla.heading("suelo", text="Suelo", anchor=CENTER)
        self.tabla.heading("riego", text="Riego Auto", anchor=CENTER)

        # 2. Anchos definidos y alineación de datos
        # stretch=False en ID hace que no ocupe espacio innecesario
        self.tabla.column("id", width=40, minwidth=40, anchor=CENTER, stretch=False)
        self.tabla.column("nombre", width=180, minwidth=100, anchor=W)
        self.tabla.column("cultivo", width=100, minwidth=80, anchor=CENTER)
        self.tabla.column("area", width=80, minwidth=60, anchor=CENTER)
        self.tabla.column("humedad", width=80, minwidth=60, anchor=CENTER)
        self.tabla.column("suelo", width=100, minwidth=80, anchor=CENTER)
        self.tabla.column("riego", width=100, minwidth=80, anchor=CENTER)

        scrollbar = ttk.Scrollbar(marco_tabla, orient=VERTICAL, command=self.tabla.yview)
        self.tabla.configure(yscroll=scrollbar.set)

        scrollbar.pack(side=RIGHT, fill=Y)
        self.tabla.pack(fill=BOTH, expand=True)

        self.tabla.bind("<<TreeviewSelect>>", self._al_seleccionar_fila)
        self.tabla.bind("<Button-1>", self._al_clic_fondo)

    def _actualizar_etiqueta_humedad(self, _):
        val = int(self.slider_humedad.get())
        self.lbl_valor_humedad.config(text=f"{val} %")

    def _cargar_datos_tabla(self):
        datos = self.gestor.cargar_parcelas()
        for item in self.tabla.get_children():
            self.tabla.delete(item)
        if datos is not None:
            for _, fila in datos.iterrows():
                self.tabla.insert("", "end",
                                  values=(fila['id'], fila['nombre'], fila['cultivo'], fila['area'], fila['humedad'],
                                          fila['suelo'], fila['riego_auto']))
        else:
            messagebox.showwarning("Alerta", "No se pudo acceder al archivo de datos.")

    def _accion_guardar(self):
        nombre = self.var_nombre.get()
        area = self.var_area.get()

        if not nombre or not area:
            messagebox.showerror("Error", "Nombre y Área son obligatorios.")
            return
        try:
            float(area)
        except ValueError:
            messagebox.showerror("Error", "El área debe ser numérica.")
            return

        datos_nuevos = {
            "nombre": nombre,
            "cultivo": self.var_cultivo.get(),
            "area": area,
            "humedad": self.var_humedad.get(),
            "suelo": self.var_suelo.get(),
            "riego_auto": "Activo" if self.var_riego.get() else "Inactivo"
        }

        if self.gestor.guardar_parcela(datos_nuevos):
            messagebox.showinfo("Éxito", "Registro guardado.")
            self._accion_limpiar()
            self._cargar_datos_tabla()
        else:
            messagebox.showerror("Error", "Fallo al escribir en el archivo.")

    def _accion_actualizar(self):
        if not self.id_seleccionado:
            messagebox.showwarning("Atención", "Seleccione una parcela para editar.")
            return

        datos_editados = {
            "nombre": self.var_nombre.get(),
            "cultivo": self.var_cultivo.get(),
            "area": self.var_area.get(),
            "humedad": self.var_humedad.get(),
            "suelo": self.var_suelo.get(),
            "riego_auto": "Activo" if self.var_riego.get() else "Inactivo"
        }

        if self.gestor.actualizar_parcela(self.id_seleccionado, datos_editados):
            messagebox.showinfo("Éxito", "Información actualizada.")
            self._accion_limpiar()
            self._cargar_datos_tabla()
        else:
            messagebox.showerror("Error", "No se pudo actualizar el registro.")

    def _accion_eliminar(self):
        if not self.id_seleccionado:
            messagebox.showwarning("Atención", "Seleccione una parcela para eliminar.")
            return

        if messagebox.askyesno("Confirmar", f"¿Eliminar parcela ID {self.id_seleccionado}?"):
            if self.gestor.eliminar_parcela(self.id_seleccionado):
                messagebox.showinfo("Éxito", "Parcela eliminada.")
                self._accion_limpiar()
                self._cargar_datos_tabla()
            else:
                messagebox.showerror("Error", "Fallo al eliminar.")

    def _accion_limpiar(self):
        self.var_nombre.set("")
        self.var_area.set("")
        self.var_riego.set(False)
        self.var_suelo.set("Franco")
        self.var_humedad.set(0)
        self.lbl_valor_humedad.config(text="0 %")
        self.id_seleccionado = None
        if self.tabla.selection():
            self.tabla.selection_remove(self.tabla.selection())

    def _al_seleccionar_fila(self, _):
        seleccion = self.tabla.selection()
        if seleccion:
            datos_fila = self.tabla.item(seleccion[0])['values']
            self.id_seleccionado = datos_fila[0]
            self.var_nombre.set(datos_fila[1])
            self.var_cultivo.set(datos_fila[2])
            self.var_area.set(datos_fila[3])

            # Cargar humedad
            try:
                humedad_valor = int(float(datos_fila[4]))
            except ValueError:
                humedad_valor = 0

            self.var_humedad.set(humedad_valor)
            self.lbl_valor_humedad.config(text=f"{humedad_valor} %")

            self.var_suelo.set(datos_fila[5])
            self.var_riego.set(True if datos_fila[6] == "Activo" else False)

    def _al_clic_fondo(self, event):
        region = self.tabla.identify_region(event.x, event.y)
        if region == "nothing":
            self._accion_limpiar()

    def _al_cerrar_ventana(self):
        self.ventana.destroy()
        self.padre.deiconify()