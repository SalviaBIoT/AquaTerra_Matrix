# Sprint 2 (Fase 1) — Capa API Local FastAPI (`aquaterra/api/`)

- **Fecha:** `2026-11-14`
- **Estado:** Completado y Verificado (`tests/test_api_v6.py` 2/2 en verde, `ruff` sin errores)
- **Archivos creados:**
  - `aquaterra/api/__init__.py`
  - `aquaterra/api/app.py`
  - `aquaterra/api/deps.py`
  - `aquaterra/api/schemas.py`
  - `aquaterra/api/routers/__init__.py`
  - `aquaterra/api/routers/auth.py`
  - `aquaterra/api/routers/estaciones.py`
  - `aquaterra/api/routers/parcelas.py`
  - `aquaterra/api/routers/riego.py`
  - `aquaterra/api/routers/copiloto.py`
  - `aquaterra/api/routers/hardware.py`
  - `aquaterra/api/routers/sistema.py`
  - `tests/test_api_v6.py`

---

## 1. ¿Qué se hizo?

Se construyó la capa de API HTTP local (`FastAPI`) desacoplada por dominios como puente 1:1 hacia `Contenedor`, manteniendo **cero lógica agronómica o de negocio** en los endpoints:

1. **Autenticación, Sesiones y Usuarios (`auth.py`):**
   - `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`
   - `GET /api/usuarios`, `POST /api/usuarios`, `POST /api/usuarios/{id}/clave`
2. **Radar, Estaciones, Pulso 24h y Telemetría (`estaciones.py`):**
   - `GET /api/radar` (filtrado + conteos KPI globales), `GET /api/estaciones`, `POST /api/estaciones`, `POST /api/estaciones/sembrar-base`
   - `GET /api/estaciones/{id}/pulso`, `GET /api/estaciones/{id}/series`, `GET /api/estaciones/{id}/ventana-movil`, `GET /api/estaciones/{id}/correlacion` (incluye pares alineados y extremos de recta OLS), `GET /api/estaciones/{id}/pronostico`, `GET /api/estaciones/{id}/eventos`, `POST /api/estaciones/{id}/reparar-rtc`, `POST /api/estaciones/{id}/narrar-24h`
3. **Parcelas & Comparativo (`parcelas.py`):**
   - `GET /api/parcelas`, `GET /api/parcelas/{id}`, `POST /api/parcelas`, `PATCH /api/parcelas/{id}` (actualización parcial con soporte de desvinculación), `DELETE /api/parcelas/{id}`, `GET /api/monitor/comparativo`
4. **Riego, 5 Candados, Bomba & Incidencia (`riego.py`):**
   - `GET /api/parcelas/{id}/riego/contexto`, `POST /api/parcelas/{id}/riego/aplicar`, `POST /api/parcelas/{id}/riego/programar`, `POST /api/riego/incidencia`
5. **Copiloto IA, Calibración Auditada & SFT (`copiloto.py`):**
   - `GET /api/copiloto/estado` (incluye historial de versiones `calibraciones_nodo` y catálogo de cotas), `POST /api/copiloto/consultar`, `POST /api/copiloto/aplicar`, `POST /api/copiloto/rollback`, `GET /api/copiloto/dataset.jsonl`
6. **Hardware `nRF24L01+` & MicroSD (`hardware.py`):**
   - `GET /api/hardware/puertos`, `POST /api/hardware/serial/leer`, `POST /api/hardware/tramas`, `POST /api/hardware/microsd/escanear`, `POST /api/hardware/microsd/importar`
7. **Sistema, Conectividad, Búsqueda `Ctrl+K` y Exportación (`sistema.py`):**
   - `GET /api/health`, `GET /api/sistema/estado` (sin exponer tokens secretos en claro), `POST /api/sistema/sync`, `POST /api/sistema/notificar-24h`, `POST /api/sistema/conectores`, `POST /api/sistema/ollama/precalentar`, `POST /api/sistema/worker`, `GET /api/sistema/buscar`, `GET /api/exportar/xlsx`, `GET /api/exportar/csv`

---

## 2. ¿De qué manera se implementó?

- **Fábrica `crear_app(contenedor=None, static_dir=None)` en `aquaterra/api/app.py`:**
  - En producción gestiona el ciclo de vida de `Contenedor` vía `lifespan` (abriendo SQLite WAL al arrancar y consolidando `PRAGMA wal_checkpoint(TRUNCATE)` al apagar). En pruebas recibe un `Contenedor` inyectado con `:memory:`.
  - Registra *exception handlers* globales para traducir las excepciones de dominio directamente a códigos HTTP semánticos:
    - `ErrorAutenticacion` $\to$ `401`
    - `ErrorPermiso` $\to$ `403`
    - `EntidadNoEncontrada` $\to$ `404`
    - `ErrorValidacion` $\to$ `422` (devolviendo tanto `detail` como el arreglo `problemas[]`)
    - `ErrorDominio` $\to$ `400`
  - Prepara montaje estático + fallback SPA para `frontend/dist` sin interceptar `/api/*`, y CORS controlado para `localhost:5173` / `127.0.0.1:5173` durante desarrollo Vite.
- **Gestión de Sesiones Dual (`deps.py`):**
  - `GestorSesiones` thread-safe emite tokens `secrets.token_urlsafe(32)` aceptados tanto por cabecera `Authorization: Bearer` como por `X-AquaTerra-Token` o cookie `HttpOnly` (`aquaterra_session`), lo que facilita descargas directas de `.xlsx`, `.csv` y `.jsonl` desde el navegador o `pywebview`.
- **Serializador recursivo (`schemas.py`):**
  - `serializar_objeto` transforma `dataclass` congelados, `StrEnum` y `Path` a JSON limpio conservando fidelidad exacta con las entidades del backend.

---

## 3. ¿Por qué se diseñó así?

1. **Cero duplicación científica:** Toda lógica de VPD, Pearson $r$, recta OLS, 5 candados, cotas anti-alucinación y validación (`DT-03`) permanece exclusivamente en Python (`aquaterra/core` y `aquaterra/application`). TypeScript nunca reimplementa cálculos agronómicos.
2. **Seguridad de credenciales:** `/api/sistema/estado` solo expone indicadores booleanos (`ubidots_configurado`, `ia_gemini_configurado`, `webhook_configurado`, `telegram_configurado`) sin devolver tokens ni API keys en respuestas GET.
3. **Respeto estricto a RBAC:** `operador` recibe `403 Forbidden` al intentar mutaciones críticas (parcelas, riegos, calibraciones, conectores, usuarios), mientras conserva acceso operativo a consultas, hardware e ingesta.

---

## 4. ¿Cómo mejora esto la ruta del Frontend final (`v6.0`)?

1. **Contrato HTTP limpio y tipado:** Cada pantalla React de las Fases 2, 3 y 4 tiene exactamente los endpoints y payloads agregados que necesita (por ejemplo, `/api/parcelas/{id}/riego/contexto` entrega en una sola llamada parcela, 5 candados, recomendación proactiva, bomba, programados, historial e incidencias).
2. **Desacoplamiento total entre UI y motor:** Permite iterar el diseño web en Vite con *Hot Reload* instantáneo contra el backend real, y luego servir el bundle compilado desde el mismo proceso Python sin Node.js en producción.
3. **Verificación automática antes de tocar UI:** Con `tests/test_api_v6.py`, cualquier cambio futuro en los servicios queda validado extremo a extremo antes de llegar a la interfaz.
