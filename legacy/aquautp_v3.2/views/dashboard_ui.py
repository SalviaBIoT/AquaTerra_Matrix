import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import messagebox
# Importamos las ventanas hijas para poder abrirlas desde aquí
from views.parcelas_ui import VentanaParcelas
from views.riegos_ui import VentanaRiego
from views.monitor_ui import VentanaMonitor


class VentanaDashboard:
    def __init__(self, datos_usuario):
        self.datos_usuario = datos_usuario # Guardamos todo (nombre, rol, id)
        self.nombre_usuario = datos_usuario['nombre']
        self.rol_usuario = datos_usuario['rol']

        # Usamos Toplevel porque esta ventana vive encima del Login (que está oculto)
        self.ventana = ttk.Toplevel()
        self.ventana.title("Panel de Control - AquaUTP")
        self.ventana.geometry("800x600")
        self.ventana.resizable(True, True)

        # Ejecutamos la construcción visual
        self._configurar_interfaz()

    def _configurar_interfaz(self):
        """Diseño de la cuadrícula principal y los botones de acceso."""

        # 1. ENCABEZADO
        marco_encabezado = ttk.Frame(self.ventana, padding=20)
        marco_encabezado.pack(fill=X)

        # Saludo al usuario
        ttk.Label(
            marco_encabezado,
            text=f"Bienvenido, {self.nombre_usuario}",
            font=("Helvetica", 16)
        ).pack(side=LEFT)

        # Botón de Salir
        ttk.Button(
            marco_encabezado,
            text="Cerrar Sesión",
            bootstyle="danger-outline",
            command=self._accion_cerrar_sesion
        ).pack(side=RIGHT)

        # Línea divisoria
        ttk.Separator(self.ventana).pack(fill=X, padx=20)

        # 2. MENÚ PRINCIPAL (Rejilla)
        marco_menu = ttk.Frame(self.ventana, padding=40)
        marco_menu.pack(expand=True, fill=BOTH)

        # Configuración de la cuadrícula (2x2)
        # Los 'weight=1' hacen que los botones se estiren si agrando la ventana
        marco_menu.columnconfigure(0, weight=1)
        marco_menu.columnconfigure(1, weight=1)
        marco_menu.rowconfigure(0, weight=1)
        marco_menu.rowconfigure(1, weight=1)

        # Botón 1: Parcelas
        btn_parcelas = ttk.Button(
            marco_menu,
            text="GESTIONAR PARCELAS",  # Texto limpio en mayúsculas
            bootstyle="primary",
            command=self._abrir_gestion_parcelas
        )
        # sticky="nsew" obliga al botón a llenar todo el cuadro disponible
        btn_parcelas.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # Botón 2: Riego
        btn_riego = ttk.Button(
            marco_menu,
            text="PROGRAMAR RIEGO",
            bootstyle="info",
            command=self._abrir_programacion_riego
        )
        btn_riego.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        # Botón 3: Monitor
        btn_monitor = ttk.Button(
            marco_menu,
            text="MONITOR Y GRÁFICOS",
            bootstyle="success",
            command=self._abrir_monitor
        )
        btn_monitor.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        # Botón 4: Salir del Sistema
        btn_salir = ttk.Button(
            marco_menu,
            text="SALIR DEL SISTEMA",
            bootstyle="danger",
            command=self.ventana.quit
        )
        btn_salir.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")

    def _abrir_gestion_parcelas(self):
        # LÓGICA DE NAVEGACIÓN:
        # 1. Ocultamos este Dashboard para limpiar la pantalla
        self.ventana.withdraw()

        # 2. Abrimos la ventana hija y le pasamos 'self.ventana' (este objeto Dashboard)
        # De esta forma, la hija podrá decir "padre.deiconify()" cuando la cierren.
        VentanaParcelas(self.ventana, self.rol_usuario)

    def _abrir_programacion_riego(self):
        self.ventana.withdraw()  # Ocultar dashboard
        VentanaRiego(self.ventana, self.rol_usuario)  # Abrir Riego

    def _abrir_monitor(self):
        self.ventana.withdraw()  # Ocultar dashboard
        VentanaMonitor(self.ventana)  # Abrir Gráficos

    def _accion_cerrar_sesion(self):
        # Destruimos esta ventana visualmente y cerramos la aplicación
        self.ventana.destroy()
        # Nota: Idealmente volveríamos al Login, pero por simplicidad cerramos.
        self.ventana.quit()

    def ejecutar(self):
        self.ventana.mainloop()