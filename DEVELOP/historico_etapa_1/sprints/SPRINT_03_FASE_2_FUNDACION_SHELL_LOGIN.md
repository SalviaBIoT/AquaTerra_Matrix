# Sprint 3 (Fase 2) — Fundación Visual Bio-Tech, Login Split-Screen y App Shell Minimalista

**Fecha de ejecución:** 2026-11-14  
**Estado:** Completado y compilado con éxito (`tsc --noEmit` + `vite build` en 1.32s)  
**Archivos creados/actualizados:**
- `frontend/vite.config.ts`
- `frontend/index.html`
- `frontend/src/index.css`
- `frontend/src/types/aquaterra.ts`
- `frontend/src/lib/api.ts`
- `frontend/src/lib/formatters.ts`
- `frontend/src/context/AppContext.tsx`
- `frontend/src/components/common/Badge.tsx`
- `frontend/src/components/common/CommandPalette.tsx`
- `frontend/src/components/layout/AppShell.tsx`
- `frontend/src/pages/LoginPage.tsx`
- `frontend/src/App.tsx`
- `frontend/src/main.tsx`
- `frontend/src/assets/paisajeriego.png`

---

## 1. Qué se hizo
1. **Fundación tipográfica y cromática *Bio-Tech Orgánico* offline (`index.html` + `index.css`):**
   - Integración de `@tailwindcss/vite` (Tailwind CSS v4) con tipografía local `@fontsource/plus-jakarta-sans` y `@fontsource/jetbrains-mono` empaquetada dentro del bundle final (sin dependencia de internet/Google Fonts en entornos rurales).
   - Implementación del sistema dual de tokens CSS:
     - **Obsidian Canopy (Dark):** Lienzo `#0A0E0C`, superficie `#111814`, elevación `#17211C`, texto `#F1F5F2`, acento bio-tech `#34D399`.
     - **Field Daylight (Light):** Lienzo `#F5F7F4`, superficie `#FFFFFF`, elevación `#EEF2ED`, texto `#0F1713`, acento esmeralda `#059669`.
   - Prevención síncrona de flash visual (*FOUC*) en `<head>` mediante `<meta name="color-scheme" content="light dark">` y selector `:has(> head > meta[name="color-scheme"])` con fallback `@media (prefers-color-scheme: dark)` y `[data-theme]`.
2. **Capa de contratos y cliente HTTP tipado (`types/aquaterra.ts`, `lib/api.ts`, `context/AppContext.tsx`):**
   - Tipado completo espejo de las entidades de `aquaterra/core/` y los endpoints FastAPI de Fase 1.
   - Cliente `fetch` con soporte simultáneo de cookies `HttpOnly` (`credentials: "include"`) y respaldo `Authorization: Bearer` en `sessionStorage`, más extractor unificado de errores `ApiError` y descargador seguro por `Blob` para `.xlsx`, `.csv` y `.jsonl`.
   - Contexto global `AppProvider` que administra sesión, sincronización de tema sistema/claro/oscuro entre pestañas, título dinámico `<title>` accesible por ruta y estación activa compartida entre vistas.
3. **Pantalla de Acceso Split-Screen (`pages/LoginPage.tsx`):**
   - Composición asimétrica con fotografía agronómica real (`paisajeriego.png`) tratada con gradiente Obsidian a la izquierda y formulario de alta legibilidad a la derecha.
   - Validación accesible tras interacción real (`onBlur` / `submit` con `:user-invalid` + `.user-invalid-fallback`, `aria-invalid`, `aria-describedby`), botón de visibilidad de contraseña con `aria-pressed` y región `role="alert"` para errores de autenticación.
4. **App Shell Minimalista y Command Palette (`components/layout/AppShell.tsx`, `CommandPalette.tsx`):**
   - Sidebar colapsable (`232px` expandida / `68px` contraída) organizada en 3 bloques limpios (*MONITOREO*, *OPERACIÓN*, *INFRAESTRUCTURA*) sin prefijos numéricos ni emojis decorativos, más drawer responsive en pantallas pequeñas y *skip link* de accesibilidad.
   - Topbar de `56px` con selector global de estación IoT, botón de sincronización Open-Meteo/Ubidots, **Popover de Salud del Ecosistema** (SQLite WAL, Ubidots, IA, Worker, puertos COM, n8n/Telegram), toggle inteligente de tema (2 estados respetando preferencia del SO) y disparador del buscador **`Ctrl+K`**.
   - **Command Palette nativo `<dialog closedby="any">`** conectado en vivo con `/api/sistema/buscar` y atajos instantáneos a las 7 vistas y estaciones IoT.

---

## 2. De qué manera se implementó
- Se evitó cualquier polyfill pesado o librería de UI innecesaria: los modales utilizan `<dialog>` nativo con `showModal()` y contención `overscroll-behavior: contain` tanto en `dialog:modal` como en `dialog::backdrop`, sin bloquear el scroll del `<body>`.
- El toggle de tema de la barra superior implementa el patrón de dos estados inteligentes: cuando el usuario vuelve al tema que coincide con su sistema operativo, limpia la preferencia manual en `localStorage` para volver a seguir al sistema automáticamente (`light dark`).
- El Vite proxy (`/api -> http://127.0.0.1:8765`) permite desarrollo en caliente con HMR mientras `vite build` produce los assets y fuentes listos para FastAPI y PyWebView.

---

## 3. Por qué era necesario
- Sin un sistema unificado de tokens cromáticos, tipografía tabular (`.tabular-nums`) y contratos TypeScript estrictos (`verbatimModuleSyntax` + `erasableSyntaxOnly`), cada vista habría reinventado estilos, formularios y manejo de errores.
- El acceso rural exige que **todo** (fuentes Plus Jakarta Sans, JetBrains Mono, iconografía Lucide y activos fotográficos) quede compilado localmente sin llamadas a CDNs externos.

---

## 4. Cómo mejora la ruta del frontend final
1. **Identidad visual consolidada desde la raíz:** Elimina definitivamente los `LabelFrame` neón y menús numerados heredados de Tkinter, estableciendo un estándar nivel Linear/Grafana adaptado a ingeniería bio-agronómica.
2. **Navegación de teclado y productividad real (`Ctrl+K`):** Los investigadores pueden saltar en milisegundos entre estaciones, bitácoras, eventos de riego y auditorías de calibración sin navegar manualmente por menús.
3. **Desbloqueo total para Sprints 4 y 5:** Las 7 vistas operativas y analíticas ahora se montan directamente sobre un `AppShell`, contexto de estación activa y cliente HTTP ya validados en compilación real.
