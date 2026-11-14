# 📋 REP-006: Fase B5 — Orquestador IA en Cascada, Guardarraíles de Calibración, Rollback y Mejoras IoT (`v4.1.0`)

- **ID del Reporte:** `REP-006`
- **Fecha:** `2026-11-13`
- **Versión Alcanzada:** `v4.1.0` (Cierre completo del Plan de Backend B1–B5)
- **Rama:** `develop` $\to$ `main`
- **Autor y Arquitecto:** Daniel Felipe Duque Lizarralde

---

## 1. Resumen Ejecutivo

Con la **Fase B5** se completa al 100 % la arquitectura de Backend proyectada en [`ARQUITECTURA_MAESTRA_BRUJULA.md`](../ARQUITECTURA_MAESTRA_BRUJULA.md), coronando el sistema con:

1. **Guardarraíles Físicos y Agronómicos Anti-Alucinación (`aquaterra/core/copiloto/cotas_calibracion.py`):**
   - Catálogo estricto de 9 parámetros calibrables (`umbral_humedad_pct`, `capacidad_campo_pct`, `lamina_max_l_m2`, `adc_seco`, `adc_agua`, `ema_alpha`, `vpd_alerta_kpa`, `temp_nido_min_c`, `umbral_mojado_foliar_pct`).
   - Acotamiento en 3 etapas: rechazo de claves inventadas/no numéricas, límite de paso máximo por iteración (`±delta_max_por_paso`), recorte a cotas absolutas `[minimo, maximo]` y validación de invariantes cruzadas (`umbral_humedad_pct <= capacidad_campo_pct - 5%` y `adc_agua <= adc_seco - 400 cuentas`).
2. **Motor Determinista `AsesorDeterministaCopiloto` (`aquaterra/core/copiloto/asesor_reglas.py`):**
   - Sistema experto 100 % offline capaz de diagnosticar sobrerriego/escorrentía, déficit hídrico, deriva de sonda capacitiva ADC de 12 bits, ruido eléctrico en el filtro EMA (`ema_alpha`), termorregulación de colmenas *Melipona* (`InBeersa`) y riesgo fúngico de *Sigatoka*.
3. **Orquestador IA en Cascada (`aquaterra/infrastructure/ia/proveedores.py`):**
   - Conector moderno para **Google AI Studio** (`ClienteGeminiAIStudio`, modelo por defecto `gemini-4-hydrogen` sobre la API `Interactions` con `response_format` JSON Schema, usando `google-genai >= 3.2.0` o cliente REST `/v1beta/interactions`).
   - Conector para **Ollama Local** (`ClienteOllamaLocal` en `http://127.0.0.1:11434/api/chat` con ping rápido de disponibilidad).
   - Cascada automática resiliente: `Gemini AI Studio` $\to$ `Ollama Local` $\to$ `AsesorDeterministaCopiloto`.
4. **Servicio de Aplicación `CalibrationCopilotService` (`aquaterra/application/copiloto_servicio.py`):**
   - Construye automáticamente la fotografía matemática del nodo/parcela desde SQLite (`NodePulseService`, `DecisionAndControlService`, `RepositorioIncidenciaRiego`, `RepositorioCalibraciones`).
   - Persiste cada turno en `conversaciones_copiloto`, aplica recalibraciones en 1 clic (`aplicar_ajustes_interaccion`), ejecuta *rollback* no destructivo en 1 clic (`revertir_calibracion`) y exporta datasets `.jsonl` listos para *Supervised Fine-Tuning (SFT)* en Google AI Studio o Colab.
5. **Mejoras Complementarias de Infraestructura IoT:**
   - Re-anclaje temporal de sesiones con batería RTC agotada (`RepositorioLecturas.reparar_timestamps_rtc`), desplazando lecturas `calidad = 2` a la marca real de recolección en campo y promoviéndolas a `calidad = 1`.
   - Sincronización automática de `parcelas.humedad_pct` con la última lectura real de `suelo_a` al importar telemetría en `StationDiscoveryService`.

---

## 2. Archivos Creados y Modificados

| Archivo | Rol en la Arquitectura |
|---|---|
| `aquaterra/core/copiloto/cotas_calibracion.py` | Catálogo de cotas físicas, paso máximo por iteración e invariantes cruzadas (`auditar_y_acotar_ajustes`). |
| `aquaterra/core/copiloto/contratos_ia.py` | Contratos `ContextoDiagnosticoCopiloto`, `PropuestaCopiloto`, `ESQUEMA_JSON_RESPUESTA_COPILOTO` y prompts maestros. |
| `aquaterra/core/copiloto/asesor_reglas.py` | Sistema experto determinista offline (`AsesorDeterministaCopiloto`). |
| `aquaterra/core/copiloto/__init__.py` | Exportaciones públicas del dominio del Copiloto. |
| `aquaterra/infrastructure/ia/proveedores.py` | `ClienteGeminiAIStudio`, `ClienteOllamaLocal`, `ConfiguracionIA` y `OrquestadorIA`. |
| `aquaterra/infrastructure/ia/__init__.py` | Exportaciones públicas de infraestructura IA. |
| `aquaterra/application/copiloto_servicio.py` | `CalibrationCopilotService` (consulta, aplicación 1 clic, rollback 1 clic y exportador `.jsonl`). |
| `aquaterra/infrastructure/db/repositorios.py` | Método `RepositorioLecturas.reparar_timestamps_rtc()`. |
| `aquaterra/application/radar_servicio.py` | Método `StationDiscoveryService.sincronizar_humedad_parcelas()` integrado en la importación. |
| `aquaterra/application/contenedor.py` | Inyección de `self.copiloto = CalibrationCopilotService(self.conexion)`. |
| `tests/test_copiloto_y_calibracion.py` | 7 pruebas integrales cubriendo guardarraíles, cascada IA, rollback y mejoras IoT. |

---

## 3. Verificación y Calidad

- **Linter (`ruff check .`):** `All checks passed!` (`0` errores).
- **Suite de Pruebas (`pytest -v`):** **`78 passed in 16.44s`** (`0` fallos, `0` advertencias).
