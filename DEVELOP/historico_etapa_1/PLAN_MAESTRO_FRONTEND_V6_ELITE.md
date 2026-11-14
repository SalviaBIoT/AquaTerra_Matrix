# 🌿 Plan Maestro de Transformación Estética e Implementación Frontend `v6.0` — AquaTerra Matrix

- **Código de Documento:** `PLAN_MAESTRO_FRONTEND_V6_ELITE`
- **Versión Objetivo:** `v6.0.0` (*Enterprise Bio-Tech Web App + Shell Nativo*)
- **Línea Base Actual:** `v5.0.0` (Backend `v4.2.0` + Consola Tkinter `ttkbootstrap`, **86/86 pruebas en verde**, `ruff` sin errores)
- **Propósito del Documento:** Servir de diagnóstico estético honesto sobre la UI actual y **manual completo de implementación** para ejecutar la reconstrucción del frontend en un nuevo hilo de trabajo sin pérdida de contexto ni riesgo sobre la lógica de negocio.

---

## 1. Diagnóstico Estético y Técnico de `v5.0` (Auditoría Visual Real)

Tras auditar las 11 capturas reales en ejecución de `AquaTerra Matrix v5.0.0`, el diagnóstico es inequívoco: **el backend tiene nivel industrial, pero la capa gráfica (`Tkinter` + `ttkbootstrap`) impone un techo visual y de experiencia de usuario que hace que el producto parezca académico/amateur.**

### 1.1. Fallas Estéticas Detectadas en Pantalla
1. **Efecto "Jaula de Neón" (`LabelFrame` excesivos):** Cada panel está rodeado por un marco de 1px de un color saturado distinto (verde, azul, rojo, ámbar), fragmentando la vista con ruido visual constante en lugar de usar jerarquía de elevación y superficies limpias.
2. **Sobrecarga de Números y Texto en Navegación y Topbar:**
   - El menú lateral muestra prefijos numéricos rígidos (`1. Radar (1 ⚠️)`, `2. Telemetría Multi-Nodo`, ..., `7. Nodos, Conectores & Users`) dentro de cajas cerradas centradas.
   - La barra superior apila selector de estación (texto truncado), barra de búsqueda sin *placeholder*, botón buscar, 4 etiquetas de estado (`Ubidots`, `Clima`, `IA`, `Radio`) y 4 botones de acción (`Sync`, `Notificar 24h`, `Excel .xlsx`, `*`) en una sola franja densa.
3. **Login con Renderizado Obsoleto:** La imagen de fondo no escala proporcionalmente en todo el ancho (deja una banda negra lateral derecha), el panel central simula transparencia con tramado punteado de Canvas (`stipple`) rodeado de un borde verde neón `#10b981`, y el botón de tema queda cortado (`Tem`).
4. **Tablas (`Treeview`) y Controles sin Aire Tipográfico:** Cabeceras de tabla con bloques sólidos saturados (`#0ea5e9` azul brillante, `#06b6d4` cian, `#f59e0b` naranja fuerte), filas pegadas con texto recortado (`Último d...`, `Mue...`) y scrollbars gruesos nativos de Tcl/Tk.
5. **Desproporción Espacial en Vistas Secundarias:**
   - En **Riego (`riegos_view.py`)**, el indicador `45 %` flota solo en una caja gigante vacía mientras los controles están comprimidos a la derecha.
   - En **Hardware (`hardware_view.py`)**, el visor de texto negro ocupa casi todo el alto de la pantalla con apenas dos líneas arriba.
   - En **Parcelas (`parcelas_view.py`)**, los 4 botones (`Guardar`, `Actualizar`, `Limpiar`, `Archivar`) compiten con igual peso cromático y saturación máxima.
6. **Gráficas Estáticas con Superposición:** Las leyendas de Matplotlib tapan líneas de tendencia (`Suelo B`), carecen de *hover tooltips* interactivos, zoom fluido o bandas translúcidas de rango óptimo.

### 1.2. Bug Crítico de Concurrencia SQLite Detectado Visualmente
En la ejecución real en vivo (al pulsar **Analizar 24h con IA** o **Notificar 24h** en el hilo de UI), apareció en el banner y en el footer el error exacto:
> `SQLite objects created in a thread can only be used in that same thread. The object was created in thread id 6044 and this is thread id 13492.`

- **Causa raíz verificada en código:** [`aquaterra/infrastructure/db/conexion.py`](../aquaterra/infrastructure/db/conexion.py) abre la conexión SQLite sin `check_same_thread=False` (línea 26: `sqlite3.connect(str(ruta), detect_types=0)`), y [`aquaterra/application/contenedor.py`](../aquaterra/application/contenedor.py) comparte esa única instancia de `sqlite3.Connection` entre los 10 servicios. Cuando un hilo secundario llama a `copiloto.narrar_pulso_24h()` o `sincronizacion.notificar_pulso_24h_estacion()`, SQLite rechaza la llamada desde otro `thread_id`.
- **Solución obligatoria en Fase 0:** Configurar una factoría thread-safe de conexiones WAL (o conexión con `check_same_thread=False` protegida por `threading.RLock()` / `threading.local()` por hilo en modo servidor API) sin alterar los contratos de dominio.

---

## 2. Decisión Arquitectónica `v6.0`: Frontend Web Empresarial + Shell Nativo *Local-First*

Parchear Tkinter solo suavizaría síntomas; **la única forma de lograr fluidez orgánica, tipografía moderna, glassmorphism real, gráficas interactivas y diseño tipo Linear/Vercel/Grafana** es separar la capa visual en un **Frontend Web moderno servido localmente por Python**.

### Stack Recomendado (100% Gratuito, Estándar Industrial y Offline-Ready)
| Capa | Tecnología | Por qué esta elección |
|---|---|---|
| **Core & Servicios (Intacto)** | `aquaterra/core/`, `aquaterra/application/`, `aquaterra/infrastructure/` | Todo el motor agronómico, 5 candados, Ollama/Gemini, Ubidots, Open-Meteo, `nRF24L01+`, MicroSD y `SQLite3 WAL` ya funcionan y pasan 86 tests. **No se reescribe.** |
| **Puente Local API** | **`FastAPI` + `Uvicorn`** (`aquaterra/api/`) | Expone endpoints REST + SSE/WebSocket locales (`http://127.0.0.1:8765/api/...`) delegando 1:1 en `Contenedor`. |
| **Frontend Web UI** | **`React 19` + `Vite` + `TypeScript`** (`frontend/`) | Ecosistema web maduro; el bundle compilado (`frontend/dist`) lo sirve `FastAPI` directamente sin requerir Node.js en el PC del cliente final. |
| **Estilos y Componentes** | **`Tailwind CSS v4` + `shadcn/ui` (Radix) + `Lucide Icons`** | Bordes suaves, radios coherentes, estados hover/focus fluidos, *Command Palette* (`Ctrl+K`), *Drawers*, *Popovers* y accesibilidad de teclado. |
| **Visualización Científica** | **`Apache ECharts` (`echarts-for-react`)** | Series temporales con zoom de rueda, *crosshair* sincronizado entre humedad/temperatura/VPD, degradados orgánicos bajo curvas y 0 congelamientos de UI. |
| **Ventana Desktop Nativa** | **`pywebview` (Edge WebView2 nativo en Windows 11)** | Al ejecutar `python -m aquaterra`, levanta `FastAPI` en segundo plano y abre la Web App dentro de una ventana nativa elegante (y opcional `--web` para abrir en navegador/red local). |

> **Nota de Entorno Verificada:** Actualmente el equipo **no tiene instalado Node.js / `npm`** (`node --version` no reconocido). En la **Fase 0** del plan se instala `OpenJS.NodeJS.LTS` vía `winget` únicamente en la máquina de desarrollo para compilar el frontend (`npm run build`). Para distribución al cliente, solo corre Python + `FastAPI` + `frontend/dist`.

---

## 3. Sistema de Diseño "Bio-Tech Orgánico" (La Identidad Estética `v6.0`)

Para que deje de parecer un tablero de "cajas verdes de laboratorio escolar" y transmita **tecnología agroecológica de alta precisión**:

### 3.1. Paleta Orgánica Refinada (Adiós Neones Chillones)
- **Modo Oscuro Principal (*Obsidian Canopy*):**
  - **Fondo Canvas:** `#0A0E0C` (carbón profundo con sutil calidez orgánica, no negro puro `#000` ni azul `#0b0f14`).
  - **Superficie Elevada 1 (Sidebar / Tarjetas):** `#111814` con borde sutil `rgba(236, 243, 238, 0.07)`.
  - **Superficie Elevada 2 (Hover / Modales / Popovers):** `#17211C` con `backdrop-filter: blur(16px)`.
  - **Texto:** Primario `#EEF3F0` · Secundario `#95A59C` · Terciario `#607067`.
  - **Acento Botánico Primario (dosificado al 5–8% de la pantalla):** `#10B981` $\to$ hover `#059669` (solo en el botón principal activo, indicador de foco y punto vivo).
  - **Acento Hídrico (telemetría agua/VPD):** `#38BDF8` (azul cielo calibrado) y `#2DD4BF` (turquesa suave).
  - **Estados Semánticos Elegantes (Badges translúcidos, NUNCA cajas sólidas):**
    - Óptimo: texto `#34D399`, fondo `rgba(16, 185, 129, 0.12)`, borde `rgba(16, 185, 129, 0.25)`.
    - Atención: texto `#FBBF24`, fondo `rgba(245, 158, 11, 0.12)`, borde `rgba(245, 158, 11, 0.25)`.
    - Crítico: texto `#F87171`, fondo `rgba(239, 68, 68, 0.12)`, borde `rgba(239, 68, 68, 0.25)`.
- **Modo Claro (*Field Daylight* — Trabajo bajo sol en campo):**
  - **Canvas Mineral Cálido:** `#F5F7F4` · **Tarjetas:** `#FFFFFF` · **Bordes:** `#E2E8E3` · **Sombra:** `0 1px 2px rgba(10, 14, 12, 0.04), 0 8px 24px rgba(10, 14, 12, 0.03)`.

### 3.2. Tipografía y Densidad de Datos
- **UI & Títulos:** `'Plus Jakarta Sans', 'Inter', system-ui, sans-serif` (pesos `400`, `500`, `600`, `700`; tracking `-0.02em` en números KPI).
- **Datos Numéricos y Series:** `'JetBrains Mono', monospace` con **`font-variant-numeric: tabular-nums`** para que columnas de porcentajes, hPa, kPa y relojes queden perfectamente alineadas al píxel.
- **Regla de Oro de Contenedores:** Eliminar **todos** los `LabelFrame` con borde coloreado. Toda tarjeta usa la misma elevación limpia, `rounded-xl` (`12px` de radio), padding interno generoso (`20px`) y espacio libre mínimo del **25%** en la composición.

### 3.3. Limpieza del *App Shell* (Eliminando la Sobrecarga Visual)
1. **Sidebar Fluido Sin Números (`232px`, colapsable a `68px`):**
   - **Cero prefijos `1.`, `2.`, `3.`** y cero bordes alrededor de cada botón.
   - Agrupación orgánica en 3 bloques con subtítulos diminutos en gris apagado (`11px uppercase tracking-wider`):
     - *MONITOREO:* **Radar General** (píldora roja discreta `1` solo si hay nodos críticos) · **Telemetría**
     - *OPERACIÓN:* **Parcelas** · **Riego & Candados** · **Copiloto IA**
     - *INFRAESTRUCTURA:* **Radio & MicroSD** · **Sistema & Conectores**
   - Ítem activo: fondo translúcido `rgba(16, 185, 129, 0.12)`, barra vertical izquierda de `3px` en `#10B981`, icono y texto nítido.
   - Pie fijo minimalista: Avatar con iniciales (`AD`), nombre/rol y dos acciones discretas (`Cerrar sesión` / icono `Power` para salir con confirmación).
2. **Topbar Minimalista (`56px`):**
   - **Izquierda:** Selector elegante de estación con punto de estado + *Breadcrumb* de la vista activa (`TerraBit-NodoINTI · Óptimo`).
   - **Centro:** Botón falso de búsqueda (`Buscar en bitácoras, nodos o comandos...   Ctrl K`) que al pulsarlo abre un **Command Palette flotante** con blur.
   - **Derecha (máximo 4 controles limpios):**
     1. Píldora unificada de salud (`Online · 4/4 activos` — al hacer clic abre un Popover detallado con Ubidots, Open-Meteo, IA y puertos COM).
     2. Botón primario sutil **Sincronizar** (gira el icono en vivo con estado SSE).
     3. Menú **Exportar / Notificar** (agrupa `.xlsx` y alerta 24h a WhatsApp/Telegram).
     4. Botón icono **Tema Sol/Luna**.

---

## 4. Plan de Ejecución en 5 Fases (De Cero a Élite)

### Fase 0: Prerrequisitos y Saneamiento de Concurrencia Backend (½ día)
- **Acciones:**
  1. Instalar Node.js LTS (`winget install OpenJS.NodeJS.LTS`) en el equipo de desarrollo.
  2. Corregir el fallo de hilos SQLite en [`aquaterra/infrastructure/db/conexion.py`](../aquaterra/infrastructure/db/conexion.py) y [`aquaterra/application/contenedor.py`](../aquaterra/application/contenedor.py): soportar `check_same_thread=False` con bloqueo `threading.RLock()` o proveedor de conexión *thread-local* para el servidor API y los hilos de sincronización/notificación/IA.
  3. Añadir dependencias Python al entorno (`fastapi`, `uvicorn[standard]`, `pydantic`, `pywebview` opcional).
- **Criterio de éxito:** `pytest -ra` sigue pasando al 100% (`>= 86 passed`), y las llamadas concurrentes desde hilos a `narrar_pulso_24h` / `notificar_pulso_24h_estacion` dejan de arrojar `SQLite objects created in a thread`.

### Fase 1: Capa API Local (`aquaterra/api/`) — Puente Limpio 1:1 (1 día)
- **Acciones:**
  1. Crear `aquaterra/api/app.py`, `aquaterra/api/deps.py`, `aquaterra/api/schemas.py` y routers modulares por dominio:
     - `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`
     - `GET /api/radar`, `GET /api/estaciones`, `POST /api/estaciones`, `GET /api/estaciones/{id}/pulso`, `GET /api/estaciones/{id}/series`, `GET /api/estaciones/{id}/pronostico`, `GET /api/estaciones/{id}/eventos`, `POST /api/estaciones/{id}/reparar-rtc`, `POST /api/estaciones/{id}/narrar-24h`
     - `GET/POST/PATCH/DELETE /api/parcelas` + `GET /api/monitor/comparativo`
     - `GET /api/parcelas/{id}/riego/contexto` (candados, recomendación proactiva, salud bomba, historial, cola programada, incidencias), `POST /api/parcelas/{id}/riego/aplicar`, `POST /api/parcelas/{id}/riego/programar`
     - `GET /api/copiloto/estado`, `POST /api/copiloto/consultar`, `POST /api/copiloto/aplicar`, `POST /api/copiloto/rollback`, `GET /api/copiloto/dataset.jsonl`
     - `GET /api/hardware/puertos`, `POST /api/hardware/serial/leer`, `POST /api/hardware/tramas`, `POST /api/hardware/microsd/escanear`, `POST /api/hardware/microsd/importar`
     - `GET /api/sistema/estado`, `POST /api/sistema/sync`, `POST /api/sistema/notificar-24h`, `POST /api/sistema/conectores`, `POST /api/sistema/ollama/precalentar`, `POST /api/sistema/worker`, `GET /api/sistema/buscar?q=...`, `GET/POST /api/usuarios`, `GET /api/exportar/xlsx` y `.csv`
  2. Mantener **cero lógica de negocio en FastAPI**: cada endpoint solo valida JSON, extrae el `Usuario` de sesión y llama al método equivalente de `Contenedor`.
- **Criterio de éxito:** Suite `tests/test_api_v6.py` con `fastapi.testclient.TestClient` validando login, RBAC (`ErrorPermiso -> 403`), radar, riego con 5 candados, copiloto y sync offline sin excepciones.

### Fase 2: Fundación Visual Web, Tokens Orgánicos, Login y App Shell (1–2 días)
- **Acciones:**
  1. Inicializar `frontend/` con Vite + React + TypeScript + Tailwind v4 + `shadcn/ui`.
  2. Configurar fuentes locales/empaquetadas (`Plus Jakarta Sans` + `JetBrains Mono` vía `@fontsource` para funcionar 100% offline).
  3. Rediseñar **Login (`LoginPage`)**: layout asimétrico *Split-Screen* (izquierda: fotografía agroecológica de alta resolución con gradiente orgánico difuminado + narrativa sutil de telemetría; derecha: tarjeta limpia sin tramado pixelado ni bordes neón, con toggle de tema y salida segura).
  4. Construir **AppShell**: Sidebar colapsable sin números, Topbar de `56px`, *Command Palette* `Ctrl+K` conectado a `/api/sistema/buscar`, Popover de conectividad híbrida y *Toast notifications* elegantes (`sonner`).
- **Criterio de éxito:** Navegación instantánea (`< 50ms`) entre las 7 rutas en modo oscuro (*Obsidian Canopy*) y claro (*Field Daylight*) con 0 errores de consola y diseño responsivo `1280px`–`2560px`.

### Fase 3: Radar Bento, Telemetría ECharts Interactiva y Parcelas (2 días)
- **Acciones:**
  1. **Radar General (`DashboardPage`):**
     - Banner ejecutivo IA con tipografía editorial limpia, etiqueta de proveedor usado (`Gemini` / `Ollama` / `Reglas`) y esqueletos de carga (*Skeleton loaders*) mientras procesa.
     - Fila superior de **4 KPI Cards minimalistas** con *sparkline* sutil de tendencia (sin bordes de colores chillones).
     - Tabla interactiva de estaciones y tabla de Pulso 24h con **badges tipo píldora**, alineación numérica tabular (`tabular-nums`), barras visuales finas de completitud y filtro rápido.
     - Gráfica compacta de pronóstico horario Open-Meteo (temperatura + probabilidad de lluvia combinada en barras translúcidas + curvas suaves).
  2. **Telemetría Multi-Nodo (`TelemetryPage`):**
     - Migrar las gráficas por `TipoEstacion` (`TERRABIT_INTI`, `INBEERSA`, `SIGATOKA`, `CONSERVACION`) a **Apache ECharts** con áreas degradadas orgánicas, leyenda superior limpia (fuera del área de trazo), *crosshair* sincronizado, selector segmentado `6h | 24h | 7d | Todo` y pestaña de Correlación Bivariada con dispersión + recta de regresión OLS interactiva.
  3. **Parcelas (`ParcelsPage`):**
     - Vista tabla/tarjetas con medidor visual de humedad del suelo, badge de cultivo/suelo y estación IoT vinculada; botón `+ Nueva Parcela` que abre un **Sheet/Drawer lateral deslizante** limpio en lugar de partir la pantalla en dos mitades desbalanceadas.
- **Criterio de éxito:** Gráficas fluidas a 60fps, exportación `.csv` y `.xlsx` operativa y cero solapamiento de etiquetas.

### Fase 4: Control 5 Candados, Copiloto IA Conversacional, Radio `nRF24L01+` y Configuración (2 días)
- **Acciones:**
  1. **Riego, 5 Candados & Bomba (`IrrigationPage`):**
     - Selector de parcela con tarjeta resumen de contexto; **Stepper horizontal limpio de los 5 Candados** (`Humedad`, `Lluvia`, `VPD/ET0`, `Ventana Nocturna`, `Enclavamiento Bomba`) en verde salvia / ámbar / rojo translúcido; tarjeta de recomendación proactiva (`horas hasta estrés`, $\Delta\theta/\Delta t$); formulario compacto de dosis y pestaña de historial/incidencias post-riego ($\Delta\theta_A / \Delta\theta_B$).
  2. **Copiloto IA & Calibración (`CopilotPage`):**
     - Interfaz tipo consola/chat técnico a la izquierda (prompts rápidos tipo *chips* + historial conversacional real) y **Auditor de Calibración Diff** a la derecha con barras de rango físico permitido `[min .. max]` mostrando visualmente dónde cae el cambio propuesto antes de pulsar **Aplicar (1 clic)** o **Rollback**.
  3. **Radio `nRF24L01+` & MicroSD (`HardwarePage`):**
     - Tarjetas descubiertas para puertos `COM` (`COM3..COM12`), botón de escucha USB-Serial, consolita elegante estilo terminal (`max-height` balanceada, NO 90% pantalla vacía) para decodificar tramas, y panel derecho dedicado a escáner MicroSD, reparación de reloj RTC (`calidad=2`) y log reciente de eventos.
  4. **Sistema, Conectores & Usuarios (`SettingsPage`):**
     - Navegación vertical interna (*Tabs verticales* estilo Vercel/Linear): *Conectores Cloud & WhatsApp/Telegram*, *IA Híbrida & GPU Ollama*, *Estaciones IoT & GPS*, *Usuarios y Permisos*.
- **Criterio de éxito:** Paridad funcional del 100% respecto a `v5.0`, con flujos guiados y cero bloques vacíos desproporcionados.

### Fase 5: Empaquetado Nativo, Tests E2E y Lanzamiento `v6.0.0` (1 día)
- **Acciones:**
  1. Compilar `frontend/dist` (`npm run build`) y servirlo estáticamente desde `aquaterra/api/app.py`.
  2. Conectar `python -m aquaterra` para lanzar `FastAPI` en hilo local (puerto libre o `8765`) + ventana `pywebview` (título limpio, icono AquaTerra, cierre seguro que ejecuta `contenedor.cerrar()` y `PRAGMA wal_checkpoint(TRUNCATE)`). Flag `--web` abre en navegador para uso multipuesto/tableta en finca.
  3. Correr verificación completa (`ruff check .`, `pytest -ra`, `npm run build` + smoke Playwright/HTTP) y generar reporte `REP-009` + tag `v6.0.0`.

---

## 5. Mapa Verificado de Contratos Backend (Para el Hilo de Implementación)

El nuevo chat **NO necesita reexplorar todo el proyecto ni tocar `aquaterra/core/`**. Los servicios disponibles en `Contenedor` ([`aquaterra/application/contenedor.py`](../aquaterra/application/contenedor.py)) son exactamente:

- **`contenedor.auth` (`ServicioAutenticacion`, [`servicios.py`](../aquaterra/application/servicios.py)):**
  - `iniciar_sesion(usuario, clave) -> Usuario`
  - `listar_usuarios() -> list[Usuario]`
  - `crear_usuario(actor, *, usuario, nombre, clave, rol) -> Usuario`
  - `cambiar_clave(actor, *, usuario_id, nueva_clave) -> None`
- **`contenedor.parcelas` (`ServicioParcelas`, [`servicios.py`](../aquaterra/application/servicios.py)):**
  - `listar(*, solo_riego_auto=False) -> list[Parcela]`
  - `obtener(parcela_id) -> Parcela`
  - `crear(actor, **campos) -> Parcela`
  - `actualizar(actor, parcela_id, **campos) -> Parcela`
  - `archivar(actor, parcela_id) -> Parcela`
- **`contenedor.riego` (`ServicioRiego`, [`servicios.py`](../aquaterra/application/servicios.py)):**
  - `aplicar_riego(actor, parcela_id, litros, *, fecha_iso=None) -> ResultadoRiego`
- **`contenedor.monitor` (`ServicioMonitor`, [`servicios.py`](../aquaterra/application/servicios.py)):**
  - `humedad_por_parcela() -> list[tuple[str, float]]`
  - `consumo_por_parcela() -> list[tuple[str, float]]`
- **`contenedor.radar` (`StationDiscoveryService`, [`radar_servicio.py`](../aquaterra/application/radar_servicio.py)):**
  - `listar_radar_priorizado() -> list[EntradaRadarEstacion]`
  - `buscar_estaciones(termino="") -> list[Estacion]`
  - `detectar_archivos_estacion(directorios) -> list[OrigenDatosDetectado]`
  - `importar_archivo_estacion(ruta, ...) -> ResultadoImportacionEstacion`
  - `sincronizar_humedad_parcelas(estacion_id) -> int`
  - `listar_estaciones() -> list[Estacion]`, `obtener_estacion(id)`, `listar_eventos_estacion(id, limite=50)`
- **`contenedor.pulso` (`NodePulseService`, [`pulso_servicio.py`](../aquaterra/application/pulso_servicio.py)):**
  - `obtener_pulso_24h(estacion_id, ahora=None)`
  - `consultar_ventana_movil(estacion_id, variable, ventana, ...)`
  - `comparar_variables(estacion_id, var_x, var_y, ventana, ...)`
  - `obtener_series_ventana(estacion_id, ventana, ...)`
- **`contenedor.control` (`DecisionAndControlService`, [`control_servicio.py`](../aquaterra/application/control_servicio.py)):**
  - `recomendar_riego_parcela(parcela_id, ...)`
  - `programar_riego_validado(actor, parcela_id, ...)`
  - `registrar_verificacion_e_incidencia(...)`
  - `listar_riegos_parcela(parcela_id)`, `listar_riegos_programados(parcela_id=None)`, `listar_incidencias_parcela(parcela_id)`, `ultimo_salud_actuador(parcela_id)`
- **`contenedor.copiloto` (`CalibrationCopilotService`, [`copiloto_servicio.py`](../aquaterra/application/copiloto_servicio.py)):**
  - `obtener_calibracion_efectiva(estacion_id=None)`
  - `consultar_copiloto(pregunta, *, parcela_id=None, estacion_id=None)`
  - `aplicar_ajustes_interaccion(actor, interaccion_id, ...)`
  - `revertir_calibracion(actor, estacion_id, ...)`
  - `listar_historial_conversaciones(...)`
  - `exportar_dataset_entrenamiento_jsonl(ruta_destino)`
  - `narrar_pulso_24h(estacion_id)`
  - `buscar_inteligente_bitacora(consulta, estacion_id=None)`
- **`contenedor.exportacion` (`AnalyticsAndExportService`, [`exportacion_servicio.py`](../aquaterra/application/exportacion_servicio.py)):**
  - `exportar_xlsx_estacion(estacion_id, ruta_destino)`
  - `exportar_csv_estacion(estacion_id, ruta_destino)`
- **`contenedor.sincronizacion` (`ActiveSyncAndGatewayService`, [`sincronizacion_servicio.py`](../aquaterra/application/sincronizacion_servicio.py)):**
  - `asegurar_estaciones_terrabit_base()`, `sincronizar_todo_hibrido(dias_clima=2)`, `notificar_pulso_24h_estacion(estacion_id)`
  - `ingerir_linea_gateway_radio(linea)`, `ingerir_lote_lineas_gateway(lineas)`
  - `puertos_serial_disponibles()`, `leer_puerto_serial_lote(puerto, baudrate=115200)`
  - `listar_pronostico_estacion(estacion_id)`, `registrar_estacion(actor, ...)`, `reparar_rtc_estacion(actor, estacion_id)`
  - `reconfigurar_conectores(actor, ...)`, `resumen_estado_conectividad(verificar_ollama=False)`
  - `iniciar_worker_segundo_plano()`, `detener_worker_segundo_plano()`, `worker_activo`

### Reglas Innegociables del Proyecto para el Siguiente Hilo
1. **Nunca exponer secretos:** Ni `UBIDOTS_TOKEN`, ni `GEMINI_API_KEY`, ni webhooks reales en archivos versionados (usar siempre `.env` local ignorado por Git y `config.py`).
2. **Arquitectura Limpia:** No duplicar fórmulas agronómicas (`VPD`, `Pearson r`, `OLS`, `5 Candados`) en TypeScript; el frontend es pura presentación e interacción sobre la API Python.
3. **Resguardar Compatibilidad & Tests:** Mantener los 86 tests actuales pasando (`pytest -ra`) hasta que el reemplazo de UI sea validado completamente, añadiendo pruebas de API (`TestClient`) y build de producción en `frontend/dist`.

---

## 6. Prompt Listo para Iniciar el Nuevo Chat de Implementación

Copia y pega este texto al abrir el nuevo chat:

```text
Hola maestro. Estamos en el proyecto C:\Users\danie\Developer\AquaTerra_Matrix (rama develop, tag base v5.0.0).
Lee únicamente el documento DEVELOP/PLAN_MAESTRO_FRONTEND_V6_ELITE.md antes de empezar y verifica brevemente aquaterra/infrastructure/db/conexion.py y aquaterra/application/contenedor.py.

Tu misión exclusiva es ejecutar el Plan Maestro v6.0 por fases verificables (empezando por Fase 0 y Fase 1):
1. Arreglar el fallo de concurrencia SQLite multi-hilo (Fase 0) e instalar/verificar Node.js + dependencias FastAPI/Uvicorn/pywebview.
2. Construir la capa aquaterra/api/ (FastAPI) mapeando los servicios de Contenedor con sus pruebas en TestClient (Fase 1).
3. Construir el frontend web empresarial en frontend/ (React + Vite + TypeScript + Tailwind + shadcn/ui + Apache ECharts + fuentes locales Plus Jakarta Sans & JetBrains Mono) siguiendo exactamente la estética "Bio-Tech Orgánico" descrita en DEVELOP/PLAN_MAESTRO_FRONTEND_V6_ELITE.md, integrado en shell nativo pywebview + modo --web.

Trabaja de forma ordenada fase por fase, sin tocar la lógica científica de aquaterra/core/, validando con pytest, ruff y build de Vite al cerrar cada fase.
```
