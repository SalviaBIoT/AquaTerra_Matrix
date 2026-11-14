# Sprint 07 · Auditoría Funcional 1:1, Persistencia de Sesión y Corrección de Enums (`v6.0.1`)

## 1. Diagnóstico de los Fallos Reportados en Captura de Pantalla

Al inspeccionar la captura en tiempo real del usuario dentro de `AppShell` (`Estación: Sin estaciones`, `0 nodos`, `Completitud Media 0%`, `Base SQLite WAL: Normal`, `Cloud Ubidots: Offline`, `Proveedor IA: local` y toast recurrente `"Usuario o contraseña incorrectos."`), se identificaron **cuatro causas raíz exactas**:

### Causa Raíz A — Confusión de HTTP 401 entre Credenciales Inválidas y Sesión Ausente/Reiniciada
1. En `aquaterra/api/deps.py`, `GestorSesiones` almacenaba tokens exclusivamente en un diccionario en RAM (`self._sesiones`). Si el servidor local se reiniciaba o el cliente WebView/navegador reabría con estado previo, toda petición autenticada fallaba con `401`.
2. `get_usuario_actual` lanzaba `ErrorAutenticacion()`, cuyo mensaje fijo en `aquaterra/core/domain/errores.py` era siempre `"Usuario o contraseña incorrectos."`.
3. En `frontend/src/lib/api.ts` y `frontend/src/context/AppContext.tsx`, un `401` posterior al login **no limpiaba la sesión obsoleta ni redirigía a `LoginPage`**, dejando al usuario atrapado dentro de `AppShell` con `radar = null`, `estaciones = []` y `estadoSistema = null`, disparando el toast de contraseña incorrecta con cada clic.

### Causa Raíz B — Discrepancia de Mayúsculas en `TipoEstacion` y Nombre de `Rol`
1. El dominio Python (`aquaterra/core/domain/entidades.py`) define valores en minúsculas (`terrabit_inti`, `inbeersa`, `sigatoka`, `conservacion`, `otro`) y roles (`admin`, `operador`, `lector`).
2. El frontend había tipado `TERRABIT_INTI`, `INBEERSA`, `SIGATOKA`, `CONSERVACION` y `visualizador`, provocando errores HTTP `422` al filtrar el Radar, al registrar nuevas estaciones en Configuración, al crear usuarios lectores, y rompiendo el agrupamiento multipanel adaptativo en Telemetría.

### Causa Raíz C — Campos Incompletos en `/api/sistema/estado` y Desajuste en Opciones de IA
1. `_estado_publico_seguro` (`aquaterra/api/routers/sistema.py`) no consultaba `PRAGMA journal_mode;` para reportar `"sqlite_wal": true/false` ni exponía `"ollama_disponible"` junto a `"ia_ollama_disponible"`.
2. `SettingsPage.tsx` y `AppShell.tsx` usaban `"hibrido"` / `"local"`, mientras `ConfiguracionIA` y el backend operan con `"auto"`, `"ollama"`, `"gemini"`, `"local_reglas"`.

### Causa Raíz D — Brechas Menores de Paridad vs Tkinter v5.0
Faltaban en la UI web/escritorio:
- Selector de suavizado por **Ventana Móvil SQLite** (`Crudo | 5m | 15m | 1h | 6h`) en Telemetría y su envío al exportar `.csv` / `.xlsx`.
- Visualización de **Indicadores Agronómicos de Familia** (`indicadores_inti`, `indicadores_inbeersa`, `indicadores_sigatoka`, `indicadores_conservacion`) en la tarjeta de Estación Focal del Radar.
- Botón **"Probar Ollama local"** (`?verificar_ollama=true`) y acción **"Cambiar clave"** por usuario en Configuración (`POST /api/usuarios/{id}/clave`).

---

## 2. Soluciones Implementadas

### Backend (`aquaterra/`)
- **`aquaterra/core/domain/errores.py` y `__init__.py`:** Nueva excepción `ErrorSesionExpirada` separada de `ErrorAutenticacion`.
- **`aquaterra/api/app.py`:** Manejadores HTTP 401 diferenciados (`codigo: "credenciales_invalidas"` solo en `/api/auth/login` vs `codigo: "sesion_expirada"` en rutas protegidas).
- **`aquaterra/api/deps.py` y `routers/auth.py`:** `GestorSesiones` ahora respalda los tokens mediante hash SHA-256 en tabla SQLite `sesiones_api` (`CREATE TABLE IF NOT EXISTS sesiones_api` con FK en cascada sobre `usuarios`), preservando sesiones activas ante reinicios de `uvicorn`/PyWebView y revocándolas tanto en RAM como en disco al ejecutar `/api/auth/logout`.
- **`aquaterra/api/routers/sistema.py`:** `_estado_publico_seguro` consulta `PRAGMA journal_mode;` para poblar `sqlite_wal` real y expone `ollama_disponible`.

### Frontend (`frontend/src/`)
- **`lib/api.ts` & `context/AppContext.tsx`:** Persistencia redundante (`localStorage` + `sessionStorage` + cookie `HttpOnly`), registro de manejador global de `401` (`registrarManejadorNoAutorizado`) con antirrebote (`ultimoAviso401Ref`) para cerrar sesión obsoleta y retornar limpiamente a `LoginPage` sin spamear toasts ni dejar el shell vacío, y manejo explícito de errores en `recargarGlobal()`.
- **`types/aquaterra.ts`, `lib/formatters.ts`, `DashboardPage.tsx`, `TelemetryPage.tsx`, `SettingsPage.tsx`:** Alineación estricta a `terrabit_inti | inbeersa | sigatoka | conservacion | otro`, `RolUsuario = "admin" | "operador" | "lector"`, e `ia_proveedor` (`auto | ollama | gemini | local_reglas`).
- **`AppShell.tsx`:** El popover *Salud del Ecosistema* evalúa correctamente `auto`, `ia_gemini_configurado`, `ia_ollama_disponible` y `sqlite_wal`.
- **Paridad v5.0:**
  - `TelemetryPage.tsx`: Selector `Media móvil` (`Crudo | 5m | 15m | 1h | 6h`) consultando `/api/estaciones/{id}/ventana-movil` e integrado en descargas `.csv` y `.xlsx`.
  - `DashboardPage.tsx`: Bloque de *Indicadores Agronómicos de Familia* en Estación Focal.
  - `SettingsPage.tsx`: Botón *Probar Ollama local* y cambio de contraseña por usuario en Usuarios & RBAC.

---

## 3. Verificación Ejecutada

1. **Frontend TypeScript, Lint & Build:** `npx tsc --noEmit`, `oxlint`, y `vite build` completados con código de salida `0`.
2. **Ruff + Suite Completa Pytest (`ruff check .` y `pytest -ra`):** `All checks passed!` en Ruff y **`94 passed` en Pytest (`38.00s`)**, incluyendo persistencia de sesión SQLite tras reinicio de `crear_app`, distinción `sesion_expirada` vs `credenciales_invalidas`, `sqlite_wal: True`, filtro por `tipo=terrabit_inti`, ventana móvil y cambio de clave.
3. **Smoke Test HTTP en Vivo sobre copia aislada de `data/runtime/aquaterra.db`:** Verificados `200 OK` en `/api/radar`, `/api/radar?tipo=terrabit_inti`, `/api/estaciones`, `/api/parcelas`, `/api/sistema/estado` (`sqlite_wal: True`, `ubidots_configurado: True`, `ia_proveedor: 'auto'`, `ia_gemini_configurado: True`), `/api/sistema/buscar`, `/api/copiloto/estado` y `/api/hardware/puertos`.
