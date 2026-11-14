# 📄 Reporte de Ingeniería `REP-008`: Sprint `v5.0.0` — Frontend *App Shell* Híbrido *Local-First*, 7 Vistas Operativas y Consolidación del Sistema

- **Identificador:** `REP-008`
- **Fecha:** `2026-11-14`
- **Versión del Sistema:** `v5.0.0` (Cierre Completo Backend + Frontend + Documentación Maestra)
- **Rama Git:** `develop` $\to$ `main`
- **Autor y Arquitecto:** Daniel Felipe Duque Lizarralde & Copiloto de Ingeniería

---

## 1. Resumen Ejecutivo

Con este sprint (`v5.0.0`) se completa la **primera versión integral de producto de `AquaTerra Matrix`**, unificando la ingeniería del Backend (`v4.2.0`) con una consola de escritorio de grado comercial bajo estrategia **Híbrida *Local-First*** (100% operativa sin internet mediante `SQLite3 WAL`, antena USB-Serial `nRF24L01+ PA+LNA`, MicroSD y Ollama/Reglas locales; sincronización oportunista con Ubidots REST API, Open-Meteo, Gemini Cloud y WhatsApp/Telegram vía `n8n` cuando hay red).

Los pilares entregados en este sprint son:

1. **Documento Maestro Consolidado de Frontend (`DEVELOP/ARQUITECTURA_FRONTEND_V5_MAESTRA.md`):**
   - Análisis comparativo Nube vs. Local vs. Híbrido *Local-First*, diagramas estructurales del *App Shell* y mapa completo de vistas y controles de sesión.
2. **Sistema de Diseño Dual (`aquaterra/ui/tema.py`):**
   - Registro nativo en `ttkbootstrap` 2.x de dos temas personalizados:
     - **`aquaterra-dark` (*Obsidian Bio-Tech*):** fondo `#0b0f14`, superficies `#131a22`, verde TerraBit `#10b981`, cian hídrico `#06b6d4`, ámbar `#f59e0b` y carmesí `#ef4444`.
     - **`aquaterra-light` (*Field Daylight*):** paleta de alto contraste `#f4f7f9` / `#ffffff` diseñada para visibilidad bajo sol directo en campo.
   - Estilizador unificado para figuras `Matplotlib` orientadas a objetos (`estilizar_figura`).
3. ***App Shell* Persistente sobre Ventana Única (`aquaterra/ui/shell.py` + `aquaterra/ui/app.py`):**
   - **`Top Command Bar`:** selector global de estación activa, barra de búsqueda inteligente (`Ctrl+K`) conectada a `buscar_inteligente_bitacora()`, píldoras en vivo (`Ubidots`, `Clima`, `IA`, `Radio`) y acciones rápidas en hilos no bloqueantes (`Sync Híbrido`, `Notificar 24h`, `Exportar .xlsx`, `Conmutar Tema`).
   - **`Sidebar` Lateral Fijo:** identidad TerraBit, navegación de las 7 secciones operativas con badge de estaciones críticas, tarjeta de usuario/rol y pie fijo con **`Cerrar Sesión`** (vuelve al Login en la misma raíz `DT-05a`) y **`Salir del Sistema`** (detiene el worker y consolida el WAL de SQLite).
   - **`Status Footer`:** estado SQLite3 WAL, conteo total de lecturas, estado del worker y marca temporal de última sincronización.
4. **Suite Completa de Vistas (`aquaterra/ui/views/`):**
   - **Acceso (`login_view.py`):** autenticación PBKDF2-SHA256 con selector rápido de tema y salida segura.
   - **1. Radar & Pulso 24h (`dashboard_view.py`):** narrativa ejecutiva IA asíncrona, tarjetas KPI, radar priorizado por severidad, tabla de variables 24h y pronóstico horario Open-Meteo en caché.
   - **2. Telemetría Multi-Nodo (`monitor_view.py`):** gráficas adaptativas según `TipoEstacion` (`TERRABIT_INTI`, `INBEERSA`, `SIGATOKA`, `CONSERVACION`), ventanas (`6h`, `24h`, `7d`, `Todo`), comparativo de parcelas/consumo, correlación bivariada de Pearson $r$ y exportación `.csv`, con liberación estricta de lienzos (`DT-04`).
   - **3. Parcelas & Cultivos (`parcelas_view.py`):** CRUD validado (`DT-03`), archivado lógico (`DT-01`) y vinculación a estación IoT física.
   - **4. Control, 5 Candados & Bomba (`riegos_view.py`):** riego manual/programado, semáforo en vivo de los 5 candados de `SafetyInterlockEngine`, recomendación proactiva (`horas_hasta_estres`, $\Delta\theta/\Delta t$), estado de bomba (`SIN_SENSOR_ACTUADOR` hoy / sensores a futuro) e incidencia post-riego ($\Delta\theta_A / \Delta\theta_B$).
   - **5. Copiloto IA & Calibración (`copiloto_view.py`):** consulta híbrida asíncrona, tabla *Diff* auditada contra cotas físicas, aplicar calibración en 1 clic, **Rollback** y exportador de dataset `.jsonl` (SFT).
   - **6. Hardware `nRF24L01+` & MicroSD (`hardware_view.py`):** auto-descubrimiento de puertos `COM` (`pyserial`), lectura serial e inyector/decodificador de tramas compactas, escáner de archivos MicroSD, importador en 1 clic y reparador de reloj RTC (`calidad=2`).
   - **7. Conectores, Nodos & Usuarios (`config_view.py`):** configuración gráfica en caliente para clientes finales (`UBIDOTS_TOKEN`, proveedor/modelo IA, `n8n` Webhook, Telegram Bot) con guardado opcional en `.env` local (ignorado por Git), precalentamiento GPU Ollama, toggle del worker en segundo plano, alta de nodos GPS y administración de cuentas/roles.
5. **Endurecimiento del Despliegue Híbrido y Carga `.env` (`config.py`, `servicios.py`, `sincronizacion_servicio.py`, `pulso_servicio.py`, `radar_servicio.py`, `control_servicio.py`):**
   - `sincronizar_todo_hibrido()` degrada limpiamente ante caídas de red (`online=False`) sin interrumpir la operación de campo.
   - La capa UI se comunica exclusivamente con `application` (respetando la arquitectura en 4 capas sin SQL directo en vistas).

---

## 2. Archivos Creados y Modificados en `v5.0.0`

| Archivo | Cambio Principal |
|---|---|
| [`DEVELOP/ARQUITECTURA_FRONTEND_V5_MAESTRA.md`](../ARQUITECTURA_FRONTEND_V5_MAESTRA.md) | Documento maestro consolidado del diseño UX, modo híbrido y App Shell. |
| [`aquaterra/ui/tema.py`](../../aquaterra/ui/tema.py) | Temas `aquaterra-dark` / `aquaterra-light`, paleta Matplotlib y tarjetas KPI. |
| [`aquaterra/ui/shell.py`](../../aquaterra/ui/shell.py) | `AppShell` persistente (Top Bar, Búsqueda `Ctrl+K`, Píldoras, Sidebar, Footer). |
| [`aquaterra/ui/app.py`](../../aquaterra/ui/app.py) | Controlador de ventana única `AplicacionMatrix` integrado con `AppShell` y tema dual. |
| [`aquaterra/ui/views/`](../../aquaterra/ui/views) | Renovación de `login_view`, `dashboard_view`, `monitor_view`, `parcelas_view`, `riegos_view` + nuevas `copiloto_view`, `hardware_view`, `config_view`. |
| [`aquaterra/config.py`](../../aquaterra/config.py) | Tema por defecto `aquaterra-dark` y carga/guardado seguro de `.env` local. |
| [`aquaterra/application/`](../../aquaterra/application) | Helpers de consulta/operación híbrida, serial `COM`, usuarios y conectividad en vivo. |
| [`tests/test_frontend_v50_y_hibrido.py`](../../tests/test_frontend_v50_y_hibrido.py) | Pruebas de degradación offline, conectores `.env`, usuarios/nodos y App Shell completo. |

---

## 3. Verificación Automatizada

- **Linter Estático (`ruff check .`):** `All checks passed!` (0 errores).
- **Suite Completa (`pytest`):** **86 pruebas en verde (`86 passed`, 0 fallos, 0 saltadas)** incluyendo todas las pruebas de humo GUI (`DT-04` sin fugas Matplotlib, `DT-05a` raíz única y recorrido completo del App Shell + tema dual).
