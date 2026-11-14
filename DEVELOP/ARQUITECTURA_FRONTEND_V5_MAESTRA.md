# 🏎️ Documento Maestro de Arquitectura Frontend `v5.0` — AquaTerra Matrix (Despliegue Híbrido *Local-First*)

- **Código de Documento:** `ARQUITECTURA_FRONTEND_V5_MAESTRA`
- **Versión del Sistema:** `v5.0.0` (Chasis de Interfaz sobre Backend `v4.2.0` 100% verificado)
- **Autor y Arquitecto:** Daniel Felipe Duque Lizarralde & Copiloto de Ingeniería
- **Fecha:** `2026-11-14`

---

## 1. Estrategia de Despliegue: Híbrido *Local-First* (Online + Offline Oportunista)

`AquaTerra Matrix` opera en escenarios donde la conectividad rural es intermitente (fincas cafeteras, viveros, meliponarios en bosque, páramos de *Polylepis*). Por ello, el sistema adopta una arquitectura **Híbrida *Local-First***:

| Modo Operativo | Capacidades Activas sin Interrupciones | Mecanismo Técnico |
|---|---|---|
| **Offline Estricto (Campo / Sin Internet)** | - Persistencia completa en `SQLite3 WAL` local.<br/>- Motor analítico (OLS, Pearson $r$, rumbo circular, Pulso 24h).<br/>- Enclavamientos duros de seguridad (5 candados) usando el último caché climático.<br/>- Recepción USB-Serial en vivo por antena **`nRF24L01+ PA+LNA`** (2.4 GHz).<br/>- Escaneo e importación de archivos **MicroSD** + reparación RTC.<br/>- Exportación ejecutiva `.xlsx` / `.csv` y Dataset `.jsonl`.<br/>- Copiloto IA vía **`Ollama` local (GPU GTX 1650 `qwen2.5:3b`)** o motor determinista **`local_reglas` (`< 1 ms`)**. | Cero llamadas bloqueantes en el hilo de UI; degradación limpia ante falta de red (`URLError`). |
| **Online Oportunista (Wi-Fi / 4G / Oficina)** | - Descarga incremental desde **Ubidots REST API** por marca de agua (`?start=`).<br/>- Descarga horaria real de pronóstico y ET0 FAO desde **Open-Meteo API**.<br/>- Copiloto con **Google Gemini AI Studio** (`gemini-4-hydrogen`) en PCs de bajos recursos.<br/>- Envío automático o manual de reportes 24h hacia **WhatsApp (`n8n` Webhook)** y **Telegram Bot**. | Worker `daemon` con conexión WAL propia (`intervalo=900s`) + botón **Sincronizar Ahora** bajo demanda. |

---

## 2. Arquitectura del *App Shell* Persistente (`v5.0`)

Reemplaza las ventanas sueltas de `v3.2` por un **Marco de Mando Unificado (*App Shell*)** sobre una **única ventana raíz `Tk` y un único `mainloop()` (regresión `DT-05a`)**:

```text
+---------------------------------------------------------------------------------------------------+
| 🧭 TOP COMMAND BAR                                                                                |
| [Estación Activa ▼]  [🔍 Buscar bitácora / Ctrl+K]  [☁️ Ubidots] [🌦️ Clima] [🧠 IA] [📻 Radio]   |
|                      [🔄 Sync]  [📲 Notificar 24h]  [📊 Excel .xlsx]  [☀️/🌙 Tema]               |
+-------------------+-------------------------------------------------------------------------------+
| 🗂️ SIDEBAR        | 🖥️ WORKSPACE CENTRAL (Monte dinámico de Vista 1..6 sin fugas DT-04)          |
|                   |                                                                               |
| 📡 1. Radar 24h   |   Vista activa renderizada sobre ttk.Frame independiente:                   |
| 📈 2. Telemetría  |   - Radar & Pulso 24h                                                         |
| 🌱 3. Parcelas    |   - Telemetría Multi-Nodo (Matplotlib OO adaptativo por TipoEstacion)         |
| 💧 4. Riego/Bomba |   - Riego, 5 Candados & Salud de Bomba                                        |
| 🧠 5. Copiloto IA |   - Copiloto IA & Calibración Auditada (1-clic Aplicar / Rollback)            |
| 📻 6. Radio & SD  |   - Radio nRF24L01+ PA+LNA & MicroSD                                          |
| ⚙️ 7. Config/User |   - Configuración de Conectores, Nodos GPS y Usuarios                         |
| ───────────────── |                                                                               |
| 👤 Usuario (Rol)  |                                                                               |
| 🔒 Cerrar Sesión  |                                                                               |
| ⏻  Salir Sistema  |                                                                               |
+-------------------+-------------------------------------------------------------------------------+
| 📟 STATUS FOOTER: SQLite WAL · Lecturas totales · Última Sync · Estado IA/Worker · v5.0.0         |
+---------------------------------------------------------------------------------------------------+
```

> **Nota de Compatibilidad y Trazabilidad:** Las rutas heredadas (`mostrar_dashboard`, `mostrar_parcelas`, `mostrar_riego`, `mostrar_monitor`, `cerrar_sesion`, `salir`) siguen funcionando exactamente sobre `app._vista`, asegurando que el **100% de las pruebas `DT-04` y `DT-05a`** continúen pasando sin excepciones.

---

## 3. Sistema de Diseño Dual (*Obsidian Bio-Tech* & *Field Daylight*)

Para responder tanto en laboratorio/oficina como bajo luz solar directa en campo, [`aquaterra/ui/tema.py`](file:///C:/Users/danie/Developer/AquaTerra_Matrix/aquaterra/ui/tema.py) registra dos `ThemeDefinition` nativos en `ttkbootstrap`:

1. **`aquaterra-dark` (*Obsidian Bio-Tech*, por defecto):**
   - Fondo principal `#0B0F14`, superficies/tarjetas `#131A22`, texto `#F1F5F9`, bordes `#263241`.
   - Semántica Bio-IoT: Verde TerraBit `#10B981` (`success`), Cian Hídrico `#06B6D4` (`info`), Azul Matriz `#3B82F6` (`primary`), Ámbar Polylepis `#F59E0B` (`warning`), Carmesí Interlock `#EF4444` (`danger`).
2. **`aquaterra-light` (*Field Daylight*, conmutable en 1 clic):**
   - Fondo `#F4F7F9`, superficies `#FFFFFF`, texto de alto contraste `#0F172A`, bordes `#CBD5E1`, preservando los acentos semánticos saturados para lectura al aire libre.

Toda gráfica `Matplotlib` se construye exclusivamente con la **API Orientada a Objetos (`Figure` + `FigureCanvasTkAgg`)**, estilizada automáticamente con la paleta activa y destruida explícitamente en `destroy()` (`0` figuras registradas en `pyplot.Gcf`).

---

## 4. Mapa Completo de Pantallas y Vínculo con el Backend

| Pantalla | Clase / Archivo | Responsabilidades Principales | Servicios `application` Conectados |
|---|---|---|---|
| **0. Acceso** | `VistaLogin` (`login_view.py`) | Autenticación PBKDF2-SHA256 (`600k`), cambio rápido de tema, botón Salir seguro. | `ServicioAutenticacion` |
| **1. Radar & Pulso 24h** | `VistaDashboard` (`dashboard_view.py`) | Narrativa ejecutiva IA 24h (`narrar_pulso_24h` en hilo no bloqueante), tarjetas priorizadas por severidad, KPIs de sensores en vivo, pronóstico horario Open-Meteo. | `StationDiscoveryService`, `NodePulseService`, `CalibrationCopilotService`, `ActiveSyncAndGatewayService` |
| **2. Telemetría Multi-Nodo** | `VistaMonitor` (`monitor_view.py`) | Gráficas adaptativas por familia (`TERRABIT_INTI`, `INBEERSA`, `SIGATOKA`, `CONSERVACION`) con ventanas (`6h`, `24h`, `7d`, `Todo`), comparativo de parcelas/consumo hídrico y exportación `.csv`. | `NodePulseService`, `ServicioMonitor`, `AnalyticsAndExportService` |
| **3. Parcelas & Cultivos** | `VistaParcelas` (`parcelas_view.py`) | CRUD validado (`DT-03`), archivado lógico (`DT-01`), vinculación a estación física, estado de humedad y riego automático. | `ServicioParcelas`, `StationDiscoveryService` |
| **4. Riego, Candados & Bomba** | `VistaRiego` (`riegos_view.py`) | Evaluación en vivo de los **5 Candados de Seguridad**, recomendación proactiva (`horas_hasta_estres`, $\Delta\theta/\Delta t$), registro de riego manual/programado, estado de bomba (`SIN_SENSOR_ACTUADOR` hoy / vibración-caudal futuro) e incidencia post-riego ($\Delta\theta_A / \Delta\theta_B$). | `DecisionAndControlService`, `ServicioRiego`, `ServicioParcelas` |
| **5. Copiloto IA & Calibración** | `VistaCopiloto` (`copiloto_view.py`) | Consulta técnica híbrida (`Gemini`/`Ollama`/`Reglas`), tarjeta *Diff* de parámetros auditados con cotas físicas, aplicar calibración en 1 clic, **Rollback** a versiones previas y exportador de dataset `.jsonl` (SFT). | `CalibrationCopilotService` |
| **6. Hardware `nRF24L01+` & MicroSD** | `VistaHardware` (`hardware_view.py`) | Descubrimiento de puertos `COM` (`pyserial`), lectura de gateway USB-Serial `nRF24L01+ PA+LNA`, simulador/inyector de tramas (`NRF24|...` y `TerraBit v1`), escáner de tarjetas MicroSD + importación en 1 clic y reparador de reloj RTC (`calidad=2`). | `ActiveSyncAndGatewayService`, `StationDiscoveryService` |
| **7. Configuración, Nodos & Usuarios** | `VistaConfiguracion` (`config_view.py`) | Alta de nuevas estaciones con GPS, configuración en caliente de Ubidots/Open-Meteo/IA (`Gemini`/`Ollama`/`Reglas`)/`n8n`/Telegram + guardado opcional en `.env` local, control del worker 2do plano, precalentamiento de GPU Ollama y administración de usuarios/roles. | `ActiveSyncAndGatewayService`, `ServicioAutenticacion` |

---

## 5. Controles Laterales, Seguridad por Roles y Ciclo de Cierre

- **Control de Roles en UI:**
  - `admin`: acceso completo a CRUD, riegos, calibración IA, configuración de conectores y alta de usuarios.
  - `operador`: consulta, sincronización, ingesta de campo (`nRF24L01+` / MicroSD), exportaciones y consultas al Copiloto IA; acciones destructivas/actuadores críticos resguardados en backend (`ErrorPermiso`).
  - `lector`: modo observador seguro.
- **Cierre Limpio de Sesión y Sistema:**
  - **Cerrar Sesión:** desmonta el *App Shell*, limpia el actor autenticado y vuelve a `VistaLogin` sin cerrar ni duplicar la ventana raíz.
  - **Salir del Sistema:** detiene el `daemon` de sincronización, ejecuta `PRAGMA wal_checkpoint(TRUNCATE);`, destruye lienzos `Matplotlib` y cierra la raíz limpia y determinísticamente.
