# Sprint 08 — Paridad de Contratos API/TS y Verificación E2E en Chrome Real

## 1. Diagnóstico de Causa Raíz (Pantalla Negra Post-Login)

Al iniciar sesión con credenciales válidas (`admin` / `1234`), el endpoint `/api/auth/login` autenticaba correctamente y React cambiaba de `LoginPage` a `DashboardPage` (actualizando `<title>` a `Radar General · AquaTerra Matrix`). Sin embargo, un desajuste acumulado entre los modelos JSON serializados por FastAPI (`dataclasses` reales de `aquaterra/core/domain/` y servicios de `aquaterra/application/`) y las interfaces TypeScript del frontend causaba un `TypeError` no capturado durante el primer renderizado:

- En `DashboardPage.tsx`, el código intentaba evaluar `entry.alertas_resumen[0]` sobre una propiedad inexistente (`EntradaRadarEstacion` expone `alertas_activas: number`, `completitud_24h_pct`, `ultimo_ts_epoch`, `diagnostico_resumen`, `parcelas_asociadas`). Al no existir un `ErrorBoundary`, React desmontaba todo el árbol `#root`, dejando únicamente el fondo oscuro (`#0A0E0C`).

Además, una auditoría campo-por-campo contra `TestClient` y los routers reales reveló desajustes adicionales de contrato en múltiples vistas que habrían provocado fallos o valores vacíos al interactuar con ellas.

---

## 2. Correcciones Implementadas

### 2.1 Resiliencia Global (`AppErrorBoundary`)
- **`frontend/src/App.tsx`**: Se envolvió `<AppProvider>` en un componente de clase `AppErrorBoundary` (`getDerivedStateFromError` + `componentDidCatch`) con tarjeta de diagnóstico en español y botón de recarga segura para evitar pantallas en blanco silenciosas ante cualquier excepción de renderizado.

### 2.2 Contrato TypeScript 1:1 con Dataclasses de Backend
- **`frontend/src/types/aquaterra.ts`**: Reescritura completa alineada 1:1 con los esquemas JSON reales de FastAPI para:
  - Radar y pulso (`EntradaRadarEstacion`, `ResumenPulso24h`, `ResumenVariablePulso`, `PronosticoPunto`, `EventoEstacion`).
  - Seguridad hidráulica y actuadores (`EstadoCandado`, `VeredictoSeguridad`, `RecomendacionRiego`, `SaludActuador`, `EventoRiego`, `RiegoProgramado`, `IncidenciaRiego`).
  - Copiloto IA y calibración (`CotaCalibracion`, `RecorteParametro`, `InteraccionCopiloto`, `VersionCalibracion`, `ConsultarCopilotoResponse`).
  - Búsqueda global (`ItemBusquedaGlobal`, `ResultadoBusquedaGlobal`) y salud del sistema (`EstadoSistema`).
- **`frontend/src/lib/formatters.ts`**: Incorporación de `formatearFechaIso()` y `minutosDesdeEpoch()`, y ampliación del mapa `NOMBRES_VARIABLES` con claves reales de telemetría (`suelo_a`, `suelo_b`, `temp_aire`, `hum_aire`, `presion`, `temp_raiz`, `voltaje`, `vpd`), códigos de candados físicos, indicadores por familia (`inti`, `inbeersa`, `sigatoka`, `conservacion`) y claves del catálogo de calibración.

### 2.3 Alineación por Página y Componentes
- **`frontend/src/pages/LoginPage.tsx`**: Corrección de la etiqueta de roles en el pie informativo (`lector` en lugar de `visualizador`).
- **`frontend/src/components/common/CommandPalette.tsx`**: Navegación adaptada a `categoria` y `referencia_id` y renderizado seguro de `item.detalle ?? item.subtitulo ?? ""`.
- **`frontend/src/pages/HardwarePage.tsx`**: Tabla de bitácora conectada a los campos reales de `EventoEstacion` (`ev.ts_epoch`, `ev.tipo_evento`, `ev.valor_texto`, `ev.archivo_ruta`).
- **`frontend/src/pages/DashboardPage.tsx`**: Tabla de Radar y panel Estación Focal actualizados a `completitud_24h_pct`, `diagnostico_resumen`, `alertas_activas`, `minutosDesdeEpoch(entry.ultimo_ts_epoch)`, `completitud_global_pct`, `hasta_epoch`, `alertas_detectadas` y unidades en tarjetas de variables.
- **`frontend/src/pages/IrrigationPage.tsx`**: Sincronización completa con `ControlService` y `/api/parcelas/{id}/riego/contexto`:
  - `veredicto_seguridad` (`autorizado`, `motivos_bloqueo`, `advertencias_recorte`) y candados (`superado`, `recorte_aplicado`, `detalle`, `nombreLegibleVariable(c.codigo)`).
  - Tarjeta de recomendación (`regar`, `justificacion`, `apertura_sugerida_pct`, `umbral_disparo_pct`).
  - Salud de bomba (`diagnostico_mecanico`, `modo_verificacion`, `apertura_max_pct`, `caudal_lpm`, `corriente_a`, `registrado_en`, último `delta_a_pct`).
  - Tablas y selector de eventos post-riego (`litros_propuestos`, `motivo_bloqueo`, `agua_litros`, `humedad_inicial_pct -> humedad_final_pct`, `evaluado_en`, `observaciones`).
- **`frontend/src/pages/CopilotPage.tsx`**: Historial conectado a `diagnostico_ia`, `calibracion_aplicada_id` y `ts_iso`; panel de auditoría adaptado a `propuesta` (`diagnostico_tecnico`, `justificacion_agronomica`, `confianza`, `alertas_consideradas`) y `auditoria` (`ajustes_seguros`, `recortes_aplicados`, `claves_rechazadas`, `advertencias_seguridad`); Diff Auditor mapeado por `cota.clave`, `cota.valor_por_defecto` y `formatearFechaIso(v.creado_en)`.

---

## 3. Verificación Técnica Ejecutada

| Verificación | Alcance | Resultado |
|---|---|---|
| `npx.cmd tsc --noEmit` + `npm.cmd run lint` + `npm.cmd run build` | Todo el paquete React/TypeScript/Vite | Exit code `0`, bundle generado en `frontend/dist/` |
| Chrome Headless vía CDP (`cdp_probe.py`) | Login + navegación por las **7 vistas**, sub-pestañas de Riego y Configuración, popover `Estado` y búsqueda `Ctrl+K` (`"INTI"`) | **0 excepciones JS (`Runtime.exceptionThrown`)**, **0 errores HTTP tras login**, DOM poblado en las 7 vistas (`34.6 KB`–`49.2 KB` de HTML) |
| `.\.venv\Scripts\ruff.exe check .` | Código Python completo (`aquaterra/`, `tests/`) | `All checks passed!` |
| `.\.venv\Scripts\pytest.exe -ra` | Suite completa de pruebas backend | `93 passed, 1 skipped` (`tests/test_ui_smoke.py:48` omitido por falta de display gráfico en entorno headless) |
