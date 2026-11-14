# Checkpoint de Estado Actual — AquaTerra Matrix v6.0.0 (Cierre Etapa 1)

**Fecha de Checkpoint:** 2026-11-14  
**Rama Activa / Remoto:** `develop` (`https://github.com/dfelipeduquel/AquaTerra_Matrix.git`)  
**Autor:** Daniel Felipe Duque Lizarralde  

---

## 1. Resumen Ejecutivo

**AquaTerra Matrix** cierra su Etapa 1 convertido en una plataforma operativa **Local-First**, modular y desacoplada para monitoreo Bio-IoT, control seguro de riego y diagnóstico asistido por IA (**Mandarino IA Studio**). El sistema corre de forma nativa en Windows sobre **FastAPI + SQLite WAL + PyWebView + React 19 + TypeScript + Tailwind CSS v4**, sin depender de internet ni servicios de terceros para conservar trazabilidad completa en campo.

---

## 2. Estado de Módulos en Producción (`v6.0.0`)

| Capa / Módulo | Ubicación Principal | Estado Operativo |
|---|---|---|
| **Dominio & Ciencia** | `aquaterra/core/` | Psicrometría $VPD$ (Tetens FAO-56), analítica OLS/Pearson/viento circular, Pulso 24h por familia (`TerraBit INTI`, `InBeersa`, `Sigatoka`, `Conservación`), motor de 5 candados físicos y cotas metrológicas de calibración. |
| **Casos de Uso** | `aquaterra/application/` | Pulso multi-estación, recomendador/ejecutor de riego auditado, descubrimiento de nodos, exportación `.xlsx` multi-hoja, sincronía híbrida (`Ubidots` + `Open-Meteo` + serial `nRF24L01+`) y Copiloto con contexto climático y parcelario. |
| **Persistencia & Seguridad** | `aquaterra/infrastructure/` | SQLite3 en modo `WAL` (cero bloqueo concurrente API/worker), hashing `PBKDF2-HMAC-SHA256` (600,000 iteraciones + sal), bitácora de auditoría, cookies `HttpOnly` y aislamiento RBAC (`admin`, `operador`, `lector`). |
| **API REST & Desktop** | `aquaterra/api/` · `aquaterra/desktop.py` | API FastAPI versionada con SPA React compilado (`frontend/dist`), lanzamiento nativo PyWebView o servidor web (`--web`), precalentamiento Ollama no bloqueante y accesos directos de escritorio. |
| **Frontend React 19** | `frontend/src/` | 7 vistas activas (*Radar General*, *Telemetría Multipanel ECharts*, *Parcelas*, *Control de Riego*, *Mandarino IA Studio*, *Hardware IoT* y *Configuración*), tema dual claro/oscuro, búsqueda `Ctrl+K` y selector normalizado de variables en series temporales. |
| **Mandarino IA Studio** | `frontend/src/components/copilot/` · `aquaterra/infrastructure/ia/` | Arquitectura de 3 columnas modular (`StationSidebar`, `ChatMessageList`, `ChatBubble`, `TypingIndicator`, `ProactiveBoundsPanel`), hilos aislados por estación persistentes en `sessionStorage`, Markdown + tablas GFM, enlace climático en tiempo real **Open-Meteo** (`°C` y `% lluvia` en cabecera y prompt), cascada híbrida (`gemini-3.5-flash-lite` $\to$ Ollama `qwen2.5:3b` $\to$ motor determinista) y presets rápidos en Configuración. |

---

## 3. Verificaciones de Calidad Verdes al Momento del Checkpoint

| Verificación | Alcance | Resultado Observado |
|---|---|---|
| **Linter Backend** | `ruff check .` | `All checks passed!` |
| **Suite Backend / API** | `pytest -m "not gui" -ra` | **`95 passed, 4 deselected, 2 warnings in 28.55s`** |
| **TypeScript Frontend** | `npx.cmd tsc --noEmit` | `0 errors` |
| **Linter Frontend** | `npm.cmd run lint` (`oxlint`) | `0 errors` (`19 warnings` preexistentes) |
| **Build Producción SPA** | `npm.cmd run build` (`vite`) | `✓ built in 4.47s` |
| **E2E Navegador Real** | Chrome Headless CDP (`Open-Meteo` + `gemini-3.5-flash-lite` en vivo) | `SPRINT13_HEADER_WEATHER` activo, `claimsNoWeather: false`, `mentionsTempOrRain: true`, `hasGenericBoilerplate: false`, `EXCEPTIONS: 0` |
| **Seguridad Git Pública** | Escaneo de secretos e historial Git + `.gitignore` | Cero credenciales en historial ni staged; `data/runtime/` y `.env` ignorados; `.env.example` creado; `frontend/src/lib/` correctamente versionado. |

---

## 4. Arranque Rápido al Retomar el Desarrollo (Etapa 2)

```powershell
cd C:\Users\danie\Developer\AquaTerra_Matrix
.\.venv\Scripts\Activate.ps1
ruff check .
pytest -m "not gui" -ra
python main.py
```

* Todo el legado detallado de Sprints 01–13, ADRs y reportes `REP-000`–`REP-008` quedó archivado ordenadamente en [`historico_etapa_1/`](historico_etapa_1/).
