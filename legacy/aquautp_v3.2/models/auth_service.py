import json
import os


class ServicioAutenticacion:
    def __init__(self):
        # Calculamos la ruta relativa para que funcione en cualquier equipo
        carpeta_actual = os.path.dirname(os.path.abspath(__file__))
        raiz_proyecto = os.path.dirname(carpeta_actual)

        # Ruta al archivo JSON de usuarios
        self.ruta_usuarios = os.path.join(raiz_proyecto, 'data', 'usuarios.json')

    def iniciar_sesion(self, usuario, clave):
        try:
            # Abrimos el archivo en modo lectura ('r') con soporte para tildes (utf-8)
            with open(self.ruta_usuarios, 'r', encoding='utf-8') as archivo:
                usuarios_registrados = json.load(archivo)  # Convierte JSON a lista de diccionarios

            # Buscamos si las credenciales coinciden recorriendo la lista
            for registro in usuarios_registrados:
                # Comparamos usuario y contraseña
                # Nota: 'usuario' y 'pass' son las claves exactas dentro del archivo JSON
                if registro['usuario'] == usuario and registro['pass'] == clave:
                    return registro  # Credenciales correctas, devolvemos los datos del usuario

            return None  # Si termina el bucle sin éxito, las credenciales son incorrectas

        except FileNotFoundError:
            print("ERROR: NO SE ENCUENTRA EL ARCHIVO DE USUARIOS")
            return None
        except Exception as e:
            print(f"ERROR FALLO INESPERADO EN AUTENTICACIÓN: {e}")
            return None