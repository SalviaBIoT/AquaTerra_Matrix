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
├── reportes/                                                    # Reportes paso a paso de cada fase ejecutada
│   ├── REP-000_migracion_semilla_y_entorno.md                   # Fase 0: Semilla v3.2, Git, .venv y diagnóstico
│   └── REP-001_arquitectura_v4_y_resolucion_deuda_tecnica.md    # Fase 1: Arquitectura 4 capas, SQLite WAL y DT-01..05
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
