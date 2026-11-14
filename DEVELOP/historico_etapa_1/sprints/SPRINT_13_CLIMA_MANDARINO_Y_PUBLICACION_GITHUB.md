# Sprint 13 — Consciencia Meteorológica de Mandarino (Open-Meteo), Pulido Visual y Preparación Pública en GitHub

**Fecha:** 2026-11-14  
**Plataforma:** AquaTerra Matrix v6.0.0  
**Estado:** Completado, compilado y verificado en vivo (Backend + Frontend + Chrome Headless CDP + Open-Meteo + Google Gemini `gemini-3.5-flash-lite`).

---

## 1. Enlace Meteorológico Real (`Open-Meteo`) en Mandarino IA Studio

1. **Inyección Automática en `CalibrationCopilotService` (`aquaterra/application/copiloto_servicio.py`):**
   - Implementado `_construir_contexto_climatico()`: consulta `pronostico_clima_cache` en SQLite y, si está vacío en ejecución real, sincroniza automáticamente desde `ClienteOpenMeteo` para las coordenadas GPS de la estación activa (o nodo principal UTP Pereira en canal global).
   - Empaqueta lectura horaria actual (`ahora`: temperatura, humedad relativa, probabilidad/lámina de lluvia, viento y $ET_0$), `resumen_24h` (mínimas/máximas, acumulado de lluvia y $ET_0$ total) y bloque `proximas_horas` cada 3 horas.
   - Se enriqueció además `fecha_hora_local` (UTC-05:00), `parcelas_relacionadas` y `ultimas_variables` en `panorama_global_estaciones`.
2. **Contratos y Clasificación de Consultas (`aquaterra/core/copiloto/contratos_ia.py`):**
   - `es_consulta_ligera()` reconoce intención meteorológica (`clima`, `pronóstico`, `lluvia`, `viento`, `et0`, `temperatura`) para entregar contexto completo en modo `analisis_tecnico` e incluye resumen climático en `charla_ligera`.
   - `construir_system_instruction_terrabit()` instruye a Mandarino a cruzar Open-Meteo exterior con telemetría física de nodos ESP32/ESP32-S3 y nunca afirmar ausencia de datos climáticos cuando el bloque esté presente.
3. **Resincronización Bajo Demanda (`aquaterra/application/sincronizacion_servicio.py` & `aquaterra/api/routers/estaciones.py`):**
   - `/api/estaciones/{id}/pronostico` activa `auto_descargar=True` si la caché local de pronóstico está vacía.

---

## 2. Pulido de Respuestas y UX Conversacional

* **Supresión de relleno genérico:** En `aquaterra/infrastructure/ia/proveedores.py` (`parsear_respuesta_json_ia`) y `ChatBubble.tsx` se eliminó el texto automático `"Evaluación generada por modelo IA."` para mostrar la caja verde *Fundamento Agronómico* solo cuando existe justificación real.
* **Indicador meteorológico en cabecera (`CopilotPage.tsx`):** Píldora en vivo con temperatura exterior y probabilidad de lluvia (`Open-Meteo`) junto al estado del nodo.
* **Quick Reply `Clima y pronóstico 24h` (`ChatBubble.tsx`)** visible al pie de la última respuesta de Mandarino (con o sin alertas).
* **Sticky Date Header (`ChatMessageList.tsx`):** Margen inferior ajustado (`mb-2.5`) para evitar colisiones con el encabezado del primer mensaje cercano al tope del scroll.

---

## 3. Preparación del Repositorio Público en GitHub

* **Auditoría de `.gitignore`:**
  * Corregido `lib/` $\to$ `/lib/`, `lib64/` $\to$ `/lib64/` y `dist/` $\to$ `/dist/` + `frontend/dist/`, evitando que `frontend/src/lib/` (`api.ts`, `formatters.ts`) quedara ignorado por error al subir a GitHub.
  * Ampliado `data/runtime/*.db` $\to$ `data/runtime/` para excluir `aquaterra.db`, `-wal`, `-shm`, logs y `webview_profile/`.
* **Plantilla de entorno (`.env.example`):** Documenta todas las variables requeridas (`GEMINI_API_KEY`, `AQUATERRA_GEMINI_MODEL`, `AQUATERRA_OLLAMA_MODEL`, `UBIDOTS_TOKEN`, etc.) sin exponer claves reales.
* **Reorganización de `DEVELOP/`:** Todos los Sprints (`SPRINT_01..SPRINT_13`) consolidados en `DEVELOP/sprints/` y reportes del sistema en `DEVELOP/reportes/`, eliminando carpetas con espacios y actualizando `README.md` y `DEVELOP/README.md`.

---

## 4. Verificación Final Ejecutada

* `ruff check .`: `All checks passed!`
* `pytest -m "not gui" -ra`: **`95 passed, 4 deselected, 2 warnings in 28.55s`** (incluye `test_mandarino_inyecta_clima_open_meteo_y_evita_texto_generico`).
* Frontend: `npx.cmd tsc --noEmit` (0 errores), `npm.cmd run lint` (`0 errors`), `npm.cmd run build` (`✓ built in 4.47s`).
* Chrome Headless CDP (`cdp_sprint13_clima_mandarino.py`):
  * Cabecera meteorológica en vivo: `22.1 °C · 98% lluvia`.
  * Respuesta real de `gemini-3.5-flash-lite` usando datos exactos de `TerraBit-NodoINTI` (`lat: 4.7905, lon: -75.6904`), sin texto genérico (`hasGenericBoilerplate: false`, `EXCEPTIONS: 0`).
