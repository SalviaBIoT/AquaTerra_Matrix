# Reporte General del Sistema y Arquitectura Completa — AquaTerra Matrix v6.0

> Documento técnico integral listo para evaluación por IA externa / comité de arquitectura sobre selección de modelos IA (Nube vs Local), gestión de cuotas en Google AI Studio y optimización del módulo **Mandarino IA**.

---

## PARTE I — Reporte General del Sistema y Entorno de Cómputo

### 1.1 Hardware Real Medido (Estación de Desarrollo / Ejecución Local)
- **Sistema Operativo:** Microsoft Windows
- **Procesador (CPU):** `Intel(R) Core(TM) i5-10300H CPU @ 2.50GHz`
- **Memoria RAM del Sistema:** `15.84 GB`
- **Aceleradores Gráficos (GPU):**
  - Dedicada: `NVIDIA GeForce GTX 1650` (Driver `32.0.15.9174` — serie portátil de 4 GB VRAM)
  - Integrada: `Intel(R) UHD Graphics` (Driver `27.20.100.8280`)

### 1.2 Stack de Software & Runtime
- **Backend Python (`requires-python >= 3.11`, entorno virtual en Python 3.13):**
  - `fastapi>=0.115,<1` + `uvicorn[standard]>=0.30,<1`
  - `pywebview>=5.0,<7` (ventana nativa desktop) + Edge/Chrome PWA / acceso navegador local
  - `google-genai 3.3.0` (API `Interactions`, SDK oficial Gemini)
  - `pyserial>=3.5`, `Pillow>=10.3`, `matplotlib>=3.9,<4`, `ttkbootstrap>=1.10.1,<3`
  - Linter / Tests: `ruff`, `pytest` (`93` pruebas core/API/integración + `4` pruebas heredadas Tkinter marcadas `@pytest.mark.gui`)
- **Frontend React / TypeScript (`frontend/package.json`):**
  - `react ^19.3.1`, `react-dom ^19.3.1`, `typescript ~7.0.2`, `vite ^8.3.6`
  - `tailwindcss ^4.3.5`, `echarts ^6.1.0`, `lucide-react ^1.73.0`, `sonner ^2.0.8`
  - `@fontsource/plus-jakarta-sans ^5.3.0`, `@fontsource/jetbrains-mono ^5.3.0`
  - Linter: `oxlint ^1.90.0`

### 1.3 Estado Real de los Motores de IA Configurados (`aquaterra/infrastructure/ia/proveedores.py`)
El sistema implementa un **Orquestador en Cascada Híbrida de 3 Niveles (`OrquestadorIA`, modo `auto`)**:

| Nivel | Proveedor | Modelo Configurado | Estado / Hallazgos Medidos en Campo |
|---|---|---|---|
| **1. Nube** | Google Gemini AI Studio (`/v1beta/interactions`) | `gemini-4-hydrogen` (`MODELO_GEMINI_POR_DEFECTO`) | La clave `GEMINI_API_KEY` configurada opera en **Free Tier** con límite observado de **20 peticiones/día (`20 requests per day`)**. Al llegar a `HTTP 429` bloquea por ~12+ horas (`too_many_requests`). Tras Sprint 11 usa `timeout=12s`, máximo **3 reintentos rápidos** solo en `408/5xx`, cero reintento en `429` (falla en **~1.36 s**) y activa **Circuit Breaker de 300 s**. |
| **2. Borde Local (Offline)** | Ollama (`http://127.0.0.1:11434/api/chat`) | `qwen2.5:3b` (`3.1B`, `Q4_K_M`, peso en disco `~1.93 GB`, contexto `32768`) | ÚNICO modelo actualmente descargado en Ollama local. Latencia medida en arranque frío: **17.57 s**; se añadió `keep_alive: "10m"` para mantenerlo cargado en la VRAM de la GTX 1650 (4 GB). Limitación cualitativa: al ser 3B cuantizado, en saludos simples tiende a sobre-anclarse en parámetros JSON de calibración si el prompt incluye todas las cotas metrológicas. |
| **3. Determinista** | Motor Reglado Nativo (`AsesorDeterministaCopiloto`) | Sin pesos neuronales (reglas agronómicas + auditoría física) | Latencia **< 5 ms**, 100% offline. Soporta saludos contextualizados, recomendaciones prácticas ante alertas activas y auditoría determinista contra cotas físicas. |

### 1.4 Cómo Consultar Límites, Cuotas y Uso en Google AI Studio
Para inspeccionar exactamente cuántas peticiones/día, tokens por minuto (TPM) y modelos disponibles tiene tu cuenta:
1. **Monitor directo de Rate Limits:** Abre [https://ai.dev/rate-limit](https://ai.dev/rate-limit) iniciado con la misma cuenta Google dueña de la `GEMINI_API_KEY`. Ahí verás una tabla por **cada modelo** (`RPM`, `TPM`, `RPD — Requests Per Day`) en tu nivel actual (*Free Tier* vs *Tier 1 Paid*).
2. **Consola de Google AI Studio (Uso y Claves API):**
   - Entra a [https://aistudio.google.com/](https://aistudio.google.com/) → menú lateral izquierdo **API Keys** (verifica a qué proyecto de Google Cloud pertenece tu clave) y **Usage & Billing** / **Quota**.
   - Revisa el historial diario y el estado de facturación del proyecto asociado: muchos modelos Flash/Lite en Google AI Studio tienen **RPD muy superiores** al de modelos experimentales o con límite estricto de 20 req/día en Free Tier.
3. **Configuración por variables de entorno en AquaTerra Matrix (sin recompilar):**
   - `AQUATERRA_GEMINI_MODEL`: permite cambiar el modelo nube (ej. probar modelos Flash con mayor cuota RPD).
   - `AQUATERRA_IA_PROVEEDOR`: `auto` (defecto) | `gemini` | `ollama` | `local_reglas`.
   - `AQUATERRA_OLLAMA_MODEL`: permite cambiar el modelo local (ej. `qwen2.5:3b`, `gemma3:4b`, `qwen2.5:7b`).

---

## PARTE II — Reporte General de Todo el Proyecto (`AquaTerra Matrix v6.0`)

### 2.1 Propósito y Alcance Agronómico / Bio-IoT
**AquaTerra Matrix v6.0** es una plataforma desktop/web local-first para monitoreo agrometeorológico, bio-IoT e irrigación controlada en nodos de campo ESP32/ESP32-S3 del ecosistema **TerraBit**, cubriendo cuatro dominios reales:
1. **TerraBit Nodo INTI:** Humedad edáfica A/B, temperatura radicular y del aire, humedad relativa, presión atmosférica, VPD, batería solar y lluvia.
2. **InBeersa (Abejas Angelitas / *Melipona*):** Homeostasis térmica interna del nido (ej. umbral mínimo `29.0 °C`), humedad interna, VPD y actividad.
3. **Sigatoka_C (Plátano):** Condiciones microclimáticas favorables a infección foliar (humedad prolongada/temperatura).
4. **Conservación Páramos & *Polylepis*:** Estaciones ambientales de alta montaña con trazabilidad histórica offline.

### 2.2 Arquitectura Modular por Capas (`aquaterra/`)
- **Dominio y Núcleo Puro (`aquaterra/core/` — cero dependencias de UI o framework HTTP):**
  - `core/domain/`: Entidades inmutables (`Estacion`, `Parcela`, `InteraccionCopiloto`, `VersionCalibracion`, `IncidenciaRiego`), errores tipados y validadores.
  - `core/agronomia/`: Cálculos psicrométricos (`psicrometria.py`: VPD, punto de rocío) y balance hídrico (`hidrico.py`).
  - `core/analitica/`: `pulso.py` (estado 24h, completitud de telemetría, detección de severidades `normal`/`atencion`/`critico`) y `series.py` (correlación bivariada de Pearson y regresión OLS).
  - `core/control/`: `enclavamientos.py` (**5 candados físicos de seguridad**: enclavamiento por lluvia, saturación de suelo, volumen máximo por evento, energía/batería mínima y estado de bomba), `planificador.py` y `actuadores.py`.
  - `core/copiloto/`: `cotas_calibracion.py` (catálogo metrológico con rangos físicos estrictos y paso máximo permitido por iteración para impedir alucinaciones de IA), `contratos_ia.py` (contrato JSON + contexto multi-turno + panorama global) y `asesor_reglas.py`.
- **Servicios de Aplicación (`aquaterra/application/`):**
  - `contenedor.py`: Inyección de dependencias unificada.
  - `pulso_servicio.py`, `radar_servicio.py`, `control_servicio.py`, `copiloto_servicio.py`, `sincronizacion_servicio.py`, `exportacion_servicio.py`, `servicios.py`.
- **Infraestructura (`aquaterra/infrastructure/`):**
  - `db/`: SQLite en modo **WAL** (`conexion.py`, `esquema.py`, `repositorios.py`) para concurrencia segura entre API HTTP, ingesta IoT y UI; migrador desde versiones heredadas (`legacy/migrador_v32.py`).
  - `iot_ingest/`: Adaptadores de trama multi-familia (`adaptadores.py`), puerto serie COM (`serial_gateway.py`) y cliente Ubidots (`ubidots_client.py`).
  - `clima/`: `open_meteo_client.py` (caché local 48h con evapotranspiración ET0 y lluvia esperada).
  - `ia/`: `proveedores.py` (Orquestador Híbrido Gemini Interactions + Ollama + Reglas).
  - `notificaciones/`: `mensajeria.py` (webhooks n8n / Telegram).
  - `exportacion/`: Reportes CSV y Excel `.xlsx` nativos sin dependencias pesadas (`xlsx_writer.py`, `exportador_estacion.py`).
  - `seguridad/`: Hashing de contraseñas y aislamiento de roles (`admin`, `operador`, `lector`).
- **API HTTP REST (`aquaterra/api/`):**
  - FastAPI (`app.py`, `deps.py`, `schemas.py`) con cookies `HttpOnly` y 7 routers:
    `auth.py`, `estaciones.py`, `parcelas.py`, `riego.py`, `copiloto.py`, `hardware.py`, `sistema.py`.
- **Launcher Nativo (`aquaterra/desktop.py`):** Levanta servidor FastAPI embebido (`ServidorLocalEmbebido`), sirve `frontend/dist` precompilado y abre ventana PyWebView (con fallback Edge/Chrome `--app` y accesos directos de escritorio).

### 2.3 Arquitectura Frontend (`frontend/src/`)
Aplicación SPA compilada con React 19 + Vite 8 + Tailwind CSS v4 + ECharts 6:
1. **`LoginPage.tsx`:** Acceso multi-usuario con sesión segura por cookie `HttpOnly`.
2. **`DashboardPage.tsx` (Radar General):** Salud global del ecosistema, tarjetas de estaciones, completitud 24h y pronóstico Open-Meteo 48h.
3. **`TelemetryPage.tsx` (Telemetría y Analítica):** Series temporales desacopladas por escalas/variables (evita aplastamiento por presión atmosférica hPa), correlación Pearson/OLS y comparativa hídrica por parcela.
4. **`ParcelsPage.tsx` (Parcelas):** Gestión de lotes, cultivos, tipos de suelo y asociación con estaciones.
5. **`IrrigationPage.tsx` (Control & Riego):** Simulación y ejecución de riego validando en tiempo real los 5 candados físicos y auditoría de incidencias post-riego.
6. **`CopilotPage.tsx` (Mandarino IA Studio — Sprint 11):** Estudio de 3 columnas con avatar transparente animado de Mandarino, canales estrictamente segmentados por estación + `Charla General` con visión global, memoria de últimos 5 turnos del hilo, menú interactivo/didáctico *Inicio Mandarino*, panel proactivo derecho y auditoría/rollback + exportación `.jsonl`.
7. **`HardwarePage.tsx` (Hardware IoT):** Gestión de puertos COM seriales, ingestión de tramas ESP32/LoRa, importación CSV/MicroSD y sincronización Ubidots.
8. **`SettingsPage.tsx` (Configuración):** Administración de parámetros del sistema, cuentas y conectividad IA/Clima/Mensajería.

---

## PARTE III — Preguntas Estratégicas Listas para Consultar a una IA en Nube

Copia y pega este documento completo en tu IA en nube junto con estas 4 preguntas puntuales para recibir una recomendación adaptada exactamente a tu hardware y cuota:

1. *Dado mi equipo (`i5-10300H`, `15.84 GB RAM`, `GTX 1650` de 4 GB VRAM) y que actualmente tengo `qwen2.5:3b` (`~1.93 GB Q4_K_M`, 17.5 s en frío), ¿qué modelo cuantizado de Ollama en rango 3B–4B o 7B-IQ4 cabe completo en 4 GB VRAM sin desbordar a RAM compartida y da mejor español conversacional + JSON estricto que `qwen2.5:3b`?*
2. *Mi clave de Google AI Studio agotó a las 20 req/día el modelo `gemini-4-hydrogen` en Free Tier (`HTTP 429`). ¿Cómo comparo en `https://ai.dev/rate-limit` qué modelos Gemini actuales tienen mayor cuota RPD/RPM gratuita (o qué presupuesto mensual estimado en Tier 1 pagado tendría usando solo ~100–200 mensajes/día con contexto ~1.5k tokens)?*
3. *Para `Mandarino IA`, ¿conviene usar arquitectura **two-tier** donde Ollama local (o Gemini Flash-Lite) maneje saludos/seguimientos conversacionales sin el esquema JSON de calibración y un modelo más capaz se reserve únicamente cuando el usuario solicite diagnóstico profundo o ajuste de parámetros metrológicos?*
4. *¿Cómo debo estructurar el entrenamiento SFT a partir del dataset `.jsonl` que ya exporta AquaTerra Matrix para que un modelo ligero local (3B–4B) no alucine calibraciones ni hable en tercera persona?*
