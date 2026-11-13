import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import messagebox
from ttkbootstrap.widgets import DateEntry
from models.data_manager import GestorDatos


class VentanaRiego:
    def __init__(self, ventana_padre, rol_usuario):
        self.padre = ventana_padre
        self.rol_usuario = rol_usuario

        self.ventana = ttk.Toplevel(ventana_padre)
        self.ventana.title("Programación de Riego - AquaUTP")
        self.ventana.geometry("950x480")
        self.ventana.resizable(False, False)

        self.ventana.protocol("WM_DELETE_WINDOW", self._al_cerrar_ventana)

        self.gestor = GestorDatos()

        # Variables de control
        self.var_humedad = ttk.IntVar(value=45)
        self.var_parcela_seleccionada = ttk.StringVar()
        self.var_litros = ttk.IntVar(value=50)
        self.mapa_parcelas = {}

        self._configurar_interfaz()
        self._cargar_parcelas_en_combo()

    def _configurar_interfaz(self):
        # Layout principal
        self.ventana.columnconfigure(0, weight=1)
        self.ventana.columnconfigure(1, weight=1)
        # Importante: Le damos peso a la fila 0 para que ocupe el espacio,
        # pero no demasiado para no dejar huecos gigantes abajo.
        self.ventana.rowconfigure(0, weight=1)

        # === LADO IZQUIERDO: CONFIGURACIÓN ===
        marco_izq = ttk.Frame(self.ventana, padding=20)
        marco_izq.grid(row=0, column=0, sticky="nsew")

        ttk.Label(marco_izq, text="Seleccione Parcela (Riego Activo):", font=("Helvetica", 11, "bold")).pack(fill=X,
                                                                                                             anchor=W)

        self.combo_parcelas = ttk.Combobox(
            marco_izq,
            textvariable=self.var_parcela_seleccionada,
            state="readonly",
            font=("Helvetica", 10)
        )
        self.combo_parcelas.pack(fill=X, pady=(5, 20))
        self.combo_parcelas.bind("<<ComboboxSelected>>", self._al_seleccionar_parcela)

        # Sección Umbral
        lbl_frame_slider = ttk.Labelframe(marco_izq, text="Condición de Disparo", padding=20, bootstyle="info")
        lbl_frame_slider.pack(fill=X, expand=True, anchor=N)

        ttk.Label(lbl_frame_slider, text="Activar si humedad es menor a:", bootstyle="secondary").pack()

        self.etiqueta_valor = ttk.Label(
            lbl_frame_slider,
            text="45 %",
            font=("Helvetica", 40, "bold"),
            bootstyle="info"
        )
        self.etiqueta_valor.pack(pady=10)

        self.slider = ttk.Scale(
            lbl_frame_slider,
            from_=0,
            to=100,
            variable=self.var_humedad,
            command=self._actualizar_etiqueta,
            bootstyle="info"
        )
        self.slider.pack(fill=X, pady=10)

        frame_rango = ttk.Frame(lbl_frame_slider)
        frame_rango.pack(fill=X)
        ttk.Label(frame_rango, text="0%").pack(side=LEFT)
        ttk.Label(frame_rango, text="100%").pack(side=RIGHT)

        # BOTÓN VOLVER (Ahora a la izquierda, abajo del todo)
        # Usamos un frame spacer para empujarlo al fondo del panel izquierdo
        ttk.Frame(marco_izq).pack(expand=True)

        ttk.Button(
            marco_izq,
            text="⬅ Volver al Menú Principal",
            bootstyle="secondary-outline",
            width=25,
            command=self._al_cerrar_ventana
        ).pack(side=BOTTOM, anchor=W, pady=10)

        # === LADO DERECHO: EJECUCIÓN ===
        marco_der = ttk.Frame(self.ventana, padding=20)
        marco_der.grid(row=0, column=1, sticky="nsew")

        # Tarjeta de Info
        self.lbl_info_parcela = ttk.Label(
            marco_der,
            text="Seleccione una parcela...",
            font=("Arial", 11),
            wraplength=350,
            justify=LEFT,
            bootstyle="inverse-secondary",
            padding=15
        )
        self.lbl_info_parcela.pack(fill=X, pady=(0, 20))

        # Formulario
        grp_programacion = ttk.Labelframe(marco_der, text="Parámetros de Riego", padding=15)
        grp_programacion.pack(fill=X)

        ttk.Label(grp_programacion, text="Fecha:", font=("Helvetica", 10)).pack(anchor=W)
        self.calendario = DateEntry(grp_programacion, bootstyle="success", startdate=None)
        self.calendario.pack(fill=X, pady=(5, 10))

        ttk.Label(grp_programacion, text="Hora (HH:MM):", font=("Helvetica", 10)).pack(anchor=W)
        self.entrada_hora = ttk.Entry(grp_programacion)
        self.entrada_hora.insert(0, "06:00")
        self.entrada_hora.pack(fill=X, pady=(5, 10))

        ttk.Label(grp_programacion, text="Cantidad de Agua (Litros):", font=("Helvetica", 10, "bold")).pack(anchor=W)
        self.spin_litros = ttk.Spinbox(
            grp_programacion,
            from_=1,
            to=5000,
            textvariable=self.var_litros,
            bootstyle="success"
        )
        self.spin_litros.pack(fill=X, pady=(5, 5))

        # Botón Grande de Acción
        self.btn_aplicar = ttk.Button(
            marco_der,
            text="APLICAR RIEGO AHORA",
            bootstyle="success",
            command=self._accion_ejecutar_riego_individual
        )
        self.btn_aplicar.pack(fill=X, pady=20)

        if self.rol_usuario != "admin":
            self.btn_aplicar.configure(state="disabled")

            # Mensaje visual opcional
            ttk.Label(
                marco_der,
                text="Solo administradores pueden ejecutar riegos.",
                bootstyle="warning",
                font=("Arial", 9)
            ).pack(fill=X)

    def _cargar_parcelas_en_combo(self):
        datos = self.gestor.cargar_parcelas()
        nombres_aptos = []
        self.mapa_parcelas = {}

        if datos is not None:
            for _, fila in datos.iterrows():
                if str(fila['riego_auto']) == "Activo":
                    nombre = fila['nombre']
                    nombres_aptos.append(nombre)
                    self.mapa_parcelas[nombre] = fila

            self.combo_parcelas['values'] = nombres_aptos

            if nombres_aptos:
                self.combo_parcelas.current(0)
                self._al_seleccionar_parcela(None)
            else:
                self.combo_parcelas.set("Sin parcelas activas")
                self.slider.configure(state="disabled")

    def _al_seleccionar_parcela(self, _):
        nombre = self.var_parcela_seleccionada.get()
        if nombre in self.mapa_parcelas:
            datos = self.mapa_parcelas[nombre]
            hum = int(float(datos['humedad']))

            info = (f"PARCELA: {datos['nombre']}\n"
                    f"Cultivo: {datos['cultivo']}\n"
                    f"Humedad Actual: {hum}%")

            self.lbl_info_parcela.config(text=info, bootstyle="inverse-info")

    def _actualizar_etiqueta(self, _):
        valor = int(self.slider.get())
        self.etiqueta_valor.config(text=f"{valor} %")

    def _accion_ejecutar_riego_individual(self):
        nombre = self.var_parcela_seleccionada.get()

        if nombre not in self.mapa_parcelas:
            messagebox.showwarning("Atención", "Seleccione una parcela válida.")
            return

        df_fresco = self.gestor.cargar_parcelas()
        filtro = df_fresco['nombre'] == nombre
        if filtro.any():
            fila_actual = df_fresco[filtro].iloc[0]

            id_parcela = int(fila_actual['id'])
            humedad_actual = int(float(fila_actual['humedad']))
            umbral = self.var_humedad.get()
            litros_agua = self.var_litros.get()

            if humedad_actual < umbral:
                nuevos_datos = fila_actual.to_dict()
                nuevos_datos['humedad'] = 95

                if self.gestor.actualizar_parcela(id_parcela, nuevos_datos):

                    evento_riego = {
                        "id_parcela": id_parcela,
                        "nombre_parcela": nombre,
                        "fecha": self.calendario.entry.get(),
                        "hora": self.entrada_hora.get(),
                        "humedad_inicial": humedad_actual,
                        "humedad_final": 95,
                        "agua_litros": litros_agua
                    }
                    self.gestor.registrar_riego(evento_riego)

                    messagebox.showinfo("Riego Aplicado",
                                        f"La parcela '{nombre}' ha sido regada.\n"
                                        f" Consumo: {litros_agua} Litros\n"
                                        f" Humedad subió a 95%.")

                    self.mapa_parcelas[nombre]['humedad'] = 95
                    self._al_seleccionar_parcela(None)
                else:
                    messagebox.showerror("Error", "No se pudo actualizar la base de datos.")
            else:
                messagebox.showinfo("Información",
                                    f"La parcela tiene {humedad_actual}% de humedad.\nEstá por encima del umbral ({umbral}%). No se requiere riego.")
        else:
            messagebox.showerror("Error", "No se encontró la parcela en la base de datos.")

    def _al_cerrar_ventana(self):
        self.ventana.destroy()
        self.padre.deiconify()