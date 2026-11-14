"""Pruebas del despliegue Frontend v5.0 (App Shell, Tema Dual, Modo Híbrido y Conectores)."""

from __future__ import annotations

import urllib.error

import pytest

from aquaterra.application.contenedor import construir_contenedor
from aquaterra.config import Configuracion, cargar_env_local
from aquaterra.core.domain import ErrorPermiso, Rol, TipoEstacion
from aquaterra.ui.tema import TEMA_CLARO, TEMA_OSCURO


def test_hibrido_offline_degrada_sin_excepciones(tmp_path) -> None:
    """En campo sin internet, `sincronizar_todo_hibrido` reporta online=False sin romper la app."""
    c = construir_contenedor(Configuracion(ruta_db=tmp_path / "hibrido.db"))
    try:
        c.sincronizacion.asegurar_estaciones_terrabit_base()

        class _ClimaOffline:
            def descargar_pronostico_estacion(self, _est, *, dias=2):
                raise urllib.error.URLError("Sin conexión a Internet en campo")

        c.sincronizacion.clima = _ClimaOffline()  # type: ignore[assignment]
        res = c.sincronizacion.sincronizar_todo_hibrido(dias_clima=1)
        assert res.online is False
        assert res.aviso is not None
        assert "Open-Meteo offline" in res.aviso
    finally:
        c.cerrar()


def test_reconfigurar_conectores_y_env_local(tmp_path, monkeypatch) -> None:
    c = construir_contenedor(Configuracion(ruta_db=tmp_path / "cfg.db"))
    try:
        admin = c.auth.iniciar_sesion("admin", "1234")
        ruta_env = tmp_path / ".env"

        resumen = c.sincronizacion.reconfigurar_conectores(
            admin,
            ubidots_token="TOKEN_TEST_LOCAL",
            ia_proveedor="local_reglas",
            ia_ollama_url="http://192.168.1.99:11434",
            ia_ollama_modelo="qwen2.5:0.5b",
            webhook_n8n_url="https://n8n.local/webhook/terrabit",
            telegram_bot_token="123:ABC",
            telegram_chat_id="-100999",
            guardar_en_env_local=True,
            ruta_env=ruta_env,
        )
        assert resumen["ubidots_configurado"] is True
        assert resumen["ia_proveedor"] == "local_reglas"
        assert resumen["ia_ollama_modelo"] == "qwen2.5:0.5b"
        assert set(resumen["canales_notificacion"]) == {"n8n_webhook", "telegram"}
        assert ruta_env.exists()

        # Verificar que cargar_env_local lee las claves en un entorno limpio
        for k in ("UBIDOTS_TOKEN", "AQUATERRA_IA_PROVEEDOR", "AQUATERRA_OLLAMA_MODEL"):
            monkeypatch.delenv(k, raising=False)
        cargadas = cargar_env_local(ruta_env)
        assert cargadas >= 3
        import os

        assert os.environ["AQUATERRA_OLLAMA_MODEL"] == "qwen2.5:0.5b"
    finally:
        c.cerrar()


def test_admin_usuarios_y_registro_estacion(tmp_path) -> None:
    c = construir_contenedor(Configuracion(ruta_db=tmp_path / "users.db"))
    try:
        admin = c.auth.iniciar_sesion("admin", "1234")
        oper = c.auth.crear_usuario(
            admin,
            usuario="investigador_utp",
            nombre="Semillero Kilby",
            clave="clave_segura",
            rol=Rol.OPERADOR,
        )
        assert oper.rol is Rol.OPERADOR
        autenticado = c.auth.iniciar_sesion("investigador_utp", "clave_segura")
        assert autenticado.id == oper.id

        with pytest.raises(ErrorPermiso):
            c.sincronizacion.registrar_estacion(
                oper,
                codigo="sigatoka-01",
                nombre="Sigatoka Prueba",
                tipo=TipoEstacion.SIGATOKA,
            )

        est = c.sincronizacion.registrar_estacion(
            admin,
            codigo="sigatoka-01",
            nombre="Sigatoka Prueba",
            tipo=TipoEstacion.SIGATOKA,
        )
        assert est.codigo == "sigatoka-01"
        assert len(c.radar.listar_estaciones()) == 1
    finally:
        c.cerrar()


@pytest.mark.gui
def test_app_shell_v5_todas_las_vistas_y_tema_dual(tmp_path) -> None:
    tk = pytest.importorskip("tkinter")
    try:
        tk.Tk().destroy()
    except tk.TclError:
        pytest.skip("Sin entorno gráfico disponible")

    from aquaterra.ui.app import AplicacionMatrix
    from aquaterra.ui.views.config_view import VistaConfiguracion
    from aquaterra.ui.views.copiloto_view import VistaCopiloto
    from aquaterra.ui.views.hardware_view import VistaHardware

    c = construir_contenedor(Configuracion(ruta_db=tmp_path / "shell.db"))
    app = AplicacionMatrix(c)
    try:
        app._vista.entrada_usuario.insert(0, "admin")
        app._vista.entrada_clave.insert(0, "1234")
        app._vista._ingresar()
        app.raiz.update_idletasks()

        # Sembrar nodos base + ingerir trama nRF24L01+ desde VistaHardware
        c.sincronizacion.asegurar_estaciones_terrabit_base()
        app.notificar_cambio_datos("Base lista")

        for mostrar in (
            app.mostrar_dashboard,
            app.mostrar_monitor,
            app.mostrar_parcelas,
            app.mostrar_riego,
            app.mostrar_copiloto,
            app.mostrar_hardware,
            app.mostrar_configuracion,
        ):
            mostrar()
            app.raiz.update()

        assert isinstance(app._vista, VistaConfiguracion)
        app.mostrar_copiloto()
        assert isinstance(app._vista, VistaCopiloto)
        app.mostrar_hardware()
        assert isinstance(app._vista, VistaHardware)
        app._vista._ingerir_buffer_radio()
        assert c.sincronizacion.resumen_estado_conectividad()["lecturas_totales"] >= 2

        # Alternar Tema Dual (Oscuro <-> Claro) en vivo
        nuevo = app.alternar_tema()
        assert nuevo == TEMA_CLARO
        nuevo2 = app.alternar_tema()
        assert nuevo2 == TEMA_OSCURO
    finally:
        if app.raiz.winfo_exists():
            app.salir()
        c.cerrar()
