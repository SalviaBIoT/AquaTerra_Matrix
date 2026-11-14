# REP-002: Fase B1 — Esquema SQLite v2, Repositorios de Control y Calibración e Ingesta Universal de 4 Familias

- **Fecha:** `2026-11-13`
- **Versión:** `v4.1.0a1`
- **Rama:** `develop`
- **Autor:** Daniel Felipe Duque Lizarralde

---

## 1. Resumen Ejecutivo

Se ejecutó completamente la **Fase B1** definida en la [Brújula Maestra de Arquitectura (`ARQUITECTURA_MAESTRA_BRUJULA.md`)](../ARQUITECTURA_MAESTRA_BRUJULA.md), evolucionando la base de datos de **AquaTerra Matrix** al **Esquema SQLite v2 (`_MIGRACION_002`)** con 7 tablas nuevas para eventos discretos no escalares, calibraciones versionadas con *rollback*, verificación hidromecánica de motobombas, evaluación post-riego, cola de riegos programados, caché de pronóstico meteorológico y trazabilidad del copiloto. Simultáneamente, se amplió la capa de ingesta IoT para cubrir las **4 familias reales de hardware del Ecosistema TerraBit** (`Nodo INTI`, `InBeersa`, `Sigatoka` y `Conservación Polylepis/Páramos`), integrando cálculo automático de $VPD$ y $\Delta T$ y una guardia física contra relojes RTC no inicializados.

---

## 2. Mapeo de Cambios por Capa

| Capa / Archivo | Cambio Implementado | Justificación Técnica / Agronómica |
|---|---|---|
| `aquaterra/__init__.py` | Incremento de `__version__` a `"4.1.0a1"`. | Marca el primer hito incremental del Backend v4.1 sobre la base `v4.0.0a1`. |
| `aquaterra/core/domain/entidades.py`<br/>`aquaterra/core/domain/__init__.py` | Incorporación de 4 `StrEnum` (`ModoVerificacionRiego`, `DiagnosticoMecanicoBomba`, `EfectividadRiego`, `EstadoRiegoProgramado`) y 7 `dataclass(frozen=True, slots=True)` (`EventoEstacion`, `VersionCalibracion`, `RegistroSaludActuador`, `IncidenciaRiego`, `RiegoProgramado`, `PuntoPronosticoClima`, `InteraccionCopiloto`). | Contratos puros e inmutables en dominio (cero I/O) para soportar trazabilidad mecánica, agronómica y conversacional. |
| `aquaterra/infrastructure/db/esquema.py` | Adición de `_MIGRACION_002`, `MIGRACIONES = (_MIGRACION_001, _MIGRACION_002)` y `VERSION_ESQUEMA = 2`. | Evoluciona de forma incremental y transaccional cualquier base SQLite `v1` a `v2` vía `PRAGMA user_version`. |
| `aquaterra/infrastructure/db/repositorios.py` | Adición de 7 repositorios (`RepositorioEventosEstacion`, `RepositorioCalibraciones`, `RepositorioSaludActuadores`, `RepositorioIncidenciaRiego`, `RepositorioRiegosProgramados`, `RepositorioPronosticoClima`, `RepositorioCopiloto`). | Persistencia desacoplada con consultas parametrizadas, upsert idempotente de pronósticos y *rollback* en 1 paso de calibraciones. |
| `aquaterra/infrastructure/iot_ingest/adaptadores.py`<br/>`aquaterra/infrastructure/iot_ingest/__init__.py` | Implementación de `parsear_csv_sigatoka()`, `parsear_csv_conservacion()`, extensión de `Nodo INTI` e `InBeersa`, cálculo automático de $VPD$ y $\Delta T$, y guardia `EPOCH_MINIMO_VALIDO`. | Cubre el 100% de las variables reales emitidas por los firmwares C++17 (incluyendo buffer sin cabecera de Sigatoka y vibración de bomba). |
| `tests/test_esquema_v2_y_repositorios.py`<br/>`tests/test_iot_ingest.py` | 5 nuevas pruebas unitarias de esquema `v2`/repositorios y ampliación a 7 pruebas de ingesta para las 4 familias. | Verificación reproducible de migración `v1 -> v2`, *rollback* de calibración, interlocks, Sigatoka CSV/buffer y guardia RTC. |

---

## 3. Detalle Técnico Implementado

### 3.1. Esquema Relacional SQLite `v2` (`_MIGRACION_002`)

Sobre las 6 tablas base de `v1`, se incorporaron 7 tablas con restricciones `FOREIGN KEY`, `CHECK` e índices compuestos:

1. **`eventos_estacion`** (+ `ix_eventos_estacion_ts`): Almacena eventos discretos y categóricos (`estacion_id`, `tipo_evento`, `valor_texto`, `archivo_ruta`, `metadatos_json`, `ts_epoch`, `ts_iso`) con unicidad `(estacion_id, tipo_evento, ts_epoch)`. Registra etiquetas cardinales de viento de Sigatoka (`N`, `NE`, ...) y prepara el anclaje de audios `.wav` / capturas `.jpg`.
2. **`calibraciones_nodo`** (+ `ix_calibraciones_destino`): Versionado secuencial (`version >= 1`) por estación y/o parcela (`CHECK (estacion_id IS NOT NULL OR parcela_id IS NOT NULL)`). `RepositorioCalibraciones.guardar_nueva_version()` desactiva versiones previas (`activa = 0`) y `restaurar_version()` crea una nueva versión activa copiando parámetros previos (*rollback* no destructivo). Usa `IS ?` en SQL para comparar correctamente `NULL`.
3. **`salud_actuadores_log`**: Registra telemetría hidromecánica asociada `UNIQUE` a `eventos_riego`: `modo_verificacion`, `vibracion_rms_g`, `vibracion_freq_hz`, `corriente_a`, `caudal_lpm`, `apertura_max_pct` y `diagnostico_mecanico`.
4. **`incidencia_riego`**: Evalúa la respuesta real del suelo tras el riego (`humedad_a_antes/despues`, `humedad_b_antes/despues`) calculando `delta_a_pct`, `delta_b_pct` y su clasificación (`efectivo`, `infiltracion_parcial`, `exceso_percolacion`, `sin_respuesta_en_suelo`).
5. **`riegos_programados`** (+ `ix_riegos_prog_parcela_estado`): Cola de riegos futuros (`pendiente`, `ejecutado`, `bloqueado_interlock`, `cancelado`) con `apertura_max_pct` y `motivo_bloqueo`.
6. **`pronostico_clima_cache`** (+ `ix_pronostico_estacion_ts`): Caché *Offline-First* con `INSERT OR REPLACE` sobre `UNIQUE (estacion_id, ts_objetivo_epoch)` (`temp_c`, `hum_relativa_pct`, `lluvia_prob_pct`, `lluvia_mm`, `viento_ms`, `et0_mm`).
7. **`conversaciones_copiloto`**: Trazabilidad de consultas del usuario, diagnóstico IA, JSON de `ajustes_propuestos_json`, proveedor de IA y vínculo `calibracion_aplicada_id`.

### 3.2. Ingesta IoT Universal y Guardia Temporal (`adaptadores.py`)

- **Guardia de Sanidad Temporal (`EPOCH_MINIMO_VALIDO = 1_704_067_200` — `2024-01-01T00:00:00Z`):** Cualquier lectura con timestamp RTC sin inicializar (ej. año `2000`) o fuera de rango físico se etiqueta con `calidad = 2` mediante `_calidad_con_tiempo()`, quedando excluida automáticamente de `RepositorioLecturas.serie()`.
- **Sigatoka (`parsear_csv_sigatoka`):** Detecta automáticamente si el origen posee cabecera (`/MUNDONUEVO.csv`) o carece de cabecera (`/buffer_sigatoka.json` usando `_CABECERA_SIGATOKA`). Genera `LecturaSensor` numéricas, deriva `hoja_humectada` (umbral `>= 70.0 %` conforme a `sigatok_config.h`), convierte la rosa de vientos cardinal a acimut en grados (`direccion_viento_grados`), calcula `vpd` por Tetens FAO-56 y emite `EventoEstacion(tipo_evento="direccion_viento")`.
- **TerraBit Nodo INTI (`parsear_csv_nodo_inti`):** Incorpora columnas opcionales hidromecánicas (`VibracionRMS`, `VibracionFreq`, `CorrienteBomba`, `CaudalLPM`, `AperturaValvula`) y calcula `vpd` automáticamente si falta en la trama CSV.
- **InBeersa (`parsear_jsonl_inbeersa`):** Soporta tanto las claves del `/data.json` (`TempI`, `HumedadI`, `PIR`, `Lluvia`) como los campos del struct `TelemetriaInBeersa` en firmware (`tempInterna`, `humInterna`, `tempExterna`, `humExterna`, `pirDetectado`, `eventosPIRTotal`, `llovio`, `cAire`, `uptimeSeg`) y calcula `delta_temp = TempI - TempE` cuando ambos están presentes.
- **Conservación & Páramos (`parsear_csv_conservacion`):** Normaliza variables hidro-ecológicas de alta montaña (`nivel_freatico_cm`, `humedad_turba_a`, `humedad_turba_b`, `radiacion_solar_wm2`, `temp_suelo_paramo`) y microclima con cálculo automático de `vpd`.

---

## 4. Pruebas y Verificación

- **Suite `pytest -v`:** `57 passed in 14.30s` (`0` fallos, `0 warnings`). Incluye las 5 pruebas de `tests/test_esquema_v2_y_repositorios.py` y las 7 pruebas de `tests/test_iot_ingest.py`.
- **Linter `ruff check .`:** `All checks passed!` (`0` advertencias o errores).
- **Documentos de referencia:** [ARQUITECTURA_MAESTRA_BRUJULA.md](../ARQUITECTURA_MAESTRA_BRUJULA.md) · [ADR-001](../decisiones/ADR-001_sqlite_wal_y_retiro_pandas_runtime.md) · [ADR-004](../decisiones/ADR-004_estandar_temporal_iso8601_y_epoch.md).

---

## 5. Próximo Paso de Ingeniería

Ejecutar la **Fase B2**: construir el motor analítico de series temporales en `aquaterra/core/analitica/` (ventanas móviles, tasa de secado edáfico $\Delta\theta/\Delta t$, correlación bivariada y resumen 24 h adaptado a cada `TipoEstacion`) junto con `NodePulseService` en `aquaterra/application/`.
