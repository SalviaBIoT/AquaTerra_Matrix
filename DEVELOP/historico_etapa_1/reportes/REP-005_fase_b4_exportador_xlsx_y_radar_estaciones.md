# REP-005: Fase B4 — Exportador Ejecutivo Multi-Hoja (`.xlsx` / `.csv`) y Radar de Estaciones Priorizado

- **Fecha:** `2026-11-13`
- **Versión:** `v4.1.0a4`
- **Rama:** `develop`
- **Autor:** Daniel Felipe Duque Lizarralde

---

## 1. Resumen Ejecutivo

Se ejecutó completamente la **Fase B4** definida en la [Brújula Maestra de Arquitectura (`ARQUITECTURA_MAESTRA_BRUJULA.md`)](../ARQUITECTURA_MAESTRA_BRUJULA.md), implementando el paquete modular de exportación `aquaterra/infrastructure/exportacion/` (`xlsx_writer.py` y `exportador_estacion.py`), el servicio `AnalyticsAndExportService` (`aquaterra/application/exportacion_servicio.py`) y el servicio `StationDiscoveryService` (`aquaterra/application/radar_servicio.py`), ambos integrados en `Contenedor`. El sistema genera libros `.xlsx` nativos OpenXML de **3 hojas profesionales** sin dependencias externas (`zipfile` + `xml.etree.ElementTree`), exporta matrices temporales `.csv` con medias móviles, ordena automáticamente la flota de estaciones por criticidad operativa (`CRITICO` $\to$ `ATENCION` $\to$ `OPTIMO` $\to$ `SIN_DATOS`), ofrece búsqueda multicriterio y detecta/importa archivos de campo desde unidades o directorios MicroSD.

---

## 2. Mapeo de Cambios por Capa (Modularización Estricta)

| Capa / Archivo | Cambio Implementado | Justificación Técnica / Agronómica |
|---|---|---|
| `aquaterra/__init__.py` | Incremento de `__version__` a `"4.1.0a4"`. | Cuarto corte incremental del Backend v4.1. |
| `aquaterra/infrastructure/exportacion/xlsx_writer.py` | Implementación de `HojaCalculo`, `escribir_libro_xlsx()` y `leer_hojas_xlsx()`. | Escritor y lector OpenXML (`.xlsx`) con la biblioteca estándar de Python (cero dependencias pesadas de terceros). |
| `aquaterra/infrastructure/exportacion/exportador_estacion.py`<br/>`aquaterra/infrastructure/exportacion/__init__.py` | Implementación de `construir_hojas_reporte_estacion()`, `exportar_reporte_estacion_xlsx()` y `exportar_series_csv()`. | Construye las 3 hojas ejecutivas (`1_Ficha_y_Resumen`, `2_Series_Temporales`, `3_Eventos_y_Riegos`) y el CSV en formato ancho. |
| `aquaterra/application/radar_servicio.py` | Implementación de `StationDiscoveryService`, `EntradaRadarEstacion`, `OrigenDatosDetectado` y `ResultadoImportacionEstacion`. | Prioriza estaciones por severidad, filtra por parcela/ecosistema/alertas y detecta e importa archivos de campo (`data.csv`, `data.json`, `MUNDONUEVO.csv`, `turbera.csv`). |
| `aquaterra/application/exportacion_servicio.py`<br/>`aquaterra/application/contenedor.py`<br/>`aquaterra/application/__init__.py` | Creación de `AnalyticsAndExportService` e inyección de `Contenedor.radar` y `Contenedor.exportacion`. | Orquesta exportación ejecutiva conectando `NodePulseService`, ventanas móviles SQLite e historial de riegos/eventos. |
| `tests/test_exportacion_y_radar.py` | 3 pruebas integrales cubriendo priorización del radar, búsqueda por parcela/alerta/tipo, autodetección MicroSD de las 4 familias y exportación `.xlsx`/`.csv`. | Verifica la integridad estructural de las 3 hojas `.xlsx` y la importación automática. |

---

## 3. Detalle Técnico Implementado

### 3.1. Exportador Ejecutivo Multi-Hoja `.xlsx` y `.csv` (`exportacion/`)

1. **Motor OpenXML Estándar (`xlsx_writer.py`):**
   - Construye el paquete ZIP reglamentario (`[Content_Types].xml`, `_rels/.rels`, `xl/workbook.xml`, `xl/_rels/workbook.xml.rels`, `xl/styles.xml` y `xl/worksheets/sheetN.xml`) con encabezados en negrita sobre fondo verde institucional (`#1B4332`), celdas numéricas (`t="n"`) y textos UTF-8 (`t="inlineStr"`).
2. **Estructura de 3 Hojas Ejecutivas (`exportador_estacion.py`):**
   - **`1_Ficha_y_Resumen`:** Metadatos geográficos y de ecosistema de la estación, rango ISO-8601 exportado, severidad, completitud global, diagnóstico determinista y tabla estadística por variable (`Ultimo_Valor`, `Media_Periodo`, `Minimo_Periodo`, `Maximo_Periodo`, `Tendencia`, `Tasa_Por_Hora`, `Muestras`, `Completitud_Pct`).
   - **`2_Series_Temporales`:** Matriz temporal en formato ancho (`Timestamp_Epoch`, `Fecha_Hora_ISO`) con cada variable y su respectiva columna `<variable>_media_movil_<ventana>` calculada en SQLite.
   - **`3_Eventos_y_Riegos`:** Fusión ordenada cronológicamente de los eventos de riego de las parcelas asociadas (incluyendo `efectividad` y $\Delta\theta_A$) y los eventos discretos de `eventos_estacion`.

### 3.2. Radar de Estaciones y Auto-Detección (`radar_servicio.py`)

- **Priorización por Criticidad (`listar_radar_priorizado`):** Ordena la flota colocando primero las estaciones en estado `CRITICO`, seguidas de `ATENCION`, `OPTIMO` y finalmente `SIN_DATOS`.
- **Buscador Multicriterio (`buscar_estaciones`):** Permite buscar simultáneamente por código de nodo, nombre de estación, familia de ecosistema o nombre de la parcela agrícola asociada.
- **Autodetección e Importación de Archivos (`detectar_archivos_estacion` & `importar_archivo_estacion`):** Reconoce firmas de archivo y cabeceras de las 4 familias (`TERRABIT_INTI`, `INBEERSA`, `SIGATOKA`, `CONSERVACION`) e importa sus lecturas y eventos en una sola transacción.

---

## 4. Pruebas y Verificación

- **Suite `pytest -v`:** `71 passed` (`0` fallos, `0 warnings`), incluyendo las 3 pruebas de `tests/test_exportacion_y_radar.py`.
- **Linter `ruff check .`:** `All checks passed!`.
- **Documentos de referencia:** [ARQUITECTURA_MAESTRA_BRUJULA.md](../ARQUITECTURA_MAESTRA_BRUJULA.md) · [REP-004](REP-004_fase_b3_enclavamientos_salud_bomba_e_incidencia_riego.md).

---

## 5. Próximo Paso de Ingeniería

Ejecutar la **Fase B5 (cierre del Backend v4.1)**: construir `aquaterra/application/copiloto/` con el **Orquestador de IA Híbrido en Cascada (`Gemini API` $\to$ `Ollama Local` $\to$ `RuleBasedAdvisor` determinista)** y el **Copiloto Conversacional de Calibración (`CalibrationCopilotService`)** con *rollback* de parámetros en 1 clic y cotas duras anti-alucinación.
