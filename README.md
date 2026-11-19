# SalviaBIoT

Plataforma **Local-First** de telemetría biológica, inteligencia ambiental, control hidráulico con enclavamientos físicos de seguridad y diagnóstico asistido por IA (**Mandarino IA Studio**) para redes de sensores ESP32 / Bio-IoT.

> **Ecosistema SalviaBIoT (*Biological Internet of Things*)** · Conservación & Agricultura Regenerativa de Precisión  
> **Arquitectura de Producto:** **TerraBit Station** (Capa 1 · Hardware de Campo) → **Mandarino IA** *(motor cognitivo provisional rumbo a Savia + Mandarín)*  
> **Autor y Arquitecto:** Daniel Felipe Duque Lizarralde · Pereira, Colombia

---

## Estaciones y Líneas Bio-IoT Soportadas

- **TerraBit Station (Nodo INTI):** Estación edafoclimática autónoma — humedad capacitiva del suelo (calibrada + EMA), temperatura radicular DS18B20, presión/temperatura/humedad ambiental, VPD psicrométrico (Tetens FAO-56) y gestión energética.
- **InBeersa (*Melipona eburnea*):** Homeostasis térmica/higrométrica interna y externa de colmenas, calidad de aire (`CO2/VOCs`) y trazabilidad de eventos bioacústicos I2S.
- **Sigatoka:** Vigilancia microclimática foliar y humedad de hoja para alerta temprana fitosanitaria.
- **Conservación & Páramos (*Polylepis*):** Series temporales hidro-ecológicas de alta montaña preparadas para operación intermitente / offline.

---

## Características Principales (`v6.0.0`)

- **App Nativa & Web Local-First:** Backend `FastAPI` + `SQLite WAL` empaquetado sobre `PyWebView` (o navegador con `--web`) sin depender de la nube para operar en campo.
- **Motor Analítico y Control Seguro:**
  - Pulso operativo 24 h por estación, tasa de secado OLS, correlación bivariada de Pearson y balance hídrico por parcela.
  - **Safety Interlock Engine (5 candados físicos):** Lluvia inminente (Open-Meteo), suelo en capacidad de campo, anomalía de sensor/salud de bomba, saturación y ventana de caudal.
- **Mandarino IA Studio:** Copiloto agronómico modular con hilos aislados por estación, enlace climático en tiempo real vía **Open-Meteo**, memoria conversacional, cotas metrológicas anti-alucinación y cascada híbrida (`Google Gemini` $\to$ `Ollama GPU/CPU local` $\to$ `Motor determinista`).
- **Conectores e Ingesta:** Sincronización incremental `Ubidots REST`, gateway serial `nRF24L01+ PA+LNA`, importador CSV/MicroSD, exportador ejecutivo `.xlsx` (3 hojas) y alertas vía `n8n` / `Telegram`.

---

## Arquitectura del Proyecto

```text
SalviaBIoT_Platform/
├── aquaterra/
│   ├── core/             # Dominio, psicrometría VPD, analítica OLS/Pearson, candados y contratos IA
│   ├── application/      # Casos de uso, pulso 24h, control de riego, sync híbrida y Copiloto
│   ├── infrastructure/   # SQLite WAL, PBKDF2-SHA256, Open-Meteo, Ubidots, Ollama/Gemini, .xlsx
│   ├── api/              # API REST FastAPI, cookies HttpOnly y RBAC (admin / operador / lector)
│   └── desktop.py        # Servidor embebido + ventana nativa PyWebView / modo web
├── frontend/             # SPA React 19 + TypeScript + Tailwind CSS v4 + ECharts + React-Markdown
├── DEVELOP/              # ADRs, reportes de ingeniería, sprints y guías técnicas
├── scripts/              # Utilidades CLI, generador de íconos y accesos directos de escritorio
├── tests/                # Suite automatizada pytest (core, API v6, SQLite WAL, IA y desktop)
├── legacy/aquautp_v3.2/  # Semilla histórica preservada de AquaUTP v3.2
├── .env.example          # Plantilla de variables de entorno (sin credenciales)
└── main.py               # Punto de entrada unificado
```

---

## Inicio Rápido

### 1. Entorno Python y Backend

```bash
git clone https://github.com/SalviaBIoT/AquaTerra_Matrix.git
cd AquaTerra_Matrix

python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
# source .venv/bin/activate

pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 2. Compilar el Frontend Web (`React + Vite`)

```bash
cd frontend
npm install
npm run build
cd ..
```

### 3. Configurar Variables Opcionales y Ejecutar

```bash
cp .env.example .env
# Edita .env si deseas añadir GEMINI_API_KEY, UBIDOTS_TOKEN o modelo Ollama
```

```bash
# Modo aplicación de escritorio (PyWebView):
python main.py

# Modo servidor web en navegador (puerto 8765):
python main.py --web
```

> En el primer arranque sin usuarios configurados, SalviaBIoT siembra la base SQLite local en `data/runtime/aquaterra.db` (ruta retrocompatible). Accede con tu usuario operativo y gestiona credenciales/roles desde **Configuración**.

---

## Calidad y Pruebas

```bash
ruff check .
pytest -m "not gui" -ra

cd frontend
npx tsc --noEmit
npm run lint
```

La trazabilidad completa por fases y sprints (`REP-000`–`REP-008`, `ADR-001`–`ADR-004` y `SPRINT_01`–`SPRINT_13`) vive en [DEVELOP/README.md](DEVELOP/README.md).
