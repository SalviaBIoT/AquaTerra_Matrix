"""Pruebas de humo de la interfaz (DT-04 y DT-05a).

Instancian la ventana real sobre una base temporal y recorren todas las
pantallas sin intervención humana. Se marcan ``gui`` para poder excluirlas en
servidores sin pantalla: ``pytest -m "not gui"``.
"""

from __future__ import annotations

import gc
import weakref
from datetime import date

import pytest

from aquaterra.application.contenedor import construir_contenedor
from aquaterra.config import Configuracion

pytestmark = pytest.mark.gui


@pytest.fixture
def app(tmp_path):
    tk = pytest.importorskip("tkinter")
    try:
        tk.Tk().destroy()
    except tk.TclError:
        pytest.skip("Sin entorno gráfico disponible")

    from aquaterra.ui.app import AplicacionMatrix

    contenedor = construir_contenedor(Configuracion(ruta_db=tmp_path / "ui.db"))
    aplicacion = AplicacionMatrix(contenedor)
    yield aplicacion
    if aplicacion.raiz.winfo_exists():
        aplicacion.salir()
    contenedor.cerrar()


def _iniciar(app, usuario="admin", clave="1234"):
    vista = app._vista
    vista.entrada_usuario.insert(0, usuario)
    vista.entrada_clave.insert(0, clave)
    vista._ingresar()
    app.raiz.update_idletasks()


def test_flujo_completo_una_sola_raiz(app):
    from aquaterra.ui.views.dashboard_view import VistaDashboard
    from aquaterra.ui.views.login_view import VistaLogin

    assert isinstance(app._vista, VistaLogin)
    _iniciar(app)
    assert isinstance(app._vista, VistaDashboard)
    for mostrar in (
        app.mostrar_parcelas,
        app.mostrar_riego,
        app.mostrar_monitor,
        app.mostrar_copiloto,
        app.mostrar_hardware,
        app.mostrar_configuracion,
        app.mostrar_dashboard,
    ):
        mostrar()
        app.raiz.update()
    # Regresión DT-05a: cerrar sesión vuelve al login en la MISMA raíz (antes mataba el proceso).
    app.cerrar_sesion()
    assert isinstance(app._vista, VistaLogin)
    assert app.raiz.winfo_exists()


def test_regresion_dt04_monitor_no_fuga_figuras(app):
    import matplotlib._pylab_helpers as helpers

    _iniciar(app)
    referencias = []
    for _ in range(15):
        app.mostrar_monitor()
        app.raiz.update()
        referencias += [weakref.ref(l.figure) for l in app._vista._lienzos]
        app.mostrar_dashboard()
        app.raiz.update()
    gc.collect()
    assert helpers.Gcf.get_num_fig_managers() == 0           # nada registrado en pyplot
    vivas = sum(1 for r in referencias if r() is not None)
    assert vivas == 0, f"{vivas} figuras siguen en memoria"


def test_riego_desde_la_vista(app):
    _iniciar(app)
    app.mostrar_riego()
    vista = app._vista
    vista.calendario.entry.delete(0, "end")
    vista.calendario.entry.insert(0, date(2026, 11, 13).isoformat())
    assert vista.calendario.get_date().date() == date(2026, 11, 13)
