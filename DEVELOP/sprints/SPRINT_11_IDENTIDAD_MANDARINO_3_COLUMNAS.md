# Sprint 11 — Identidad Real de Mandarino, Estudio de 3 Columnas, Memoria por Hilo y Resiliencia IA

**Fecha:** 2026-11-14  
**Rama / Versión:** `develop` · AquaTerra Matrix v6.0.0 (`Mandarino IA Studio`)

---

## 1. Objetivo del Sprint
Dar identidad visual propia al asistente **Mandarino**, rediseñar el módulo conversacional en una arquitectura de **3 columnas con ventana fija de chat** (sin expansión infinita ni desplazamiento del cursor), garantizar **segmentación estricta entre hilos** manteniendo **conciencia global del ecosistema**, añadir un menú interactivo y didáctico para regresar al **Inicio de Mandarino**, y corregir los fallos de cuelgue y amnesia conversacional detectados en el backend de IA.

---

## 2. Qué se hizo, cómo y por qué

### 2.1 Identidad Visual Real de Mandarino (cero fondo azul)
- **Extracción transparente (`RGBA` 512×512):** A partir de la ilustración vectorizada suministrada (`maceta con árbol de mandarinas`), se removió el fondo turquesa mediante flood-fill BFS desde bordes y limpieza cromática perimetral (*despill*), guardando el recurso limpio en:
  - [`frontend/src/assets/mandarino-avatar.png`](../../frontend/src/assets/mandarino-avatar.png) (incorporado al bundle final en `dist/assets/mandarino-avatar-GrLb7QPN.png`, `158.75 kB`).
- **Componente animado [`MandarinoAvatar.tsx`](../../frontend/src/components/common/MandarinoAvatar.tsx):**
  - Variantes de tamaño (`xs | sm | md | xl`), estados `flotar` (respiración suave + halo radial naranja) y `pensando` (anillo orbital punteado animado).
  - Respeto estricto a `prefers-reduced-motion` en [`frontend/src/index.css`](../../frontend/src/index.css) (`@keyframes mandarino-sway`, `.mandarino-sway`).
  - Integrado en la barra lateral de navegación de [`AppShell.tsx`](../../frontend/src/components/layout/AppShell.tsx) junto a `"Mandarino IA"`.

### 2.2 Estudio Conversacional de 3 Columnas y Ventana Móvil Acotada
- **Reestructuración integral de [`CopilotPage.tsx`](../../frontend/src/pages/CopilotPage.tsx):**
  1. **Columna Izquierda (`Estaciones disponibles · xl:col-span-3`):**
     - Selector directo entre **`Charla General`** (ecosistema completo sin mezclar nodos) y cada estación activa (`inbeersa-nodo01`, `terrabit-nodointi`, etc.) con badge de severidad, alertas activas y contador independiente de mensajes del hilo (`chatsPorCanal[clave]`).
  2. **Columna Central (`Conversación activa · xl:col-span-6`, altura acotada `h-[640px] xl:h-[calc(100dvh-13rem)] xl:min-h-[540px] xl:max-h-[820px]`):**
     - Contenedor interno con scroll propio (`flex-1 min-h-0 overflow-y-auto`) y caja de texto fija (`shrink-0`), evitando que conversaciones de 100+ mensajes expandan la página o desplacen el cursor.
     - Ventaneo progresivo (`VENTANA_MENSAJES_INICIAL = 30`, botón superior *"Ver mensajes anteriores (+25)"*) y auto-scroll inteligente (`cercaDelFondoRef` + píldora flotante *"Mensajes recientes"* cuando el operador navega hacia arriba).
  3. **Columna Derecha (`Proactivo e Historial` + `Cotas & SFT` · `xl:col-span-3`):**
     - **Sugerencias Proactivas:** Tarjetas de acción en 1 clic enfocadas en nodos críticos o en atención, abriendo directamente el hilo de esa estación.
     - **Soluciones y Calibraciones:** Versiones recientes aplicadas por estación (`versiones_globales`) con estado de respaldo para rollback.
     - **Historial Reciente por Estación:** Últimas interacciones globales etiquetadas por estación para retomar cualquier hilo pasado en 1 clic.
     - **Pestaña `Cotas & SFT`:** Límites metrológicos auditables, rollback de versiones y exportación del dataset `.jsonl`.

### 2.3 Menú Interactivo y Didáctico («Inicio Mandarino»)
- **Navegación bidireccional sin perder el hilo:**
  - En la cabecera del estudio y en la subbarra central aparece el menú **`Inicio Mandarino`** / **`Principal | Chat (N)`**. Al estar dentro de una conversación activa, el operador puede regresar en 1 clic al apartado principal sin perder sus mensajes y volver con **`Volver a tu conversación activa (N mensajes)`**.
  - **Guía Didáctica Interactiva en 3 modos:** *1. Leer Telemetría y Alertas*, *2. Recalibrar Dentro de Cotas*, y *3. Visión Global + Memoria de Hilo*, cada uno con explicación de uso (*Cuándo usarlo*, *Tip rápido*) y disparadores de ejemplo en 1 clic.
  - **Atajos contextuales sobre el input (`!mostrarInicio`):** Píldoras rápidas (`Ir al Inicio de Mandarino`, `¿Qué sugerencias me das?`, `Pasos en campo`) para continuidad conversacional sin fricción.

### 2.4 Segmentación Estricta, Memoria Multi-Turno y Resiliencia en Cascade IA
- **Segmentación backend + conciencia global:**
  - [`aquaterra/infrastructure/db/repositorios.py`](../../aquaterra/infrastructure/db/repositorios.py): `RepositorioCopiloto.listar(..., solo_sin_estacion=True)` aísla `WHERE estacion_id IS NULL` en charla general; `RepositorioCalibraciones.listar_recientes_globales(limite=12)` alimenta el panel derecho.
  - [`aquaterra/api/routers/copiloto.py`](../../aquaterra/api/routers/copiloto.py): `GET /api/copiloto/estado` acepta `solo_sin_estacion` y expone `historial_reciente_global` y `versiones_globales`.
  - [`aquaterra/core/copiloto/contratos_ia.py`](../../aquaterra/core/copiloto/contratos_ia.py) y [`aquaterra/application/copiloto_servicio.py`](../../aquaterra/application/copiloto_servicio.py): inyectan `panorama_global_estaciones` para visión completa de finca y `ultimos_turnos` (`[-5:]` estrictos del mismo canal/estación) como `historial_hilo_actual`.
  - Prompt refactorizado en primera persona (*"Hola, soy Mandarino…"*), prohibiendo tercera persona (*"el operador realizó..."*) y repetición ciega de reportes previos ante repreguntas.
- **Corrección crítica de bloqueo por HTTP 429 en Gemini + reintentos controlados ([`proveedores.py`](../../aquaterra/infrastructure/ia/proveedores.py)):**
  - **Hallazgo real:** Al agotarse la cuota Free Tier de `gemini-4-hydrogen` (`20 req/día`, `HTTP 429`), `genai.Client.interactions.create(...)` (`google-genai 3.3.0`) entraba en reintentos exponenciales automáticos durante muchos minutos por no especificar `HttpRetryOptions`.
  - **Solución:**
    - `HttpOptions(timeout=..., retry_options=HttpRetryOptions(attempts=3, initial_delay=0.5, max_delay=1.5, exp_base=2.0, http_status_codes=[408, 500, 502, 503, 504]))` + `timeout=self._timeout` explícito en `interactions.create(...)`: otorga **3 intentos rápidos** ante errores transitorios `408/5xx`, pero **no reintenta `429`**, cayendo limpio en **~1.4 s**.
    - **Circuit Breaker en `OrquestadorIA` (`COOLDOWN_CUOTA_GEMINI_SEG = 300.0`):** Al detectar cuota agotada (`429`), pausa los intentos a Gemini por 5 minutos y enruta directo a Ollama (`qwen2.5:3b`, con `"keep_alive": "10m"` en `/api/chat`) o al asesor determinista local.
- **Asesor Determinista ampliado ([`asesor_reglas.py`](../../aquaterra/core/copiloto/asesor_reglas.py)):** Soporte directo para repreguntas prácticas (*"sugerencias"*, *"al respecto"*, *"pasos"*, *"qué más puedes hacer"*).

---

## 3. Verificación Ejecutada (Resultados Reales)
- **Backend Lint & Unit Tests:**
  - `ruff check .` → **`All checks passed!`**
  - `pytest -m "not gui" -ra` → **`93 passed, 4 deselected, 2 warnings`** (las 4 pruebas `gui` de Tkinter fueron deseleccionadas con `-m "not gui"` por ausencia de recursos `ttk/sizegrip.tcl` en Python 3.13 headless Windows). Incluye pruebas unitarias nuevas de segmentación estricta y memoria multi-turno / circuit breaker 429 en [`tests/test_copiloto_y_calibracion.py`](../../tests/test_copiloto_y_calibracion.py).
- **Frontend Build & Types:**
  - `npx tsc --noEmit` + `npm run lint` (`oxlint`, `0 errors`) + `npm run build` (`vite build`) → **`✓ built in 1.39s`**.
- **Prueba E2E Chrome Headless (CDP sobre copia temporal de `data/runtime/aquaterra.db`):**
  - Circuit breaker activado limpiamente ante `429` sin colgar el hilo: `Gemini AI Studio alcanzó límite de cuota (429); activando enfriamiento 300s y pasando a respaldo local.`
  - `SPRINT11_LAYOUT`: `threeColumns: true`, `centerHeight: 597`, `avatarImgsCount: 3`, `avatarLoaded: true`, `hasBigWelcome: true`, `hasProactiveRight: true`.
  - `SPRINT11_GENERAL_CHAT`: `done: true` (respuesta completa entregada vía `Ollama Local`).
  - `SPRINT11_SEGMENTATION_STATION`: `inInbeersaThread: true`, `showsStationWelcome: true`, `neverMixedGeneralMsg: true`.
  - `SPRINT11_GENERAL_PRESERVED`: `generalPreserved: true`.
  - `SPRINT11_INICIO_MENU`: `showsDidacticGuide: true`, `showsReturnCta: true`.
  - `SPRINT11_RIGHT_COTAS_TAB`: `hasDatasetBtn: true`, `hasUmbral: true`.
  - `EXCEPTIONS`: `0`.

---

## 4. Próximas Mejoras Recomendadas (Sprint 12+)
1. **Desacoplar modo conversacional ligero del esquema de calibración para modelos locales 3B:** En pruebas reales con `ollama:qwen2.5:3b`, enviar todo el catálogo de parámetros de calibración cuando el usuario solo envía un saludo lleva ocasionalmente a que el modelo 3B proponga calibraciones innecesarias. En preguntas casuales conviene enviar contexto resumido con un esquema simple (`respuesta` + `sugerencias`) y reservar el esquema de recalibración para consultas técnicas/umbrales.
2. **Precalentamiento automático de Ollama al arranque desktop + caché de sesión UI:** Lanzar `precalentar_ollama_async()` en segundo plano al iniciar `ServidorLocalEmbebido` para absorber los ~17.6 s de carga inicial en VRAM antes del primer chat, y persistir `chatsPorCanal` en `sessionStorage` para no perder los globos visibles al cambiar temporalmente a *Telemetría*.
3. **Scroll directo a mensaje desde Historial Reciente:** Al hacer clic en un ítem de *Historial Reciente por Estación*, resaltar y desplazar exactamente hasta esa interacción específica.
