# 🌱 AquaTerra Matrix — Sistema Central de Administración Ecológica, Agrícola y Bio-IoT

**Ecosistema:** TerraBit Agrotech & Conservación (Semilleros Kilby & MUCEM — Universidad Tecnológica de Pereira)  
**Autor y Arquitecto de Software:** Daniel Felipe Duque Lizarralde  
**Versión Actual:** `v3.2.0-legacy` (En transición hacia `v4.0.0 Core SQLite & IoT Ingest`)  

---

## 1. Visión y Propósito del Sistema
**AquaTerra Matrix** (evolución directa de *AquaUTP v3.2*) es el **Centro de Operaciones Local y Servidor Matriz en Python** diseñado para administrar unidades productivas agrícolas, estaciones de monitoreo microclimático y nodos de conservación ecológica de alta montaña.

Integra bajo una sola arquitectura de software:
- **🌱 TerraBit Nodo INTI:** Telemetría edafoclimática (Humedad capacitiva calibrada + filtro EMA, Temperatura radicular DS18B20, Presión/Temp/HR ambiental, Déficit de Presión de Vapor $VPD$, presupuesto energético LiFePO4/LiPo y gestión de riego).
- **🐝 InBeersa (Abejas Angelitas — *Melipona eburnea*):** Monitoreo termohigrométrico interno/externo de colmenas, calidad de aire ($\text{CO}_2/\text{VOCs}$ vía MQ-135) e indexación de eventos bioacústicos I2S (archivos WAV 32-bit PCM @ 16 kHz).
- **🍌 Sigatoka:** Vigilancia microclimática foliar y mojado de hoja para alerta temprana fitosanitaria (*Mycosphaerella fijiensis*).
- **🏔️ Conservación & Páramos (Polylepis):** Series temporales hidro-ecológicas en turberas y bosques altoandinos con operación *Offline-First*.

---

## 2. Estructura del Proyecto

```text
AquaTerra_Matrix/
├── assets/                  # Recursos gráficos de interfaz (fondos, iconos)
├── data/                    # Capa de persistencia (v3.2 CSV/JSON -> v4.0 SQLite WAL)
├── docs/                    # Documentación de arquitectura, manuales y diagramas
├── legacy/
│   └── aquautp_v3.2/        # Respaldo histórico inmutable de la base v3.2
├── models/                  # Capa de dominio y acceso a datos (GestorDatos, Auth)
├── views/                   # Vistas gráficas (ttkbootstrap + Matplotlib TkAgg)
├── main.py                  # Punto de entrada de la aplicación
├── requirements.txt         # Dependencias del entorno virtual (.venv)
├── CHANGELOG_INGENIERIA.md  # Bitácora forense de auditoría, deuda técnica y versiones
└── README.md                # Documentación general del repositorio
```

---

## 3. Instalación y Ejecución Local

### Requisitos Previos
- **Python:** `3.11+` (recomendado `Python 3.13` 64-bit en Windows).

### Configuración del Entorno Virtual (`.venv`)
```powershell
# 1. Posicionarse en el directorio raíz del repositorio
cd C:\Users\danie\Developer\AquaTerra_Matrix

# 2. Crear el entorno virtual aislado
py -3.13 -m venv .venv

# 3. Activar el entorno e instalar dependencias
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 4. Ejecutar el sistema
python main.py
```

---

## 4. Roadmap de Ingeniería por Versiones

| Versión | Nombre Clave | Alcance Técnico Principal | Estado |
|---|---|---|---|
| **v3.2.0** | `Legacy Seed` | Base funcional en `ttkbootstrap`, `pandas` y `matplotlib`. Congelación de respaldo histórico, entorno `.venv` y autoría unificada. | ✅ **Completado (Fase 0)** |
| **v3.3.0** | `Integrity Patch` | Resolución de los 5 hallazgos críticos de auditoría: integridad referencial de IDs, validación de formularios, cierre de figuras Matplotlib (`plt.close`), ciclo único `mainloop()` y hashing SHA-256/PBKDF2 de credenciales. | 🚧 **En Cola (Fase 1A)** |
| **v4.0.0** | `Core SQLite & Ingest` | Migración de CSV/JSON planos a **SQLite3 (modo WAL)** con esquema relacional (`estaciones`, `parcelas`, `telemetria_series`, `eventos_riego`, `eventos_bioacustica`). Ingestadores nativos para `/data.csv` (Nodo INTI) y `/data.json` JSONL (InBeersa). | 📋 **Planificado (Fase 1B)** |
| **v5.0.0** | `Matrix Telemetry Hub` | Servidor local de telemetría por antena (**LoRa / ESP-NOW / WiFi LR -> Gateway Serial/MQTT Mosquitto local**), sincronización bidireccional con **Ubidots API/MQTT** (Store & Forward) y motor de alertas agronómicas ($VPD$, punto de marchitez, anomalías térmicas en colmena). | 🔭 **Horizonte (Fase 2)** |

---

**Licencia y Propiedad Intelectual:**  
Desarrollado íntegramente por **Daniel Felipe Duque Lizarralde** — Ingeniería UTP / Ecosistema TerraBit.
