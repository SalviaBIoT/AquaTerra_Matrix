# Sprint 5 (Fase 4) — Control de 5 Candados, Copiloto IA Diff Auditor, Hardware de Campo y Configuración

**Fecha de ejecución:** 2026-11-14  
**Estado:** Completado y compilado con éxito (`tsc --noEmit` + `vite build` en 1.48s)  
**Archivos creados/actualizados:**
- `frontend/src/pages/IrrigationPage.tsx`
- `frontend/src/pages/CopilotPage.tsx`
- `frontend/src/pages/HardwarePage.tsx`
- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/App.tsx` (eliminado `PlaceholderView.tsx` temporal)

---

## 1. Qué se hizo
1. **Control de Riego & Enclavamientos Físicos (`pages/IrrigationPage.tsx`):**
   - **Stepper Horizontal de 5 Candados:** Visualiza en tarjetas independientes el resultado real de cada candado (`veredicto_candados.candados`) en tonos semánticos translúcidos (aprobado, advertencia no bloqueante, bloqueo físico), con detalle de umbral aplicado vs lectura actual.
   - **Recomendación Proactiva & Despacho Hidráulico:** Presenta acción recomendada, volumen sugerido, lluvia esperada 24h, tasa de secado (`%/h`) y horas hasta estrés hídrico; incluye deslizador de umbral de disparo (`%`), ejecución inmediata (`POST /api/parcelas/{id}/riego/aplicar`) y programación validada (`POST /api/parcelas/{id}/riego/programar`).
   - **Auditoría Mecánica de Bomba y Verificación Post-Riego ΔθA/ΔθB:** Tarjeta de salud del actuador y formulario (`POST /api/riego/incidencia`) para registrar lectura antes/después en dos profundidades más caudal (`L/min`) y corriente eléctrica (`A`), más pestañas de programados, historial e incidencias.
2. **Copiloto IA & Diff Auditor de Calibración (`pages/CopilotPage.tsx`):**
   - **Consola Técnica:** Chips de consulta rápida agronómica, historial persistente de interacciones y compositor de texto respetuoso con IME (`!e.nativeEvent.isComposing` antes de enviar con `Enter`).
   - **Diff Auditor con Barras de Cota Física `[mín..máx]`:** Compara cada parámetro efectivo de `CATALOGO_COTAS_CALIBRACION` frente a los ajustes propuestos por la IA, muestra los ajustes bloqueados por el guardarraíl físico de `aquaterra/core/copiloto`, habilita aplicación aprobada (`admin`) en 1 clic, **Rollback** instantáneo a versiones previas y descarga de dataset SFT `.jsonl`.
3. **Hardware de Campo IoT & MicroSD (`pages/HardwarePage.tsx`):**
   - Descubrimiento de puertos `COM` y lectura por lotes (`POST /api/hardware/serial/leer`).
   - Decodificador e inyector manual de tramas nRF24L01+ / LoRa con reporte por trama recibida vs lecturas insertadas.
   - Escáner automático de unidades/carpetas MicroSD con detección de familia `TipoEstacion` e importación CSV en 1 clic, más botón de reparación de marcas RTC (`calidad=2`) y bitácora de eventos de estación.
4. **Configuración con Sub-navegación Vertical (`pages/SettingsPage.tsx`):**
   - **Conectores & Alertas:** Ubidots, webhook n8n/WhatsApp, Telegram, opción de guardado en `.env` local (con campos enmascarados sin exponer secretos) y selector explícito tri-estado de tema (*Sistema / Field Daylight / Obsidian Canopy*).
   - **IA Híbrida & Worker:** Selección de proveedor (`hibrido`, `ollama`, `gemini`, `local`), precalentamiento VRAM de Ollama y control del Worker autónomo en segundo plano.
   - **Estaciones IoT & GPS:** Alta de estaciones con latitud/longitud/altitud o sembrado rápido de nodos base.
   - **Usuarios & RBAC:** Listado de cuentas y creación de usuarios (`admin`, `operador`, `visualizador`).

---

## 2. De qué manera se implementó
- Se mantuvieron los permisos estrictos por rol (`esAdmin`, `puedeOperar`): los usuarios `operador` y `visualizador` ven con claridad qué acciones requieren rol `admin` (ej. aplicar calibración, controlar el worker, gestionar usuarios o conectores), evitando llamadas fallidas innecesarias pero manteniendo el respaldo HTTP `403` en FastAPI.
- En el compositor del Copiloto se aplicó verificación explícita de composición IME (`isComposing`) siguiendo las guías modernas de formularios accesibles.

---

## 3. Por qué era necesario
- El flujo completo de operación agronómica en AquaTerra Matrix requiere cerrar el ciclo: **Telemetría → Diagnóstico Copiloto → Calibración auditada → Evaluación 5 Candados → Despacho de Riego → Verificación física post-riego ΔθA/ΔθB**.
- Unificar hardware serial, escáner MicroSD y calibración visual en barras de cota física evita errores humanos peligrosos sobre actuadores y sensores.

---

## 4. Cómo mejora la ruta del frontend final
1. **Paridad funcional 100% con Tkinter pero experiencia 10x superior:** Cada flujo crítico de las 7 vistas originales está implementado sin sobrecarga visual y con retroalimentación clara por *toasts* (`sonner`) y estados vacíos guiados.
2. **Listo para Sprint 6 (Fase 5):** Con las 7 vistas completas y compiladas en `frontend/dist`, solo falta encapsular el servidor local FastAPI dentro del launcher nativo `pywebview` / `--web`, validar pruebas E2E HTTP y cerrar el lanzamiento `v6.0.0`.
