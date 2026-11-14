# Sprint 1 (Fase 0) — Saneamiento de Concurrencia SQLite Multi-Hilo y Entorno `v6.0`

- **Fecha:** `2026-11-14`
- **Estado:** Completado y Verificado
- **Archivos modificados / creados:**
  - `aquaterra/infrastructure/db/conexion.py`
  - `aquaterra/infrastructure/db/__init__.py`
  - `aquaterra/application/contenedor.py`
  - `tests/test_concurrencia_sqlite.py`

---

## 1. ¿Qué se hizo?

1. **Resolución del bug crítico de concurrencia multi-hilo en SQLite (`ProgrammingError`):**
   Se reemplazó la conexión SQLite directa de un solo hilo por una conexión endurecida con `check_same_thread=False` envuelta en el proxy thread-safe `ConexionSQLiteSegura`.
2. **Aprovisionamiento del Toolchain de Frontend (`v6.0`):**
   - Instalación de **Node.js LTS (`v26.13.1`)** con `npm` mediante `winget` (`OpenJS.NodeJS.LTS`) para compilación del nuevo frontend React/Vite/TypeScript.
   - Instalación en el entorno virtual Python (`.venv`) de **`fastapi`**, **`uvicorn[standard]`** y **`pywebview`** para servir la API local y la ventana nativa Edge WebView2.
3. **Suite de pruebas de estrés concurrente (`tests/test_concurrencia_sqlite.py`):**
   - Prueba `test_concurrencia_multihilo_narrar_y_notificar`: dispara simultáneamente desde múltiples hilos `copiloto.narrar_pulso_24h()`, `sincronizacion.notificar_pulso_24h_estacion()` y `radar.listar_radar_priorizado()`.
   - Prueba `test_concurrencia_multihilo_en_memoria_escrituras_simultaneas`: valida 8 hilos escribiendo en paralelo sobre una misma base `:memory:` sin colisiones transaccionales.

---

## 2. ¿De qué manera se implementó?

1. **`ConexionSQLiteSegura` en `aquaterra/infrastructure/db/conexion.py`:**
   - Se abre `sqlite3.connect(str(ruta), detect_types=0, check_same_thread=False)` manteniendo los PRAGMAs críticos (`foreign_keys = ON`, `journal_mode = WAL`, `synchronous = NORMAL`, `busy_timeout = 5000`).
   - Se implementó un proxy transparente con `__slots__ = ("_conn", "_lock", "_tx_depth")` protegido por un `threading.RLock()`.
   - El gestor de contexto (`__enter__` / `__exit__`) adquiere el `RLock` al iniciar una transacción (`with self._db:`) y lo libera al confirmar o revertir (`COMMIT`/`ROLLBACK`), controlando profundidad reentrante (`_tx_depth`) para evitar commits prematuros o colisiones `cannot start a transaction within a transaction`.
   - Métodos como `execute`, `executemany`, `executescript`, `cursor`, `commit`, `rollback` y `close` operan serializados bajo el mismo `RLock`, manteniendo compatibilidad total de firma con `sqlite3.Connection` sin modificar ni una línea del dominio (`aquaterra/core/`) ni de los repositorios.
2. **Integración en `Contenedor` (`aquaterra/application/contenedor.py`):**
   - Se actualizó el tipado de `Contenedor.conexion` a `sqlite3.Connection | ConexionSQLiteSegura` y se exportó `ConexionSQLiteSegura` desde `aquaterra.infrastructure.db`.

---

## 3. ¿Por qué era necesario?

- En `v5.0`, cuando la UI lanzaba tareas asíncronas en hilos secundarios (`AquaTerra-Narrar24h` o `AquaTerra-Notificar`) para no congelar la pantalla mientras consultaba Gemini u Ollama, SQLite lanzaba:
  `SQLite objects created in a thread can only be used in that same thread`.
- En la arquitectura `v6.0`, **FastAPI + Uvicorn** despacha los endpoints síncronos en un *threadpool* (`anyio`) con múltiples peticiones HTTP concurrentes (dashboard, telemetría, candados de riego y copiloto cargando al mismo tiempo). Sin una conexión thread-safe serializada transaccionalmente, la nueva API local colapsaría ante la primera ráfaga paralela del navegador o WebView.
- Usar un proxy con `RLock` sobre la misma conexión también garantiza compatibilidad tanto con bases WAL en disco como con bases `:memory:` en la suite de pruebas (`TestClient` de FastAPI).

---

## 4. ¿Cómo mejora esto la ruta del Frontend final (`v6.0`)?

1. **Desbloquea peticiones concurrentes reales desde React:** Cuando el navegador/WebView carga `DashboardPage` o `TelemetryPage` disparando 4 o 5 `fetch()` en paralelo (`radar`, `pulso`, `pronóstico`, `series`, `estado`), el servidor FastAPI responde en paralelo sin bloqueos ni caídas por cambio de hilo.
2. **Elimina congelamientos durante llamadas lentas de IA / Red:** Las operaciones pesadas (`narrar_pulso_24h`, `consultar_copiloto`, `sincronizar_todo_hibrido`) ahora conviven limpiamente con lecturas rápidas del dashboard sin errores de concurrencia.
3. **Deja listo el puente de compilación y empaquetado:** Con Node.js LTS (`v26.13.1`), FastAPI, Uvicorn y PyWebView instalados, el repositorio queda listo para levantar la capa API (Sprint 2) y compilar la interfaz web moderna sin depender de Tkinter.
