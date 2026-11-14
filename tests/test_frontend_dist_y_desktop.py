"""Pruebas de integración del frontend compilado (``frontend/dist``) y lanzador v6.0."""

from __future__ import annotations

import urllib.request
from pathlib import Path

from fastapi.testclient import TestClient

from aquaterra import __version__
from aquaterra.api import crear_app
from aquaterra.application.contenedor import construir_contenedor
from aquaterra.config import Configuracion
from aquaterra.desktop import ServidorLocalEmbebido, buscar_puerto_libre, parsear_argumentos


def test_fastapi_sirve_frontend_dist_y_protege_rutas_api(tmp_path: Path) -> None:
    dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    assert (dist / "index.html").is_file(), "Debe existir frontend/dist/index.html compilado."

    cfg = Configuracion(ruta_db=tmp_path / "spa.db")
    contenedor = construir_contenedor(cfg)
    try:
        app = crear_app(contenedor, static_dir=dist)
        with TestClient(app) as client:
            r_root = client.get("/")
            assert r_root.status_code == 200
            assert "text/html" in r_root.headers.get("content-type", "")
            assert "AquaTerra Matrix" in r_root.text

            r_spa = client.get("/telemetria")
            assert r_spa.status_code == 200
            assert "AquaTerra Matrix" in r_spa.text

            r_api_404 = client.get("/api/no-existe-esta-ruta")
            assert r_api_404.status_code == 404
            assert r_api_404.json()["detail"] == "Ruta API no encontrada."

            r_health = client.get("/api/health")
            assert r_health.status_code == 200
            assert r_health.json() == {"status": "ok", "version": __version__}
    finally:
        contenedor.cerrar()


def test_servidor_embebido_arranca_y_cierra_por_http_real(tmp_path: Path) -> None:
    puerto = buscar_puerto_libre()
    cfg = Configuracion(ruta_db=tmp_path / "desktop_http.db")
    contenedor = construir_contenedor(cfg)
    srv = ServidorLocalEmbebido(contenedor, host="127.0.0.1", port=puerto)
    try:
        srv.iniciar(timeout_s=10.0)
        with urllib.request.urlopen(f"{srv.url_base}/api/health", timeout=2.0) as resp:
            assert resp.status == 200
            cuerpo = resp.read().decode("utf-8")
            assert '"status":"ok"' in cuerpo or '"status": "ok"' in cuerpo

        with urllib.request.urlopen(f"{srv.url_base}/", timeout=2.0) as resp_html:
            assert resp_html.status == 200
            html = resp_html.read().decode("utf-8")
            assert '<div id="root"></div>' in html
    finally:
        srv.detener()
        contenedor.cerrar()


def test_parseo_argumentos_lanzador_v6() -> None:
    args_default = parsear_argumentos([])
    assert not args_default.web
    assert not args_default.legacy_ui
    assert args_default.port == 0

    args_web = parsear_argumentos(["--web", "--no-browser", "--port", "9012"])
    assert args_web.web
    assert args_web.no_browser
    assert args_web.port == 9012

    args_legacy = parsear_argumentos(["--legacy-ui"])
    assert args_legacy.legacy_ui
