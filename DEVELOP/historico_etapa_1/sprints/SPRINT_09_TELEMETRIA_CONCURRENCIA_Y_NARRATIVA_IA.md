# Sprint 09 — Telemetría Multiescala, Estabilidad de Sesión SQLite y Narrativa Ejecutiva de IA

**Fecha:** 2026-11-14  
**Estado:** Completado y verificado end-to-end (backend + frontend + Chrome headless CDP)  
**Rama:** `develop`

---

## 1. Diagnóstico Integral de Hallazgos

Durante la auditoría sobre la versión operativa en escritorio (incluyendo el análisis de `data/runtime/aquaterra_desktop.log`), se identificaron las causas raíz exactas de los tres problemas reportados:

### 1.1 Aplastamiento de escalas en Telemetría (`TelemetryPage.tsx`)
- **Síntoma:** La curva de **Presión Atmosférica (~857 hPa)** obligaba al eje Y compartido a escalar entre `0` y `1000`, comprimiendo visualmente la humedad de suelo (`77–98 %`), temperatura (`18–29 °C`) y VPD (`0.11–1.45 kPa`) casi contra el eje inferior.
- **Causa raíz:** `construirPanelesAdaptativos` esperaba identificadores de variables antiguos (`humedad_suelo_pct`, `temp_c`, `vpd_kpa`) que no coincidían con las claves reales de `TerraBit-NodoINTI` (`suelo_a`, `suelo_b`, `hum_aire`, `temp_aire`, `temp_raiz`, `presion`, `vpd`), por lo que las 7 series caían en el bloque genérico `"Series Temporales Registradas"` dentro de una sola gráfica.
- **Fallo secundario detectado en log:** El selector de media móvil enviaba `"5m"` y `"15m"` hacia `/api/estaciones/{id}/ventana-movil`, mientras que `VENTANAS_MOVILES_SEG` en `aquaterra/core/analitica/series.py` solo aceptaba `30m, 1h, 6h, 24h, 7d`, provocando 7 excepciones `ValueError` registradas en `aquaterra_desktop.log`.

### 1.2 Cierres inesperados de sesión ("Tu sesión ha expirado") al cambiar de estación o pestaña
- **Síntoma:** Al navegar rápido entre vistas o cambiar la estación seleccionada en `Radar General`, el frontend recibía `401 Unauthorized` y redirigía al login.
- **Causa raíz real capturada en `data/runtime/aquaterra_desktop.log`:**
  1. `ConexionSQLiteSegura.execute()` adquiría `self._lock` únicamente para invocar `conn.execute(...)` y lo liberaba de inmediato al retornar el `sqlite3.Cursor`.
  2. Cuando `DashboardPage` o `TelemetryPage` disparaban peticiones concurrentes al cambiar de estación/vista (`Promise.all` contra FastAPI threadpool), múltiples hilos ejecutaban `.execute()` y `.fetchone()` simultáneamente sobre la misma conexión C `sqlite3.Connection`, provocando lecturas corruptas o nulas (`ValueError: None is not a valid Rol` en `RepositorioUsuarios.obtener()` o `EntidadNoEncontrada`).
  3. En `aquaterra/api/deps.py` (`get_usuario_actual`), si esa lectura concurrente devolvía usuario no encontrado o inválido, el backend revocaba el token en memoria y devolvía `401 ErrorSesionExpirada`.
  4. Adicionalmente, `DashboardPage.tsx` no cancelaba la carga asíncrona en vuelo al cambiar rápidamente `estacionActivaId`, exponiendo a condiciones de carrera en el estado local.

### 1.3 Presentación cruda e informal de la IA (`Narrar 24h` y `Copiloto IA`)
- **Síntoma:** El mensaje generado por `"Narrar 24h con IA"` se mostraba como una cadena plana tipo WhatsApp llena de `*asteriscos*`, emojis, saltos lineales, etiquetas técnicas crudas (`optim`, `gemini:gemini-4-hydrogen`, `debil_o_nula`) y comillas invertidas (`` ` ``). En `Copiloto IA`, los mensajes mezclaban diagnóstico y fundamento agronómico en un solo bloque con sintaxis cruda.

---

## 2. Soluciones Implementadas

### 2.1 Telemetría Inteligente Multiescala y Filtro por Canal (`TelemetryPage.tsx` & `series.py`)
1. **3 Modos de Visualización Seleccionables:**
   - **Dominio físico (por defecto):** Agrupa automáticamente por compatibilidad dimensional:
     - *Dinámica Hídrica y Suelo (%)*: `suelo_a`, `suelo_b`, `hum_aire`, `mojado_foliar_pct`, etc.
     - *Régimen Térmico y Estrés Vapor (°C · kPa)* con **doble eje Y** (`°C` a la izquierda, `kPa` a la derecha para `vpd`).
     - *Atmósfera Barométrica (hPa)* aislada en su propia tarjeta para apreciar variaciones de 1–5 hPa sin aplastar los demás sensores.
     - *Energía, Radiación e Hidrología*: voltaje/batería, RSSI, radiación solar, lluvia y nivel de agua.
   - **Por variable (1 gráfica por canal):** Grilla dedicada con tarjeta individual por cada sensor activo, mostrando badges de `Último`, `Mín` y `Máx` más curva suave con área sombreada.
   - **Comparativa 0–100% (Normalizada min-max):** Normaliza temporalmente cada variable a su rango `[0%, 100%]` observado para comparar variaciones de fase entre magnitudes dispares (`hPa` vs `kPa` vs `%`), manteniendo en el tooltip el valor físico real junto con su porcentaje relativo.
2. **Chips interactivos de canales activos:** Permiten activar/desactivar variables con un clic (por ejemplo, ocultar Presión al vuelo) y restaurar con `"Mostrar todas"`. Se reinician automáticamente al cambiar de estación.
3. **Soporte nativo de `5m` y `15m` en núcleo analítico:** Se agregaron `"5m": 300` y `"15m": 900` a `VENTANAS_MOVILES_SEG` en `aquaterra/core/analitica/series.py`, eliminando los errores 500 al usar suavizado rápido.
4. **Etiqueta humana en correlación OLS:** Se reemplazó `debil_o_nula` por `etiquetarFuerzaCorrelacion(...)` (`Correlación débil o nula`, `Correlación moderada`, etc.).

### 2.2 Blindaje de Concurrencia SQLite y Ciclo de Sesión (`conexion.py`, `deps.py`, `DashboardPage.tsx`)
1. **`_CursorSeguro` y contexto `bloqueo()` en `aquaterra/infrastructure/db/conexion.py`:**
   - Todo cursor devuelto por `execute`, `executemany`, `executescript` y `cursor` ahora envuelve `fetchone`, `fetchmany`, `fetchall`, `__iter__`, `close` y `__getattr__` bajo `self._lock` reentrante (`threading.RLock`), impidiendo carreras entre `execute()` y la lectura de filas desde hilos concurrentes de FastAPI.
   - Se añadió el context manager `bloqueo()` para agrupar lecturas compuestas atómicas.
2. **`get_usuario_actual` atómico en `aquaterra/api/deps.py`:**
   - La validación del token y lectura del usuario en `RepositorioUsuarios.obtener` ahora ocurren dentro de `with contenedor.conexion.bloqueo():`.
3. **Guardia de cancelación en `DashboardPage.tsx`:**
   - El efecto de `cargarDetalleEstacion` utiliza bandera `cancelado` para descartar respuestas obsoletas si el usuario cambia rápidamente de estación activa.

### 2.3 Narrativa Ejecutiva 24h y Auditoría Limpia de Copiloto IA
1. **Payload estructurado en backend (`copiloto_servicio.py` y router `estaciones.py`):**
   - `generar_reporte_pulso_24h()` genera tanto una versión en texto plano profesional (`REPORTE EJECUTIVO 24H — ...`) sin asteriscos `*`, backticks `` ` `` ni emojis, como el objeto estructurado `reporte` (`estacion`, `severidad`, `completitud_pct`, `proveedor_legible`, `lecturas[]`, `alertas[]`, `diagnostico`, `justificacion`), manteniendo intacta la firma `(str, str)` de `narrar_pulso_24h()` para compatibilidad de pruebas.
   - Se incorporaron mapas legibles `_etiquetar_variable_reporte` y `_etiquetar_proveedor_ia` (`Google Gemini AI`, `Ollama Local`, `Motor Agronómico Determinista`).
2. **Tarjeta Ejecutiva en `DashboardPage.tsx`:**
   - Presenta cabecera con badge de severidad (`SeveridadBadge`), proveedor legible (`Google Gemini AI`), grilla de KPIs recientes en tarjetas compactas, banda de alertas si existen, y dos bloques claros: **Diagnóstico Técnico** y **Recomendación Agronómica**, además de botón `"Copiar informe"` limpio.
3. **Normalización y separación en `CopilotPage.tsx` y `formatters.ts`:**
   - Se agregaron `etiquetarProveedorIA`, `etiquetarFuerzaCorrelacion` y `limpiarTextoCopiloto`.
   - Tanto el historial como la auditoría activa separan diagnóstico y fundamento agronómico y renderizan alertas consideradas en formato de badges legibles sin sintaxis Markdown cruda.

---

## 3. Verificación Técnica Ejecutada (Post-Edición)

- **Frontend Typecheck + Lint + Build:**
  - `npx tsc --noEmit`: salida `0` (sin errores de tipos).
  - `npm run lint` (`oxlint`): `0 errors` (`19 warnings` preexistentes del proyecto).
  - `npm run build` (`tsc -b && vite build`): `✓ built in 1.56s`, bundle generado en `frontend/dist/`.
- **Backend Lint y Suite Unitaria/Integración:**
  - `ruff check .`: `All checks passed!`.
  - `pytest -ra`: `94 passed, 2 warnings in 42.81s`.
- **Verificación E2E Real en Chrome Headless + CDP (sobre copia temporal en `tempfile`):**
  - Login exitoso (`smoke_adm`), 6 ciclos de cambio rápido de estación en `Radar General` y navegación rápida entre las 7 pestañas principales: **0 sesiones cerradas**, **0 toasts de sesión expirada**, **0 excepciones JS**, **0 errores `500`**.
  - `"Narrar 24h con IA"` con respuesta real de Google Gemini AI: tarjeta ejecutiva renderizada con `INFORME EJECUTIVO 24H`, lecturas mapeadas, `DIAGNÓSTICO TÉCNICO` y `RECOMENDACIÓN AGRONÓMICA`, con `hasAsterisk=false` y `hasBacktick=false`.
  - `"Telemetría"` con media móvil `5m`: 0 errores `500`, 3 modos probados correctamente (`Dominio físico` separando Presión hPa, `Por variable` con 10 gráficas totales y Mín/Máx, `Comparativa 0–100%`) y toggle de chip `Presión Atmosférica`.
  - `"Copiloto IA"`: auditoría ejecutada con propuesta estructurada (`Fundamento Agronómico`), `hasAsterisk=false`, `hasBacktick=false`.

---

## 4. Recomendaciones y Optimizaciones Adicionales Detectadas

Durante la auditoría se detectaron oportunidades de mejora recomendadas para próximos sprints:

1. **Evitar `401` inicial en consola en carga sin sesión (`AppContext.tsx`):**
   - Al abrir la app sin sesión previa, el arranque dispara `GET /api/auth/me` aunque no haya token en `localStorage`, generando un `401` benigno en la pestaña Network/consola. Solo debería invocarse `/api/auth/me` si existe token guardado o soporte de cookie persistente explícito.
2. **Retroalimentación de latencia en Gemini AI (~8 s) + caché breve:**
   - La llamada a `Google Gemini AI` tarda ~7–9 s en generar el pulso o propuesta de calibración. Conviene añadir un estado visual con indicador de progreso ("Consultando motor Gemini AI (~5–8 s)…") y/o caché en memoria de 60 s por estación para reconsultas inmediatas.
3. **Estandarizar nombres de canales internos dentro de prosa Gemini:**
   - Ocasionalmente Gemini cita en texto corrido el nombre interno del JSON (`suelo_a`, `suelo_b`) sin comillas; ampliar `limpiarTextoCopiloto` para humanizar esos tokens puntuales haría la lectura 100 % editorial.
4. **Registrar marcador `gui` en `pyproject.toml`:**
   - Eliminar los 2 `PytestUnknownMarkWarning` declarando `markers = ["gui: pruebas que requieren entorno gráfico o ventana nativa"]` en `[tool.pytest.ini_options]`.
5. **Sincronización de zoom horizontal entre paneles de dominio:**
   - Usar `echarts.connect(...)` sobre los paneles de `Dominio físico` para que hacer zoom temporal en *Dinámica Hídrica* sincronice automáticamente el rango de *Atmósfera Barométrica* y *Régimen Térmico*.
