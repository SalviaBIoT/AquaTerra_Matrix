import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import messagebox, Canvas
from PIL import Image, ImageTk
from models.auth_service import ServicioAutenticacion
import os

class VentanaLogin:
    def __init__(self):
        # Configuración inicial de la ventana con tema oscuro
        self.ventana = ttk.Window(themename="superhero")
        self.ventana.title("Acceso AquaUTP")
        self.ventana.geometry("800x600")
        self.ventana.resizable(False, False)

        # Instancia del servicio de seguridad para validar credenciales
        self.servicio_auth = ServicioAutenticacion()

        # Variable para almacenar los datos del usuario si el login es exitoso
        self.usuario_autenticado = None

        self._configurar_interfaz()

    def _configurar_interfaz(self):
        """Diseño y disposición de los elementos visuales del login."""

        # Contenedor principal con márgenes para centrar el contenido
        carpeta_actual = os.path.dirname(os.path.abspath(__file__))
        raiz_proyecto = os.path.dirname(carpeta_actual)
        ruta_imagen = os.path.join(raiz_proyecto, 'assets', 'paisajeriego.png')

        # Cargar y redimensionar imagen para que llene la ventana (800x600)
        try:
            imagen_original = Image.open(ruta_imagen)
            imagen_redimensionada = imagen_original.resize((800, 600), Image.Resampling.LANCZOS)
            self.imagen_fondo = ImageTk.PhotoImage(imagen_redimensionada)  # Guardamos referencia en self
        except Exception as e:
            print(f"Error cargando imagen: {e}")
            self.imagen_fondo = None

        # 2. CREAR EL LIENZO (CANVAS)
        # El Canvas ocupa toda la ventana y será nuestro fondo
        self.canvas = Canvas(self.ventana, width=800, height=600, highlightthickness=0)
        self.canvas.pack(fill=BOTH, expand=True)

        # 3. DIBUJAR EL FONDO
        if self.imagen_fondo:
            # Poner la imagen en la coordenada (0,0)
            self.canvas.create_image(0, 0, image=self.imagen_fondo, anchor="nw")
        else:
            # Si falla la imagen, ponemos un fondo azul oscuro por defecto
            self.canvas.configure(bg="#2b3e50")

        # 4. DIBUJAR ELEMENTOS SOBRE LA IMAGEN
        # Usamos coordenadas X, Y para posicionar todo centrado.
        # Centro de la pantalla: X=400

        # --- TÍTULO ---
        # create_text dibuja letras con fondo transparente real
        self.canvas.create_text(
            400, 50,  # Posición X, Y
            text="Sistema de Riego Automático - AquaUTP",
            font=("Helvetica", 26, "bold"),
            fill="white"  # Color de letra blanco para resaltar sobre el cielo
        )

        # --- CAJA DE LOGIN (SEMI-TRANSPARENTE SIMULADA) ---
        # Dibujamos un rectángulo oscuro detrás de los inputs para que se lean mejor
        # (x1, y1, x2, y2)
        self.canvas.create_rectangle(
            250, 180, 550, 480,
            fill="#1a1a1a",
            stipple="gray50",  # Esto simula transparencia (tramado de puntos)
            outline=""
        )

        # --- ETIQUETAS Y CAMPOS ---

        # Etiqueta Usuario
        self.canvas.create_text(400, 210, text="Usuario:", font=("Helvetica", 12), fill="white")

        # Input Usuario (Widget real incrustado en el canvas)
        self.entrada_usuario = ttk.Entry(self.canvas, font=("Helvetica", 12), width=25)
        self.canvas.create_window(400, 240, window=self.entrada_usuario)  # create_window pone el widget

        # Etiqueta Contraseña
        self.canvas.create_text(400, 290, text="Contraseña:", font=("Helvetica", 12), fill="white")

        # Input Contraseña
        self.entrada_clave = ttk.Entry(self.canvas, font=("Helvetica", 12), show="*", width=25)
        self.canvas.create_window(400, 320, window=self.entrada_clave)

        # --- BOTÓN INGRESAR ---
        boton_ingreso = ttk.Button(
            self.canvas,
            text="INICIAR SESIÓN",
            bootstyle="success",
            width=20,
            command=self._accion_iniciar_sesion
        )
        self.canvas.create_window(400, 400, window=boton_ingreso)

        # Footer
        self.canvas.create_text(400, 560, text="v3.2 - Sistema de Gestión Agrícola y Bio-IoT", font=("Arial", 10), fill="white")
        self.canvas.create_text(400, 580, text="Arquitectura y Desarrollo: Daniel Felipe Duque Lizarralde — Ecosistema TerraBit", font=("Arial", 10), fill="white")

    def _accion_iniciar_sesion(self):
        """Captura los datos, valida con el servicio y gestiona el acceso."""
        usuario = self.entrada_usuario.get()
        clave = self.entrada_clave.get()

        # Consultamos al servicio de autenticación si las credenciales son válidas
        datos_usuario = self.servicio_auth.iniciar_sesion(usuario, clave)

        if datos_usuario:
            # Si la autenticación es correcta, guardamos los datos del usuario
            self.usuario_autenticado = datos_usuario

            # Ocultamos la ventana actual y detenemos el bucle principal
            # Esto devuelve el control al archivo main.py para que abra el Dashboard
            self.ventana.withdraw()
            self.ventana.quit()

        else:
            # Si falla, mostramos una alerta al usuario
            messagebox.showerror("Error de Acceso", "Usuario o contraseña incorrectos.")

    def ejecutar(self):
        """Inicia el bucle principal de la interfaz gráfica."""
        self.ventana.mainloop()