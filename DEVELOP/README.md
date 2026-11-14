# 🧭 Centro de Trazabilidad de Ingeniería (`DEVELOP/`) — AquaTerra Matrix

**Proyecto:** AquaTerra Matrix — Ecosistema TerraBit (Nodo INTI · InBeersa · Sigatoka · Conservación Polylepis)  
**Autor y Arquitecto:** Daniel Felipe Duque Lizarralde  
**Rama de Ingeniería Activa:** `develop`  

---

> 🧭 **Documento Rector del Sistema (`v4.0` $\to$ `v5.0 Final`):** **[`ARQUITECTURA_MAESTRA_BRUJULA.md`](ARQUITECTURA_MAESTRA_BRUJULA.md)** — Contiene el catálogo completo de variables de todas las familias de estaciones (`Nodo INTI`, `InBeersa`, `Sigatoka`, `Conservación Polylepis`), la auditoría forense de 8 modos de fallo y el plan de ejecución del Backend (`Fases B1 -> B5`).

## 1. Propósito de este Directorio
Esta carpeta (`DEVELOP/`) es la **bitácora viva de arquitectura, mejoras, decisiones técnicas y propuestas** de **AquaTerra Matrix**. Cada avance, refactorización o nuevo módulo queda registrado con trazabilidad completa hacia el código fuente y las pruebas automatizadas (`tests/`).

```text
DEVELOP/
├── README.md                                                    # Este índice maestro de trazabilidad
├── ARQUITECTURA_MAESTRA_BRUJULA.md                              # Brújula Maestra v4.0 -> v5.0 (Variables, Riesgos y Backend)
├── GUIA_INTEGRACION_IA_AISTUDIO_Y_OLLAMA.md                     # Manual 0 a 100 para conectar Gemini AI Studio y Ollama Local
├── reportes/                                                    # Reportes paso a paso de cada fase ejecutada
│   ├── REP-000_migracion_semilla_y_entorno.md                   # Fase 0: Semilla v3.2, Git, .venv y diagnóstico
│   ├── REP-001_arquitectura_v4_y_resolucion_deuda_tecnica.md    # Fase 1: Arquitectura 4 capas, SQLite WAL y DT-01..05
│   ├── REP-002_fase_b1_esquema_v2_e_ingesta_universal.md        # Fase B1: Esquema v2 (7 tablas) e ingesta 4 familias
│   ├── REP-003_fase_b2_motor_analitico_ventana_movil_y_pulso_24h.md # Fase B2: Analítica, ventana móvil SQLite y Pulso 24h
│   ├── REP-004_fase_b3_enclavamientos_salud_bomba_e_incidencia_riego.md # Fase B3: 5 candados, salud bomba e incidencia riego
│   ├── REP-005_fase_b4_exportador_xlsx_y_radar_estaciones.md    # Fase B4: Exportador .xlsx multi-hoja y Radar de Nodos
│   └── REP-006_fase_b5_orquestador_ia_y_copiloto_calibracion.md # Fase B5: Orquestador IA híbrido, Copiloto, Rollback y RTC
├── decisiones/                                                  # Architecture Decision Records (ADRs)
│   ├── ADR-001_sqlite_wal_y_retiro_pandas_runtime.md            # Motor SQLite3 WAL y esquema relacional
│   ├── ADR-002_arquitectura_capas_y_contenedor.md               # Separación Core / Application / Infra / UI
│   ├── ADR-003_seguridad_pbkdf2_y_auditoria.md                  # Hashing PBKDF2-SHA256 (600k iter) y tabla auditoria
│   └── ADR-004_estandar_temporal_iso8601_y_epoch.md             # Dualidad ISO-8601 (-05:00) + Unix Epoch
├── propuestas/                                                  # Especificaciones técnicas para las siguientes fases
│   ├── PRP-001_ingesta_antena_lora_mqtt_y_ubidots.md            # Fase 2 (v5.0): Telemetría RF Local + Sync Ubidots
│   └── PRP-002_modelo_agronomico_riego_vpd_y_suelo.md           # Fase 2 (v5.0): Riego por CC/PMP y VPD real
└── plantillas/                                                  # Plantillas oficiales para nuevos documentos
    ├── PLANTILLA_REPORTE.md
    └── PLANTILLA_PROPUESTA.md
```

---

## 2. Matriz de Trazabilidad de Deuda Técnica (AquaUTP v3.2 $\to$ AquaTerra Matrix v4.0)

| Código | Hallazgo en v3.2 | Estado | Módulo que lo Resuelve | Prueba de Regresión | Reporte / ADR |
|---|---|---|---|---|---|
| **DT-01** | `eliminar_parcela()` renumeraba los IDs (`1..N`), rompiendo la relación con `riegos.json`. | ✅ **Resuelto** | `aquaterra/infrastructure/db/esquema.py`<br/>`aquaterra/application/servicios.py` (`archivar`) | `tests/test_servicios.py::test_regresion_dt01_archivar_no_renumera_ni_rompe_riegos` | `REP-001` / `ADR-001` |
| **DT-02** | Persistencia en CSV/JSON planos reescritos por completo en cada cambio; fechas ambiguas `MM/DD/YY`. | ✅ **Resuelto** | `aquaterra/infrastructure/db/` (SQLite WAL)<br/>`aquaterra/core/tiempo.py` (ISO-8601 + Epoch) | `tests/test_migrador_v32.py`<br/>`tests/test_tiempo.py`<br/>`tests/test_iot_ingest.py` | `REP-001` / `ADR-001` / `ADR-004` |
| **DT-03** | `_accion_actualizar()` en `parcelas_ui.py` carecía de validación numérica y de campos vacíos. | ✅ **Resuelto** | `aquaterra/core/domain/validadores.py`<br/>`aquaterra/application/servicios.py` | `tests/test_validadores.py::test_regresion_dt03_actualizar_con_area_no_numerica` | `REP-001` / `ADR-002` |
| **DT-04** | Fuga de memoria en `monitor_ui.py` por uso de `plt.subplots()` global sin liberar figuras al cerrar. | ✅ **Resuelto** | `aquaterra/ui/views/monitor_view.py` (`Figure` OO + `destroy()`) | `tests/test_ui_smoke.py::test_regresion_dt04_monitor_no_fuga_figuras` | `REP-001` |
| **DT-05a** | Doble `mainloop()` (`VentanaLogin` + `Toplevel` en `VentanaDashboard`) y cierre forzoso al cerrar sesión. | ✅ **Resuelto** | `aquaterra/ui/app.py` (`AplicacionMatrix` con raíz única y montaje de `ttk.Frame`) | `tests/test_ui_smoke.py::test_flujo_completo_una_sola_raiz` | `REP-001` / `ADR-002` |
| **DT-05b** | Contraseñas almacenadas en texto plano (`"pass": "1234"`) en `usuarios.json`. | ✅ **Resuelto** | `aquaterra/infrastructure/seguridad/hashing.py` (`PBKDF2-HMAC-SHA256`, 600k iter + salt) | `tests/test_seguridad.py`<br/>`tests/test_migrador_v32.py` | `REP-001` / `ADR-003` |

---

## 3. Historial de Reportes de Ingeniería

| ID | Fecha | Versión | Título | Resumen Ejecutivo |
|---|---|---|---|---|
| **[REP-000](reportes/REP-000_migracion_semilla_y_entorno.md)** | `2026-11-12` | `v3.2.0-legacy` | Migración de Semilla, Aislamiento `.venv` y Línea Base Git | Traslado a `C:\Users\danie\Developer\AquaTerra_Matrix`, preservación en `legacy/aquautp_v3.2`, tag `v3.2.0-legacy` y auditoría forense. |
| **[REP-001](reportes/REP-001_arquitectura_v4_y_resolucion_deuda_tecnica.md)** | `2026-11-13` | `v4.0.0a1` | Re-Arquitectura por Capas, Motor SQLite WAL, Ingesta IoT y Cierre de Deuda Técnica | Implementación del paquete `aquaterra/`, erradicación de `DT-01..05`, migrador automático v3.2 $\to$ SQLite, parsers para Nodo INTI / InBeersa / Ubidots y suite de 47 pruebas automatizadas. |
| **[REP-002](reportes/REP-002_fase_b1_esquema_v2_e_ingesta_universal.md)** | `2026-11-13` | `v4.1.0a1` | Fase B1 — Esquema SQLite v2, Repositorios de Control e Ingesta Universal | Evolución de SQLite (`_MIGRACION_002`: 7 tablas nuevas de eventos, calibración versionada, actuadores, riegos programados, clima y copiloto), ingesta nativa de Sigatoka (CSV/buffer), Conservación/Páramos, guardia RTC y suite de 57 pruebas en verde. |
| **[REP-003](reportes/REP-003_fase_b2_motor_analitico_ventana_movil_y_pulso_24h.md)** | `2026-11-13` | `v4.1.0a2` | Fase B2 — Motor Analítico, Ventana Móvil SQLite y Pulso 24h | Implementación de `aquaterra/core/analitica/` (ventana móvil, tasa de secado OLS $\Delta\theta/\Delta t$, correlación de Pearson $r$, rumbo circular $\operatorname{atan2}$ y Pulso 24h para las 4 familias), Window Functions SQLite3, `NodePulseService` y suite de 64 pruebas en verde. |
| **[REP-004](reportes/REP-004_fase_b3_enclavamientos_salud_bomba_e_incidencia_riego.md)** | `2026-11-13` | `v4.1.0a3` | Fase B3 — Enclavamientos Duros, Salud de Bomba e Incidencia de Riego | Implementación modular de `aquaterra/core/control/` (`SafetyInterlockEngine` de 5 candados, clasificador de bomba con modo `SIN_SENSOR_ACTUADOR` hoy y vibración/caudal a futuro, evaluador $\Delta\theta_A/\Delta\theta_B$ y planificador proactivo), `DecisionAndControlService` y suite de 68 pruebas en verde. |
| **[REP-005](reportes/REP-005_fase_b4_exportador_xlsx_y_radar_estaciones.md)** | `2026-11-13` | `v4.1.0a4` | Fase B4 — Exportador Ejecutivo `.xlsx` Multi-Hoja y Radar de Estaciones | Implementación de `aquaterra/infrastructure/exportacion/` (libros `.xlsx` de 3 hojas con stdlib y `.csv` ancho), `StationDiscoveryService` (radar priorizado por severidad, buscador por parcela/tipo y detector/importador MicroSD), `AnalyticsAndExportService` y suite de 71 pruebas en verde. |
| **[REP-006](reportes/REP-006_fase_b5_orquestador_ia_y_copiloto_calibracion.md)** | `2026-11-13` | `v4.1.0` | Fase B5 — Orquestador IA Híbrido, Copiloto de Calibración, Rollback y Mejoras IoT | Implementación de `aquaterra/core/copiloto/` (cotas físicas anti-alucinación, `AsesorDeterministaCopiloto`, contratos JSON Schema), `aquaterra/infrastructure/ia/` (`ClienteGeminiAIStudio`, `ClienteOllamaLocal`, `OrquestadorIA`), `CalibrationCopilotService` (aplicación y rollback en 1 clic + exportador `.jsonl`), reparación RTC (`calidad=2`), sincronización automática de humedad en parcelas y suite de 78 pruebas en verde. |
