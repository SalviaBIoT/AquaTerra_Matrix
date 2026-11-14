# Roadmap Etapa 2 — Futuras y Próximas Mejoras de AquaTerra Matrix

**Punto de Partida:** Checkpoint `v6.0.0` (Etapa 1 estabilizada)  
**Objetivo de la Etapa 2:** Pasar de consola de monitoreo y diagnóstico asistido a **telemetría bidireccional en campo, inferencia bioacústica/agronómica avanzada y copiloto con ejecución de herramientas y streaming.**

---

## 1. Hardware IoT, Radiofrecuencia y Campo (ESP32 / ESP32-S3)

1. **Canal Bidireccional hacia Actuadores (`Control -> Hardware`):**
   - Extender el gateway `nRF24L01+ PA+LNA` y el protocolo LoRa/MQTT para enviar comandos firmados (`abrir_valvula`, `duracion_seg`, `heartbeat`) validados por el `SafetyInterlockEngine`.
   - Confirmación física de retorno (*ACK de caudal / presión en línea*) para pasar el estado de bomba de `SIN_SENSOR_ACTUADOR` a telemetría real de flujo/corriente.
2. **Asistente de Calibración en Sitio de Sensores Capacitivos:**
   - Flujo guiado en UI (`Hardware IoT`) para capturar lectura ADC cruda en aire (`adc_seco`) y agua (`adc_agua`) en tiempo real desde puerto serial y versionar automáticamente la calibración con parámetros EMA ($\alpha$).
3. **Resiliencia Offline en Nodos & MicroSD:**
   - Cola circular local en LittleFS/MicroSD para ESP32/ESP32-S3 con reenvío ordenado por timestamp al reconectar al nodo maestro.

---

## 2. Ciencia Agronómica, Bioacústica y Conservación

1. **Módulo Bioacústico InBeersa (*Melipona eburnea*):**
   - Procesamiento de archivos WAV (I2S 32-bit @ 16 kHz) con extracción de espectrogramas, picos de frecuencia de zumbido (dB / Hz fundamentales) y clasificador ligero (TinyML o Python DSP) para detectar estrés térmico, orfandad o enjambrazón.
2. **Modelo Hídrico Dinámico FAO-56 + Lámina Neta (`CC / PMP`):**
   - Evolucionar el planificador hacia balance hídrico diario acumulativo descontando precipitación efectiva (Open-Meteo real + pluviómetro) y evapotranspiración del cultivo ($ET_c = K_c \cdot ET_0$).
3. **Motor Fitosanitario Sigatoka & Microclima de Páramo:**
   - Cálculo de horas acumuladas de mojado foliar y ventanas térmicas favorables para *Mycosphaerella fijiensis*, más alertas de heladas y balance térmico nocturno en *Polylepis*.

---

## 3. Mandarino IA Studio — Fase 2

1. **Streaming Real de Respuestas (`SSE` / `WebSocket`):**
   - Transmitir token por token desde FastAPI hacia React para que reportes largos aparezcan progresivamente en pantalla sin esperar a completar todo el JSON.
2. **Tool Calling Nativo sobre SQLite & Analítica:**
   - Permitir que Mandarino consulte herramientas bajo demanda (`get_series_historicas`, `calcular_correlacion_pearson`, `simular_riego`, `listar_pronostico_horas`) cuando el usuario pida cruces de varios días o semanas.
3. **Memoria de Largo Plazo y Bitácoras Exportables:**
   - Resúmenes automáticos por estación para mantener contexto histórico de meses sin inflar el tamaño del prompt, más exportación directa de conversaciones o reportes técnicos en Markdown/PDF y sincronización ágil con Notion.
4. **Entrada por Voz (Campo / Manos Ocupadas):**
   - Captura de audio desde el navegador/WebView (Web Speech / Whisper local) para dictar novedades o consultar estado de parcelas directamente en campo.

---

## 4. Ingeniería, Distribución y Operación Continua

1. **Integración Continua (GitHub Actions CI):**
   - Pipeline automático en `.github/workflows/ci.yml` que ejecute `ruff check .`, `pytest -m "not gui"`, `tsc --noEmit`, `oxlint` y `vite build` en cada push o Pull Request.
2. **Instalador Autónomo `.exe` / Portátil (`PyInstaller`):**
   - Consolidar `scripts/construir_exe.ps1` para empaquetar `Python + FastAPI + PyWebView + frontend/dist` en un ejecutable único listo para instalar en cualquier PC/MiniPC de finca sin configurar Python ni Node.js.
3. **Base de Datos de Pruebas / Modo Demo Público:**
   - Comando `python main.py --demo` con datos sintéticos agronómicos realistas para que cualquier persona que clone el repositorio desde GitHub pueda probar gráficos, candados y Mandarino en 10 segundos.
