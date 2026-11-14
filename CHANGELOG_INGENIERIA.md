# Bitácora Técnica de Ingeniería: AquaTerra Matrix (Python Architecture)

**Proyecto:** Software Matriz de Administración Ecológica, Agrícola y Bio-IoT (Evolución de AquaUTP v3.2)  
**Ecosistema:** TerraBit / InBeersa / Sigatoka / Conservación Polylepis (Semilleros Kilby & MUCEM — UTP)  
**Autor & Arquitecto Principal:** Daniel Felipe Duque Lizarralde  

> **Nota de Trazabilidad:** El desglose exhaustivo de reportes paso a paso (`REP-XXX`), decisiones de arquitectura (`ADR-XXX`) y propuestas (`PRP-XXX`) se encuentra en el directorio **[`DEVELOP/`](DEVELOP/README.md)**.

---

## [v4.1.0a2] - 2026-11-13: Fase B2 — Motor Analítico de Series Temporales, Ventana Móvil SQLite y Pulso 24h

### 1. Hitos Estructurales Implementados (Ver [REP-003](DEVELOP/reportes/REP-003_fase_b2_motor_analitico_ventana_movil_y_pulso_24h.md))
- **Paquete Analítico de Dominio Puro (`aquaterra/core/analitica/`):**
  - `series.py`: Cálculo de ventanas móviles (`30m`, `1h`, `6h`, `24h`, `7d`), pendiente horaria por mínimos cuadrados ordinarios (`tasa_cambio_por_hora` para tasa de secado edáfico $\Delta\theta/\Delta t$), proyección de horas hasta estrés hídrico (`tiempo_hasta_umbral_horas`), correlación bivariada de Pearson $r$ (`correlacion_bivariada`) y promedio vectorial circular de viento (`promedio_vectorial_grados`).
  - `pulso.py`: Motor determinista offline `construir_resumen_pulso_24h()` con indicadores especializados por familia (`IndicadoresPulsoInti`, `IndicadoresPulsoInBeersa`, `IndicadoresPulsoSigatoka`, `IndicadoresPulsoConservacion`), detección de alertas y síntesis ejecutiva.
- **Window Functions Nativas en SQLite3 (`aquaterra/infrastructure/db/repositorios.py`):**
  Nuevos métodos `serie_rango()`, `series_estacion_rango()` y `serie_ventana_movil()` (`AVG/MIN/MAX OVER (ORDER BY ts_epoch RANGE BETWEEN ? PRECEDING AND CURRENT ROW)`) en `RepositorioLecturas`.
- **Servicio de Aplicación (`aquaterra/application/pulso_servicio.py`):**
  `NodePulseService` integrado en `Contenedor.pulso` con `obtener_pulso_24h()`, `consultar_ventana_movil()` y `comparar_variables()`.
- **Verificación Automatizada:**
  Suite de **64 pruebas en `pytest`** (`0 warnings`) y **`ruff check .`** (`All checks passed!`).

---

## [v4.1.0a1] - 2026-11-13: Fase B1 — Esquema SQLite v2, Repositorios de Control/Calibración e Ingesta Universal de 4 Familias

### 1. Hitos Estructurales Implementados (Ver [REP-002](DEVELOP/reportes/REP-002_fase_b1_esquema_v2_e_ingesta_universal.md))
- **Migración SQLite `v1 -> v2` (`aquaterra/infrastructure/db/esquema.py`):**
  Incorporación de `_MIGRACION_002` (`VERSION_ESQUEMA = 2`) con 7 tablas nuevas: `eventos_estacion`, `calibraciones_nodo`, `salud_actuadores_log`, `incidencia_riego`, `riegos_programados`, `pronostico_clima_cache` y `conversaciones_copiloto`.
- **Nuevas Entidades de Dominio (`aquaterra/core/domain/`) y Repositorios (`repositorios.py`):**
  4 `StrEnum` (`ModoVerificacionRiego`, `DiagnosticoMecanicoBomba`, `EfectividadRiego`, `EstadoRiegoProgramado`), 7 `dataclass` inmutables y 7 repositorios incluyendo `RepositorioCalibraciones` con versionado histórico y *rollback* en un paso (`restaurar_version()`).
- **Ingesta Universal de 4 Familias (`aquaterra/infrastructure/iot_ingest/adaptadores.py`):**
  - **Sigatoka:** Nuevo `parsear_csv_sigatoka()` con autodetección entre `/MUNDONUEVO.csv` (con cabecera) y `/buffer_sigatoka.json` (sin cabecera), derivación de `hoja_humectada` ($\ge 70\%$), rosa de vientos en grados + `EventoEstacion(tipo_evento="direccion_viento")` y cálculo de $VPD$.
  - **Conservación & Páramos:** Nuevo `parsear_csv_conservacion()` para `nivel_freatico_cm`, turberas y microclima altoandino.
  - **TerraBit Nodo INTI & InBeersa:** Soporte para telemetría hidromecánica (`VibracionRMS`, `VibracionFreq`, `CorrienteBomba`, `CaudalLPM`, `AperturaValvula`), campos del struct `TelemetriaInBeersa` y cálculo automático de `vpd` y `delta_temp`.
  - **Guardia Temporal RTC:** Marcado automático `calidad = 2` para lecturas anteriores a `EPOCH_MINIMO_VALIDO = 1_704_067_200` (`2024-01-01`).
- **Verificación Automatizada:**
  Suite de **57 pruebas en `pytest`** (`0 warnings`) y **`ruff check .`** (`All checks passed!`).

---

## [v4.0.0a1] - 2026-11-13: Fase 1 — Re-Arquitectura en 4 Capas, Motor SQLite WAL, Ingesta IoT y Cierre de Deuda Técnica

### 1. Hitos Estructurales Implementados (Ver [REP-001](DEVELOP/reportes/REP-001_arquitectura_v4_y_resolucion_deuda_tecnica.md))
- **Paquete Modular `aquaterra/` ([ADR-002](DEVELOP/decisiones/ADR-002_arquitectura_capas_y_contenedor.md)):**
  Separación estricta en `core/` (entidades inmutables, validadores, psicrometría $VPD$ Tetens, balance hídrico y tiempo ISO-8601), `infrastructure/` (SQLite WAL, seguridad PBKDF2, migrador v3.2 e ingesta IoT), `application/` (casos de uso transaccionales y contenedor de dependencias) y `ui/` (vistas `ttkbootstrap` sobre una única raíz `ttk.Window`).
- **Persistencia Transaccional SQLite3 en Modo WAL ([ADR-001](DEVELOP/decisiones/ADR-001_sqlite_wal_y_retiro_pandas_runtime.md)):**
  Esquema relacional versionado (`PRAGMA user_version = 1`) con tablas `usuarios`, `estaciones`, `parcelas`, `eventos_riego`, `lecturas_sensor` y `auditoria`. Migración automática y atómica de la semilla v3.2 en el primer arranque.
- **Erradicación del 100% de la Deuda Técnica Auditada en v3.2:**
  - **DT-01:** Eliminada la renumeración de IDs; implementado archivado lógico (`activa = 0`) y `ON DELETE RESTRICT` en `eventos_riego`.
  - **DT-02:** Estandarización temporal dual (`ts_iso` en `UTC-05:00` + `ts_epoch` Unix) y retiro de reescritura de CSV/JSON planos ([ADR-004](DEVELOP/decisiones/ADR-004_estandar_temporal_iso8601_y_epoch.md)).
  - **DT-03:** Validación de dominio compartida entre creación y actualización (`validar_datos_parcela`).
  - **DT-04:** Uso de `matplotlib.figure.Figure` orientado a objetos y liberación explícita en `VistaMonitor.destroy()`, eliminando la fuga de memoria.
  - **DT-05:** Unificación a un solo `mainloop()` con retorno limpio al cerrar sesión, y hashing `PBKDF2-HMAC-SHA256` (600,000 iteraciones + salt de 16 bytes) con rehash automático ([ADR-003](DEVELOP/decisiones/ADR-003_seguridad_pbkdf2_y_auditoria.md)).
- **Adaptadores de Ingesta para Firmwares Reales (`aquaterra/infrastructure/iot_ingest/adaptadores.py`):**
  Soporte nativo y deduplicado para `/data.csv` de **TerraBit Nodo INTI**, `/data.json` JSONL de **InBeersa** (con filtrado de anomalías `-200.0 °C` del DHT22) y payloads JSON de **Ubidots Industrial**.
- **Centro de Trazabilidad `DEVELOP/`:**
  Creación de estructura formal con reportes (`REP-000`, `REP-001`), decisiones (`ADR-001` a `ADR-004`), propuestas (`PRP-001`, `PRP-002`) y plantillas.
- **Verificación Automatizada:**
  Suite de **47 pruebas en `pytest`** (`0 warnings`) y análisis estático con **`ruff`** (`All checks passed!`).

---

## [v3.2.0-legacy] - 2026-11-12: Fase 0 — Migración a Developer, Línea Base Git y Auditoría Forense

### 1. Hitos de Infraestructura y Despliegue (Ver [REP-000](DEVELOP/reportes/REP-000_migracion_semilla_y_entorno.md))
- **Migración Arquitectónica a `C:\Users\danie\Developer\AquaTerra_Matrix`** y publicación en GitHub (`dfelipeduquel/AquaTerra_Matrix`).
- **Preservación de Línea Base:** Copia intacta en `legacy/aquautp_v3.2/` y tag Git `v3.2.0-legacy`.
- **Unificación de Autoría** bajo Daniel Felipe Duque Lizarralde y configuración de entorno virtual `.venv` (Python 3.13).
