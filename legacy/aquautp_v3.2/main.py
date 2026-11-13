from views.login_ui import VentanaLogin
from views.dashboard_ui import VentanaDashboard


def iniciar_sistema():
    # 1. Iniciar la ventana de Login
    app_login = VentanaLogin()

    app_login.ejecutar()

    # PUNTO DE VERIFICACIÓN

    # 2. Verificar si hubo un inicio de sesión exitoso
    datos_usuario = app_login.usuario_autenticado

    if datos_usuario:
        print(f"[SISTEMA] Inicio de sesión exitoso. Usuario: {datos_usuario['nombre']}")

        # 3. Iniciar el Panel de Control (Dashboard)
        app_dashboard = VentanaDashboard(datos_usuario)

        app_dashboard.ejecutar()
    else:
        print("[SISTEMA] Aplicación cerrada por el usuario.")


if __name__ == "__main__":
    iniciar_sistema()