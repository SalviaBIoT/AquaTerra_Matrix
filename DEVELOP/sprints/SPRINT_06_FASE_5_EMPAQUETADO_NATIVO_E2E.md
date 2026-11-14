# Sprint 6 (Fase 5) — Empaquetado Nativo PyWebView, Modo `--web`, Pruebas E2E y Lanzamiento `v6.0.0`

**Fecha de ejecución:** 2026-11-14  
**Estado:** Completado y verificado  
**Archivos creados/actualizados:**
- `aquaterra/desktop.py`
- `aquaterra/__main__.py`
- `aquaterra/__init__.py` (`__version__ = "6.0.0"`)
- `pyproject.toml`
- `requirements.txt`
- `.gitignore` (`frontend/node_modules/`, `frontend/.vite/`, `frontend/*.tsbuildinfo`)
- `tests/test_frontend_dist_y_desktop.py`

---

## 1. Qué se hizo
1. **Lanzador Unificado Nativo & Web (`aquaterra/desktop.py` + `aquaterra/__main__.py`):**
   - Implementación de `ServidorLocalEmbebido` que levanta Uvicorn sobre `127.0.0.1` en un hilo `daemon` sirviendo conjuntamente `/api/*` y el bundle estático `frontend/dist`.
   - Modo predeterminado nativo con **`pywebview`** (WebView2 en Windows, `width=1380`, `height=860`, fondo `#0A0E0C`) y cierre ordenado de servidor y base SQLite WAL al cerrar la ventana.
   - Bandera **`--web`**: inicia el servidor local en puerto configurable (`8765` por defecto) y abre el navegador predeterminado.
   - Bandera **`--legacy-ui`**: conserva respaldo completo hacia la interfaz clásica `ttkbootstrap` (`aquaterra-legacy`).
2. **Versionado y Dependencias (`aquaterra/__init__.py`, `pyproject.toml`, `requirements.txt`):**
   - Actualización del proyecto a **`v6.0.0`**, agregando `fastapi`, `uvicorn[standard]` y `pywebview` como dependencias de runtime y registrando los scripts `aquaterra = "aquaterra.desktop:ejecutar"` y `aquaterra-legacy = "aquaterra.ui.app:ejecutar"`.
3. **Higiene Git y Pruebas End-to-End de Distribución (`tests/test_frontend_dist_y_desktop.py`):**
   - Protección en `.gitignore` para no versionar `frontend/node_modules/`, cachés de Vite ni `.tsbuildinfo`.
   - Verificación automatizada de:
     - Servicio de `frontend/dist/index.html` y *SPA fallback* desde FastAPI sin interferir con rutas `/api/*`.
     - Arranque real por TCP/HTTP en puerto efímero de `ServidorLocalEmbebido`, verificación de `/api/health` (`v6.0.0`) y HTML raíz.
     - Parseo de flags CLI (`--web`, `--no-browser`, `--port`, `--legacy-ui`).

---

## 2. De qué manera se implementó
- Para evitar colisiones si el usuario abre más de una instancia o tiene otro servicio en `8765`, el modo nativo utiliza `buscar_puerto_libre()` (`bind(("127.0.0.1", 0))`) y realiza polling acotado sobre `/api/health` mediante `esperar_api_lista()` antes de abrir la ventana PyWebView o el navegador.
- El punto de entrada `python -m aquaterra` ahora delega directamente en `aquaterra.desktop:ejecutar`, manteniendo la experiencia de aplicación de escritorio de un solo comando.
- En `pyproject.toml` se añadió `extend-exclude = ["legacy", "frontend"]` en Ruff para que `ruff check .` audite exclusivamente el código vivo sin fallar sobre scripts históricos congelados.

---

## 3. Por qué era necesario
- Sin el servidor embebido + empaquetado `pywebview`, el usuario tendría que lanzar dos terminales (`uvicorn` y `vite`) manualmente cada vez que operara en campo.
- Con `frontend/dist` servido desde `aquaterra/api/app.py`, todo el ecosistema funciona con un único comando (`python -m aquaterra` o `aquaterra`) completamente **offline**, con persistencia local SQLite WAL y sin CORS ni puertos expuestos fuera de `127.0.0.1`.

---

## 4. Cómo mejora la ruta del frontend final
1. **Despliegue de producción en 1 comando:** `python -m aquaterra` abre una ventana nativa Edge WebView2 limpia, rápida y con renderizado Chromium moderno para ECharts 6, Tailwind v4, `:user-invalid` y `<dialog>`.
2. **Flexibilidad total de uso:** Operación nativa (`aquaterra`), en navegador externo (`aquaterra --web`), desarrollo HMR (`uvicorn` + `npm run dev` en `:5173`) o fallback histórico (`aquaterra --legacy-ui`) conviven sin romper compatibilidad ni pruebas existentes.
