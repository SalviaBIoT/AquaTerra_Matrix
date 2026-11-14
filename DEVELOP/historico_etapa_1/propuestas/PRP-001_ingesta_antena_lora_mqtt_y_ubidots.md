# PRP-001: Arquitectura de Ingesta en Vivo por Antena (LoRa / MQTT Local) y Sincronización Bidireccional con Ubidots

- **Código:** `PRP-001`
- **Versión Objetivo:** `v4.1.0` (Sincronización Ubidots + Importador UI) $\to$ `v5.0.0` (Gateway Antena RF)
- **Estado:** Propuesta Lista para Implementación (Adaptadores base ya creados en `aquaterra/infrastructure/iot_ingest/adaptadores.py`)
- **Autor:** Daniel Felipe Duque Lizarralde

---

## 1. Objetivo
Conectar el motor SQLite WAL y los parsers ya implementados en `v4.0.0a1` (`parsear_csv_nodo_inti`, `parsear_jsonl_inbeersa`, `parsear_payload_ubidots`) con tres canales de entrada operativos y una vista de telemetría en la interfaz gráfica:

1. **Canal 1 — Importación Local desde Archivo / HTTP de Estación (`v4.1.0`):**
   - Selector de archivo en la UI para importar `/data.csv` (MicroSD de **Nodo INTI**) o `/data.json` (MicroSD de **InBeersa**).
   - Descarga directa por HTTP desde el SoftAP de campo (`http://192.168.4.1/descargar-datos` o `http://inbeersa.local/descargar-datos`).
2. **Canal 2 — Sincronizador Ubidots Industrial (`v4.1.0`):**
   - **Pull Incremental REST:** Consulta `GET https://industrial.api.ubidots.com/api/v1.6/devices/<codigo>/<variable>/values?start=<ultimo_epoch * 1000>` usando `RepositorioLecturas.ultimo_epoch(estacion_id)`. Descarga únicamente las muestras nuevas ocurridas mientras el PC estuvo apagado.
   - **Stream MQTT en Vivo:** Cliente `paho-mqtt` en hilo daemon suscrito a `/v1.6/devices/+` que inserta cada paquete entrante en SQLite en tiempo real.
3. **Canal 3 — Recepción Directa por Antena en Estación Base (`v5.0.0`):**
   - **Gateway Serial (LoRa 915 MHz / ESP-NOW LR):** Un receptor ESP32 con antena exterior conectado por USB al servidor local entrega cada trama recibida como una línea JSON por puerto serial (`pyserial` a `115200 bps`).
   - **Broker MQTT Local (Mosquitto):** Para enlaces con antena WiFi exterior de largo alcance (CPE 2.4 GHz), los nodos publican al broker local en la LAN y un servicio `Store & Forward` de **AquaTerra Matrix** replica los datos hacia Ubidots cuando hay conexión a Internet.

---

## 2. Garantía de Cero Duplicados
Como la tabla `lecturas_sensor` ya posee la restricción `UNIQUE (estacion_id, variable, ts_epoch)` y `RepositorioLecturas.insertar_lote()` utiliza `INSERT OR IGNORE`, un operador puede:
1. Recibir datos en vivo por Ubidots o por antena, y
2. Semanas después insertar la tarjeta MicroSD de la estación para recuperar los huecos de cuando se cayó el WiFi,
y **SQLite insertará únicamente las muestras faltantes**, sin duplicar un solo punto.
