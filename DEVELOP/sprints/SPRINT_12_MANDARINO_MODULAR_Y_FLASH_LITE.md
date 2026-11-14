# Sprint 12 — Refactorización Modular de Mandarino IA Studio, Motor Gemini Flash-Lite y Precalentamiento Ollama

**Fecha:** 2026-11-14  
**Plataforma:** AquaTerra Matrix v6.0.0 (`develop`)  
**Estado:** Completado y verificado end-to-end (Backend + Frontend Build + Chrome Headless CDP en vivo con Google Gemini API).

---

## 1. Arquitectura Modular de Mandarino IA Studio (`frontend/src/components/copilot/`)

Se desacopló la vista conversacional (`CopilotPage.tsx`) en componentes especializados y mantenibles bajo React 19, TypeScript y Tailwind CSS v4, manteniendo intactos los contratos API de FastAPI/Gemini/Ollama:

1. **`frontend/src/components/copilot/types.ts`**
   - Define `CanalChatId`, `TabDerecha`, `MensajeChat` (incluyendo `rawJson?: Record<string, unknown>`), `TarjetaPrincipal` y utilidades puras (`canalKey`, `esSaludoOCharlaLigera`, `obtenerSaludoHorario`).
2. **`frontend/src/components/copilot/TypingIndicator.tsx`**
   - Reemplaza los textos estáticos de carga con el avatar animado de Mandarino y tres puntos oscilantes (`role="status"`), mostrando *"Mandarino está redactando su respuesta…"*.
3. **`frontend/src/components/copilot/ChatBubble.tsx`**
   - **Renderizado Markdown + GFM:** Integración de `react-markdown` y `remark-gfm` para tablas comparativas, listas con viñetas, negritas y bloques de código estilizados.
   - **Agrupación visual (Clustering):** Cuando el mismo remitente envía 2 o más mensajes consecutivos (`agrupadoConAnterior`), oculta el avatar/encabezado repetido y compacta el margen superior en bloques conversacionales limpios.
   - **Action Menu por hover:** Botonera contextual sobre las respuestas de Mandarino (`Copiar texto`, `Regenerar respuesta` y `Ver JSON RAW` desplegable en bloque `<pre>`).
   - **Quick Replies contextuales:** Chips clicables al pie de la última respuesta de Mandarino según si hubo alertas o propuesta de recalibración (`Aplicar calibración ahora`, `Ver tabla de cotas`, `Explicar anomalía`, `Pasos prácticos en campo`, `¿Qué variables vigilo hoy?`, `Sugerencias de mejora`).
4. **`frontend/src/components/copilot/ChatMessageList.tsx`**
   - **Sticky Date Headers (`date-fns` + locale `es`):** Agrupación automática por día (`Hoy`, `Ayer` o `d 'de' MMMM`) con separadores pegajosos en el centro del scroll.
   - **Salto instantáneo sin arrastre:** Al abrir o cargar historial previo ejecuta salto inmediato al fondo (`el.scrollTop = el.scrollHeight` dentro de `requestAnimationFrame`), evitando animaciones lentas sobre mensajes viejos, junto a un botón flotante para bajar al último mensaje cuando el usuario explora mensajes anteriores.
5. **`frontend/src/components/copilot/StationSidebar.tsx`**
   - **Buscador local en tiempo real:** Filtro `<input aria-label="Filtrar canales de Mandarino">` por nombre o código de nodo.
   - **Acordeones plegables:** Secciones `🌎 Ecosistema Global` (Asistente Global TerraBit en hilo aislado propio) y `📍 Nodos Físicos` (canales dedicados por estación).
   - **Indicadores vivos de severidad:** Punto con animación `animate-pulse` para nodos en estado `atencion` / `critico` o con alertas activas, y punto estático verde `#2ecc71` en estado `optimo`.
6. **`frontend/src/components/copilot/ProactiveBoundsPanel.tsx`**
   - **Historial reciente agrupado por secciones:** Organiza las consultas guardadas por estación o ecosistema en acordeones colapsables (`Historial Reciente por Sección`), eliminando mezclas en la barra lateral y permitiendo saltar directo al canal y mensaje correspondiente.
   - **Tabla comparativa de Cotas & SFT:** Columnas `Parámetro`, `Actual`, `Recomendado` y barras horizontales de proximidad respecto al rango seguro permitido, conservando rollback y descarga de dataset `.jsonl`.
7. **`frontend/src/pages/CopilotPage.tsx`**
   - **2 tarjetas limpias en pantalla de inicio:** Excluye la tarjeta redundante de alerta de estación y conserva estrictamente **Chat Normal** y **Reporte Técnico / Reporte Ecosistema**.
   - **Persistencia de hilos en `sessionStorage`:** Cambiar entre módulos (Telemetría, Radar, Configuración, etc.) ya no reinicia los mensajes en curso de cada hilo.
   - **Menú didáctico `"Inicio Mandarino"`:** Acceso rápido al panorama interactivo del copiloto con botón directo para retornar a la conversación activa sin perder el flujo.

---

## 2. Optimizaciones de Backend, Prompt en Dos Niveles y Gemini Flash-Lite

1. **Modelo Gemini por defecto optimizado (`aquaterra/infrastructure/ia/proveedores.py`):**
   - `MODELO_GEMINI_POR_DEFECTO` actualizado a `"gemini-3.5-flash-lite"`, verificado con respuesta HTTP 200 en vivo sobre tu `GEMINI_API_KEY` frente a la saturación por cuota Free Tier (`429`) de `gemini-4-hydrogen` y latencias de `gemini-3.6-flash` / `gemini-3.8-flash`.
   - Mantiene cascada automática de respaldo con reintentos hacia Ollama local (`qwen2.5:3b`) y motor determinista (`AsesorDeterministaCopiloto`).
2. **Prompt de Dos Niveles (`aquaterra/core/copiloto/contratos_ia.py`):**
   - `es_consulta_ligera()` identifica saludos y charla general para omitir el vector crudo `parametros_calibracion_actuales` (`"modo": "charla_ligera"`), evitando alucinaciones o cambios innecesarios de calibración ante mensajes como `"Hola"`.
   - En consultas técnicas (`"modo": "diagnostico_y_calibracion"`), `construir_system_instruction_terrabit()` solicita formato estructurado en Markdown (`tablas`, `listas` y métricas medidas reales).
3. **Precalentamiento Ollama no bloqueante (`aquaterra/desktop.py`):**
   - Ejecuta `contenedor.copiloto.orquestador.precalentar_ollama_async()` al iniciar `ServidorLocalEmbebido` para mantener el modelo local cargado en memoria/GPU en segundo plano sin bloquear el arranque de la app.
4. **Selector Rápido de Modelos Gemini en UI (`frontend/src/pages/SettingsPage.tsx` & `frontend/src/types/aquaterra.ts`):**
   - Sincroniza `ia_gemini_modelo` en `EstadoSistema` y agrega botones de selección rápida en **Configuración -> IA Híbrida & Worker**: `gemini-3.5-flash-lite (Alta cuota)`, `gemini-3.8-flash` y `gemini-4-hydrogen`.

---

## 3. Verificaciones Ejecutadas tras los Cambios Finales

- **Backend (`ruff` + `pytest`):**
  - `ruff check .`: `All checks passed!`
  - `pytest -m "not gui" -ra`: **`94 passed, 4 deselected, 2 warnings in 28.69s`** (incluyendo `test_prompt_modo_ligero_vs_tecnico`).
- **Frontend (`TypeScript` + `oxlint` + `Vite`):**
  - `npx.cmd tsc --noEmit`: 0 errores.
  - `npm.cmd run lint` (`oxlint`): `0 errors` (`19 warnings` preexistentes del proyecto).
  - `npm.cmd run build` (`tsc -b && vite build`): salida código `0` (`✓ built in 3.28s`, 3778 módulos transformados).
- **E2E en Chrome Headless CDP (`cdp_sprint12_mandarino.py`) contra Backend + Gemini en vivo:**
  - `SPRINT12_LAYOUT_AND_CARDS`: 3 columnas activas, buscador, acordeones `Ecosistema Global` y `Nodos Físicos`, indicador `animate-pulse`, exactamente **2 tarjetas iniciales** (`CHAT NORMAL`, `REPORTE ECOSISTEMA`), cero tarjeta de alerta inicial.
  - `SPRINT12_SIDEBAR_FILTER`: filtrado en vivo por `"inbeersa"` funcional.
  - `SPRINT12_TYPING_INDICATOR`: `<TypingIndicator />` renderizado durante la consulta (`"Mandarino está redactando su respuesta…"`).
  - `SPRINT12_CHAT_FEATURES`: respuesta real desde Google Gemini AI (`100%` confianza), Sticky Date Header (`HOY`), botonera hover (`Copiar`, `Regenerar`, `JSON`), **Ver JSON RAW** operativo mostrando payload completo, y **Quick Replies** visibles.
  - `SPRINT12_STATION_REPORT`: reporte técnico aislado para `inbeersa-nodo01` con tabla Markdown renderizada (`tableCount: 1`).
  - `SPRINT12_RIGHT_PANEL`: `Historial Reciente por Sección` activo y tabla comparativa de Cotas (`PARÁMETRO | ACTUAL | RECOMENDADO`) con 18 elementos de barra.
  - `SPRINT12_INICIO_MENU`: guía didáctica interactiva y botón de retorno verificados.
  - `SPRINT12_SETTINGS_GEMINI`: presets visibles y campo sincronizado con `gemini-3.5-flash-lite`.
  - `EXCEPTIONS: 0` en consola del navegador.
