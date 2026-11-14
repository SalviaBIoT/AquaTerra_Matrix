# Sprint 10 — Mandarino IA Studio: Chat Futurista Orgánico, Identidad Conversacional e Inspector Desplegable

**Fecha:** 2026-11-14  
**Estado:** Completado y verificado end-to-end (backend + frontend + Chrome headless CDP)  
**Rama:** `develop`

---

## 1. Problema Identificado y Objetivo de Diseño

En el módulo anterior (`Copiloto IA`), la pantalla presentaba dos fricciones clave:
1. **Respuesta fría y burocrática ante conversación humana:** Al escribir `"Hola"`, el modelo respondía como ticket de auditoría (*"Dado que el operador realizó únicamente un saludo sin solicitar recalibración..."*) y forzaba bloques rígidos de `DIAGNÓSTICO` / `RECOMENDACIÓN`.
2. **Arquitectura visual densa:** La columna lateral permanente (*Diff Auditor*, barras de cotas físicas y versiones) competía con la conversación antes de que el usuario siquiera hubiera pedido una calibración, y las tarjetas estáticas de consulta no reflejaban las alertas reales de los nodos en campo.

**Meta del Sprint 10:** Dar vida a **Mandarino** (`Mandarino IA`), un copiloto futurista con estética naranja/ámbar animada, experiencia *Chat-First* bidireccional izquierda/derecha, pantalla de bienvenida protagónica con tarjetas dinámicas basadas en errores críticos reales del ecosistema e **Inspector Técnico** opcional desplegable bajo demanda.

---

## 2. Arquitectura Implementada

### 2.1 Backend: Personalidad "Mandarino" e Intención Conversacional (`contratos_ia.py`, `asesor_reglas.py`, `copiloto_servicio.py`)
1. **`aquaterra/core/copiloto/contratos_ia.py`:**
   - Actualización de `construir_system_instruction_terrabit()` y de las descripciones de `ESQUEMA_JSON_RESPUESTA_COPILOTO`: ahora el modelo adopta explícitamente el nombre y tono de **Mandarino** (cercano, colaborativo, futurista y con rigor Bio-IoT).
   - **Separación de modo conversacional vs. técnico:** ante saludos o preguntas abiertas (*"Hola"*, *"Quién eres"*, *"Qué tal"*), responde en primera persona con calidez mencionando brevemente novedades relevantes de la estación activa (si hay alerta), dejando `justificacion_agronomica` vacía (`""`) y `ajustes_propuestos` en `{}` sin frases robóticas.
2. **`aquaterra/core/copiloto/asesor_reglas.py`:**
   - Se incorporaron `_es_charla_conversacional()` y `_responder_como_mandarino()` en `AsesorDeterministaCopiloto` para que incluso en operación 100 % offline sin Gemini ni Ollama, un saludo reciba una bienvenida humana contextualizada con el estado vivo o alerta activa del nodo.
3. **`aquaterra/application/copiloto_servicio.py`:**
   - Persistencia limpia en `consultar_copiloto()`: solo concatena `\n\nJustificación: ...` cuando `justificacion_agronomica` tiene contenido, evitando guardar separadores vacíos en saludos.

### 2.2 Estética y Micro-animaciones Naranja Futurista (`index.css` y `AppShell.tsx`)
1. **`frontend/src/index.css`:**
   - Variables de acento naranja (`--mandarino-primary: #f97316`, `--mandarino-bright: #fb923c`, `--mandarino-soft`, `--mandarino-border`, `--mandarino-glow`).
   - Keyframes dedicados: `mandarino-breathe` (respiración lumínica del núcleo/avatar `.mandarino-orb`), `mandarino-orbit` (anillo orbital punteado `.mandarino-ring`), `mandarino-wave` (ondas naranjas de pensamiento `.mandarino-dot`) y `mandarino-msg-in` (entrada fluida de burbujas). Respeto estricto a `@media (prefers-reduced-motion: reduce)`.
2. **`frontend/src/components/layout/AppShell.tsx` y `AppContext.tsx`:**
   - Etiqueta y título de vista actualizados a **Mandarino IA** con acento naranja en la barra lateral.

### 2.3 Estudio Conversacional Mandarino (`frontend/src/pages/CopilotPage.tsx`)
1. **Bienvenida Protagónica Futurista:**
   - Núcleo animado `.mandarino-orb` + órbita `.mandarino-ring` y saludo personalizado con el primer nombre del operador (`¡Hola, {nombre}! Soy Mandarino.`).
   - Resumen de estado vivo del nodo focal y conteo automático de alertas en el ecosistema, junto con botón opcional para retomar sesiones previas guardadas en SQLite.
2. **Tarjetas Dinámicas Basadas en Errores Críticos Reales:**
   - A partir de `entradasRadar`, si alguna estación presenta `severidad` `"critico"` / `"atencion"` o `alertas_activas > 0` (por ejemplo `inbeersa-nodo01` fuera de homeostasis térmica), se destacan tarjetas naranjas de **Alerta Crítica** que cambian automáticamente el nodo en contexto y lanzan la consulta diagnóstica en 1 clic.
   - Se complementan con tarjetas de pulso vivo 24h, calibración preventiva ante lluvia y charla inicial.
3. **Chat Orgánico Izquierda / Derecha:**
   - **Mensajes del usuario (derecha):** aparición optimista inmediata al enviar, burbujas translúcidas con tinte naranja, etiqueta de estación y marca horaria.
   - **Mensajes de Mandarino (izquierda):** avatar `.mandarino-orb`, badge de motor (`Google Gemini AI`, `Ollama Local` o `Motor Determinista Local`), confianza porcentual y cuerpo natural. Cuando existe fundamento agronómico, se muestra en un sub-bloque con borde naranja; cuando solo es conversación, la burbuja se mantiene ligera y limpia.
   - **Estado de pensamiento animado:** indicador de ondas naranjas con rotación de mensajes de estado mientras responde el modelo en la nube.
   - **Tarjetas interactivas de calibración dentro del chat:** si Mandarino propone ajustes seguros dentro de cotas, el bloque aparece integrado en la burbuja con deltas legibles y botones directos `"Ver en Inspector"` y `"Aplicar ajuste"` (para rol `admin`).
4. **Inspector Técnico Desplegable (`mostrarInspector`):**
   - Oculto por defecto para mantener el estudio limpio; accesible en 1 clic desde el botón **Inspector Técnico** (con contador naranja cuando hay cambios auditados) o desde cualquier propuesta en el chat.
   - Contiene el visualizador de cotas físicas `[mín..máx]`, marcadores actual/propuesto, historial de versiones, botón `Rollback anterior` y exportación de dataset `.jsonl`.
5. **Limpieza editorial reforzada (`formatters.ts`):**
   - `limpiarTextoCopiloto` ahora también traduce claves internas sin comillas invertidas (`suelo_a`, `suelo_b`, `temp_aire`, `umbral_humedad_pct`, etc.) a nombres agronómicos legibles.

---

## 3. Verificación Técnica Ejecutada (Post-Edición)

- **Frontend:**
  - `npx tsc --noEmit`: salida `0` (sin errores de tipos).
  - `npm run lint` (`oxlint`): `0 errors` (`20 warnings` no bloqueantes del linter React Compiler).
  - `npm run build` (`tsc -b && vite build`): `✓ built in 1.16s`.
- **Backend:**
  - `ruff check .`: `All checks passed!`.
  - `pytest -ra`: `93 passed, 2 skipped` (`test_ui_smoke.py` Tkinter omitido por ausencia de display en subproceso; incluye la nueva prueba `test_mandarino_saludo_conversacional_y_modo_tecnico`).
- **E2E Real en Chrome Headless + CDP (sobre DB temporal aislada):**
  - Pantalla de bienvenida Mandarino: `hasHeroGreeting=true`, `hasDynamicAlertCard=true` (detectando en vivo la alerta crítica real de `inbeersa-nodo01` por temperatura de nido `23.5 °C`), `inspectorHiddenByDefault=true`.
  - Prueba real de `"Hola"` con **Google Gemini AI**: burbuja derecha (`Smoke`) + respuesta izquierda cálida de **Mandarino** (`hasBotReply=true`, `hasRoboticPhrase=false`, `hasAsterisk=false`, `hasBacktick=false`): *"¡Hola! Soy Mandarino, tu copiloto de ingeniería agronómica, Bio-IoT y metrología en TerraBit. Al revisar la estación inbeersa-nodo01 noto una alerta crítica..."*.
  - Activación bajo demanda del botón **Inspector Técnico**: `inspectorVisible=true`, `hasCotas=true`.
  - **0 excepciones JavaScript** y **0 errores 500** durante todo el recorrido.
