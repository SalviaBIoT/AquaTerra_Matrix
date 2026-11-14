# Sprint 4 (Fase 3) — Radar Bento, Telemetría ECharts Interactiva y Gestión de Parcelas

**Fecha de ejecución:** 2026-11-14  
**Estado:** Completado y compilado con éxito (`tsc --noEmit` + `vite build` en 3.69s)  
**Archivos creados/actualizados:**
- `frontend/src/components/charts/EChartBox.tsx`
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/pages/TelemetryPage.tsx`
- `frontend/src/pages/ParcelsPage.tsx`
- `frontend/src/App.tsx`

---

## 1. Qué se hizo
1. **Motor reutilizable Apache ECharts adaptativo al tema (`components/charts/EChartBox.tsx`):**
   - Encapsulación con `ResizeObserver` automático, soporte Canvas de alto rendimiento y paleta dinámica (`obtenerPaletaECharts`) vinculada a `temaEfectivo` (*Obsidian Canopy* y *Field Daylight*).
2. **Radar General — Bento Grid de Alta Claridad (`pages/DashboardPage.tsx`):**
   - **Banner Editorial de Narrativa IA 24h:** Dispara `POST /api/estaciones/{id}/narrar-24h` y `POST /api/sistema/notificar-24h`, muestra cargadores *skeleton* mientras responde la IA local/híbrida y ofrece copia en 1 clic.
   - **4 Tarjetas KPI con `.tabular-nums`:** Estaciones monitoreadas, nodos en alerta, parcelas productivas y completitud media 24h acompañada de un mini *sparkline* ECharts en tiempo real.
   - **Radar Priorizado + Pulso Focal + Clima 48h:** Tabla ordenable/filtrable por texto, familia `TipoEstacion` y alertas activas con barras finas de completitud, panel de estadísticos 24h por variable y gráfica combinada Open-Meteo 48h (barras de precipitación `mm` + línea de temperatura `°C`).
3. **Telemetría Multipanel, Regresión OLS y Comparativas (`pages/TelemetryPage.tsx`):**
   - **Segmentador Temporal:** `6h | 24h | 7d | Todo` sincronizado con `/api/estaciones/{id}/series`.
   - **Paneles Adaptativos por Familia IoT (`TERRABIT_INTI`, `INBEERSA`, `SIGATOKA`, `CONSERVACION`):** Agrupa automáticamente variables físicas relacionadas en gráficas ECharts con crosshair (`axisPointer: 'cross'`), zoom interactivo (`dataZoom` slider + rueda/pinch) y leyendas ancladas fuera del área de trazado.
   - **Correlación Bivariada & Regresión OLS:** Selectores `Variable X / Variable Y` conectados a `/api/estaciones/{id}/correlacion`, presentando coeficiente `r` de Pearson, pendiente `m`, pares alineados e interpretación agronómica junto al scatter + recta OLS.
   - **Balance Hídrico Comparativo:** Dos gráficas paralelas (`/api/monitor/comparativo`) de humedad edáfica actual (%) con semáforo agronómico y consumo acumulado (L) por parcela.
   - Exportación directa a `.csv` y `.xlsx` mediante Blob autenticado.
4. **Parcelas y Unidades de Cultivo con Drawer Nativo (`pages/ParcelsPage.tsx`):**
   - KPIs de superficie (`m²` y hectáreas equivalentes), humedad promedio y porcentaje de parcelas automatizadas.
   - Tabla interactiva con indicador visual tipo *gauge* horizontal de humedad del suelo, nodo IoT vinculado y acceso directo al control de riego.
   - **Slide-over `<dialog>`** para crear y editar parcelas respetando validaciones de dominio y permisos RBAC, más modal de confirmación de borrado lógico con foco inicial en el botón seguro.

---

## 2. De qué manera se implementó
- Se respetó estrictamente la separación de responsabilidades: todos los cálculos estadísticos (promedios, VPD, emparejamiento ≤ 300 s, Pearson `r` y recta OLS) provienen de `aquaterra/core/` vía API REST; el frontend únicamente transforma marcas de tiempo a milisegundos (`ts * 1000`) para los ejes `'time'` de ECharts.
- Los paneles comparativos y modales emplean elementos HTML nativos (`<dialog>` con `.showModal()`), reduciendo código de manejo de foco y evitando bloqueos artificiales de scroll sobre `<body>`.

---

## 3. Por qué era necesario
- En Tkinter/Matplotlib las gráficas eran imágenes estáticas incrustadas con leyendas superpuestas y sin exploración puntual por fecha/hora. Apache ECharts aporta inspección milimétrica, zoom suave sobre ventanas multi-día y cambio instantáneo entre temas sin regenerar imágenes en Python.
- La vista de parcelas requería un flujo no bloqueante (Drawer lateral) que mantuviera el contexto del inventario visible mientras se ajustan suelo, área o vinculación IoT.

---

## 4. Cómo mejora la ruta del frontend final
1. **Lectura agronómica en segundos:** Un operador o investigador detecta en el Bento Radar qué estación requiere atención, inspecciona el pulso 24h y verifica si lloverá antes de autorizar riego.
2. **Analítica reproducible para semilleros e investigación:** Pearson `r`, OLS, series multi-ventana y exportación Excel/CSV a un clic quedan integradas en una misma superficie profesional.
3. **Listo para Sprint 5:** La navegación desde Parcelas hacia Control de Riego y desde Hardware hacia Radar/Telemetría ya enlaza directamente con la estación y parcela seleccionadas.
