# 📄 Reporte de Ingeniería `REP-007`: Sprint `v4.2.0` — Conectores Activos (Ubidots REST, Open-Meteo UTP Pereira, Gateway `nRF24L01+ PA+LNA`), Búsqueda Inteligente y Notificaciones (`n8n` / Telegram)

- **Identificador:** `REP-007`
- **Fecha:** `2026-11-13`
- **Versión del Sistema:** `v4.2.0` (Cierre 100% Backend Pre-Frontend)
- **Rama Git:** `develop` $\to$ `main`
- **Autor / Arquitecto:** Daniel Felipe Duque Lizarralde & Copiloto de Ingeniería

---

## 1. Resumen Ejecutivo

Con este sprint (`v4.2.0`) queda **100% completado, probado e integrado todo el Backend de `AquaTerra Matrix`**, listo para el despliegue del Frontend (`v5.0`) mañana por la mañana. Se construyeron e integraron los cinco músculos operativos externos del sistema manteniendo **cero dependencias pesadas adicionales** (100% `urllib.request` + `sqlite3` WAL + `threading` de la librería estándar):

1. **Cliente Incremental de Ubidots Industrial REST API (`aquaterra/infrastructure/iot_ingest/ubidots_client.py`):**
   - Descarga incremental por marca de agua (`?start={(ultimo_epoch + 1) * 1000}`) desde `https://industrial.api.ubidots.com/api/v1.6/devices/<device_label>/<variable_label>/values`.
   - Configurado con las etiquetas reales de las dos estaciones activas de Daniel en Ubidots:
     - **`terrabit-nodointi` (`ID: 6a5414b1fed41302f4e697cc`):** `suelo-a`, `suelo-b`, `temp-aire`, `hum-aire`, `temp-raiz`, `presion`, `vpd`, `voltaje` (normalizando guiones a `snake_case` y marcando `voltaje = -1` con `calidad = 2` para no disparar falsos bloqueos de batería cuando el divisor resistivo no está conectado).
     - **`inbeersa-nodo01` (`ID: 6af148b6396c6ec3eec10731`):** `temperatura_interna`, `humedad_interna`, `vpd_nido`, `actividad_pir`, `lluvia_evento`.
2. **Cliente Meteorológico Real Open-Meteo (`aquaterra/infrastructure/clima/open_meteo_client.py`):**
   - Configurado por defecto con las coordenadas oficiales del campus **UTP Pereira (`4.7905° N, -75.6904° O`, `1450 msnm`)**.
   - Alimenta la tabla `pronostico_clima_cache` con series horarias de `prob_lluvia_pct`, `precipitacion_mm`, `et0_mm` (FAO Penman-Monteith) y `temp_pronosticada_c`, activando en tiempo real el Candado #2 (lluvia inminente) del `SafetyInterlockEngine`.
3. **Receptor y Decodificador de Gateway Serial `nRF24L01+ PA+LNA` (2.4 GHz) y `LoRa` (`aquaterra/infrastructure/iot_ingest/serial_gateway.py`):**
   - Soporta tres dialectos de línea serial (`NRF24|<device>|<k=v,...>|<epoch>`, `TerraBit Frame v1` JSONL y JSON plano).
   - Optimizado para el límite de **32 bytes por paquete del transceptor `nRF24L01+ PA+LNA`**: calcula automáticamente en el servidor `vpd`, `vpd_nido` (Magnus-Tetens) y `delta_temp` cuando el nodo transmite únicamente temperaturas y humedades crudas.
4. **Despachador de Notificaciones Ejecutivas (`aquaterra/infrastructure/notificaciones/mensajeria.py`):**
   - Soporta doble canal sin librerías externas: **Webhook JSON hacia `n8n` / Make** (`AQUATERRA_WEBHOOK_URL`, ideal para enrutar a WhatsApp vía Evolution API / WhatsApp Cloud API, Telegram, Notion o Discord) y **API directa de Telegram Bot** (`AQUATERRA_TELEGRAM_BOT_TOKEN` + `AQUATERRA_TELEGRAM_CHAT_ID`).
5. **Refinamientos de IA Local y Experiencia Operativa (`proveedores.py`, `copiloto_servicio.py`, `sincronizacion_servicio.py`):**
   - **Precalentamiento asíncrono (`Warm-up`) de Ollama (`qwen2.5:3b`):** Carga el modelo en los 4 GB de VRAM de la GTX 1650 en un hilo `daemon` al iniciar la app (`keep_alive="10m"`), eliminando la espera de arranque en frío.
   - **Narrador Ejecutivo 24h (`narrar_pulso_24h`):** Sintetiza el `PulsoEstacion24h` en un boletín de 3 líneas listo para el encabezado del Dashboard o para enviarse por WhatsApp/Telegram.
   - **Barra de Búsqueda Inteligente (`buscar_inteligente_bitacora`):** Cruza en una sola consulta eventos de estación, auditoría de calibraciones IA y riegos históricos.
   - **Worker de Sincronización en Segundo Plano (`ActiveSyncAndGatewayService`):** Hilo `daemon` con su propia conexión SQLite WAL que sincroniza Ubidots y Open-Meteo periódicamente sin congelar la interfaz gráfica.

---

## 2. Módulos Creados y Actualizados

| Ruta | Rol Arquitectónico |
|---|---|
| [`aquaterra/infrastructure/iot_ingest/ubidots_client.py`](file:///C:/Users/danie/Developer/AquaTerra_Matrix/aquaterra/infrastructure/iot_ingest/ubidots_client.py) | Cliente REST incremental para Ubidots Industrial API (`X-Auth-Token`, filtro `start` en ms y mapeo por familia de estación). |
| [`aquaterra/infrastructure/clima/open_meteo_client.py`](file:///C:/Users/danie/Developer/AquaTerra_Matrix/aquaterra/infrastructure/clima/open_meteo_client.py) | Cliente REST para Open-Meteo API con coordenadas por defecto de UTP Pereira (`4.7905, -75.6904`, `1450 m`). |
| [`aquaterra/infrastructure/iot_ingest/serial_gateway.py`](file:///C:/Users/danie/Developer/AquaTerra_Matrix/aquaterra/infrastructure/iot_ingest/serial_gateway.py) | Decodificador multi-dialecto para tramas USB-Serial de receptor ESP32 con radio `nRF24L01+ PA+LNA` (2.4 GHz) o `LoRa`. |
| [`aquaterra/infrastructure/notificaciones/mensajeria.py`](file:///C:/Users/danie/Developer/AquaTerra_Matrix/aquaterra/infrastructure/notificaciones/mensajeria.py) | Despachador HTTP hacia Webhook `n8n` (WhatsApp/Telegram/Notion) y API nativa de Telegram Bot. |
| [`aquaterra/application/sincronizacion_servicio.py`](file:///C:/Users/danie/Developer/AquaTerra_Matrix/aquaterra/application/sincronizacion_servicio.py) | Servicio `ActiveSyncAndGatewayService` + worker `daemon` multi-hilo con conexión SQLite WAL aislada. |
| [`aquaterra/application/copiloto_servicio.py`](file:///C:/Users/danie/Developer/AquaTerra_Matrix/aquaterra/application/copiloto_servicio.py) | Nuevos métodos `narrar_pulso_24h()` y `buscar_inteligente_bitacora()`. |
| [`aquaterra/infrastructure/ia/proveedores.py`](file:///C:/Users/danie/Developer/AquaTerra_Matrix/aquaterra/infrastructure/ia/proveedores.py) | Métodos `ClienteOllamaLocal.precalentar()` y `OrquestadorIA.precalentar_ollama_async()`. |
| [`aquaterra/application/contenedor.py`](file:///C:/Users/danie/Developer/AquaTerra_Matrix/aquaterra/application/contenedor.py) | Exposición de `contenedor.sincronizacion` (`ActiveSyncAndGatewayService`) y cierre limpio del worker en `cerrar()`. |
| [`tests/test_conectores_activos_v42.py`](file:///C:/Users/danie/Developer/AquaTerra_Matrix/tests/test_conectores_activos_v42.py) | Suite de pruebas unitarias e integración para Gateway `nRF24L01+`, Ubidots incremental, Open-Meteo, búsqueda y notificaciones. |

---

## 3. Verificación y Suite de Pruebas (`82 passed`)

- **Linter Estático (`ruff check .`):** `All checks passed!` (0 errores, 0 advertencias).
- **Suite Automatizada (`pytest -q`):** **`82 passed`** (100% en verde, cubriendo desde `DT-01..05` hasta `Fases B1..B5` y `Sprint v4.2.0`).
