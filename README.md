# 🌱 AquaTerra Matrix — Sistema Central de Administración Ecológica, Agrícola y Bio-IoT

**Ecosistema:** TerraBit Agrotech & Conservación (Semilleros Kilby & MUCEM — Universidad Tecnológica de Pereira)  
**Autor y Arquitecto de Software:** Daniel Felipe Duque Lizarralde  
**Versión Actual:** `v4.1.0a3` (Fase B3: Enclavamientos de Seguridad + Salud de Bomba + Planificador Proactivo)  

---

## 1. Visión y Propósito del Sistema
**AquaTerra Matrix** (evolución directa de *AquaUTP v3.2*) es el **Centro de Operaciones Local y Servidor Matriz en Python** diseñado para administrar unidades productivas agrícolas, estaciones de monitoreo microclimático y nodos de conservación ecológica de alta montaña.

Integra bajo una sola arquitectura de software:
- **🌱 TerraBit Nodo INTI:** Telemetría edafoclimática (Humedad capacitiva calibrada + filtro EMA, Temperatura radicular DS18B20, Presión/Temp/HR ambiental, Déficit de Presión de Vapor $VPD$, presupuesto energético LiFePO4/LiPo y gestión de riego).
- **🐝 InBeersa (Abejas Angelitas — *Melipona eburnea*):** Monitoreo termohigrométrico interno/externo de colmenas, calidad de aire ($\text{CO}_2/\text{VOCs}$ vía MQ-135) e indexación de eventos bioacústicos I2S (archivos WAV 32-bit PCM @ 16 kHz).
- **🍌 Sigatoka:** Vigilancia microclimática foliar y mojado de hoja para alerta temprana fitosanitaria (*Mycosphaerella fijiensis*).
- **🏔️ Conservación & Páramos (Polylepis):** Series temporales hidro-ecológicas en turberas y bosques altoandinos con operación *Offline-First*.

---

## 2. Arquitectura y Estructura del Repositorio

```text
AquaTerra_Matrix/
├── aquaterra/                        # Paquete principal en 4 capas (Clean Architecture)
│   ├── core/                         # Dominio puro y ciencia agronómica (Cero I/O)
│   │   ├── domain/                   # Entidades inmutables, validadores y errores
│   │   ├── agronomia/                # Psicrometría (VPD Tetens FAO-56) y balance hídrico
│   │   ├── analitica/                # Ventanas móviles, secado OLS, Pearson r, viento circular y Pulso 24h
│   │   ├── control/                  # SafetyInterlockEngine (5 candados), salud de bomba y planificador
│   │   └── tiempo.py                 # Estandarización ISO-8601 (UTC-05:00) + Unix Epoch
│   ├── application/                  # Casos de uso, permisos, transacciones y contenedor DI
│   ├── infrastructure/               # Adaptadores técnicos
│   │   ├── db/                       # Motor SQLite3 (modo WAL), migraciones y repositorios
│   │   ├── seguridad/                # Hashing PBKDF2-HMAC-SHA256 (600,000 iteraciones + salt)
│   │   ├── legacy/                   # Migrador atómico desde AquaUTP v3.2
│   │   └── iot_ingest/               # Parsers para Nodo INTI, InBeersa, Sigatoka, Conservación y Ubidots
│   └── ui/                           # Interfaz ttkbootstrap con raíz única y Matplotlib OO
├── DEVELOP/                          # Centro de Trazabilidad (Reportes, ADRs y Propuestas)
│   ├── README.md                     # Índice maestro y matriz de deuda técnica
│   ├── ARQUITECTURA_MAESTRA_BRUJULA.md # Brújula Maestra v4.0 -> v5.0 (Fases B1..B5 + UI)
│   ├── reportes/                     # REP-000, REP-001, REP-002, REP-003, REP-004...
│   ├── decisiones/                   # ADR-001 a ADR-004
│   ├── propuestas/                   # PRP-001 (Antena/Ubidots), PRP-002 (Modelo Hídrico CC/PMP)
│   └── plantillas/                   # Plantillas estandarizadas de ingeniería
├── scripts/                          # Utilidades CLI (migrar_legacy_v32.py)
├── tests/                            # Suite de 68 pruebas automatizadas (pytest)
├── legacy/aquautp_v3.2/              # Respaldo histórico inmutable de la semilla v3.2
├── docs/                             # Documentación de telemetría y manuales originales
├── main.py                           # Punto de entrada (también ejecutable con python -m aquaterra)
├── pyproject.toml                    # Configuración de empaquetado, pytest y ruff
├── requirements.txt                  # Dependencias de producción
└── requirements-dev.txt              # Dependencias de pruebas y análisis estático
```

---

## 3. Instalación, Ejecución y Pruebas

```powershell
# 1. Posicionarse en el directorio raíz del repositorio
cd C:\Users\danie\Developer\AquaTerra_Matrix

# 2. Activar el entorno virtual (.venv con Python 3.13)
.\.venv\Scripts\Activate.ps1

# 3. Ejecutar la aplicación (importa automáticamente la semilla v3.2 a SQLite en el primer arranque)
python main.py
# o como módulo:
python -m aquaterra

# 4. Ejecutar la suite completa de pruebas y el linter
pytest -v
ruff check .
```

---

## 4. Roadmap de Ingeniería por Versiones

| Versión | Nombre Clave | Alcance Técnico Principal | Estado |
|---|---|---|---|
| **v3.2.0** | `Legacy Seed` | Congelación de respaldo histórico (`legacy/aquautp_v3.2` y tag `v3.2.0-legacy`), entorno `.venv` y autoría unificada. | ✅ **Completado ([REP-000](DEVELOP/reportes/REP-000_migracion_semilla_y_entorno.md))** |
| **v4.0.0a1** | `Core SQLite & Clean Arch` | Re-arquitectura en 4 capas (`aquaterra/`), cierre total de deuda técnica (`DT-01` a `DT-05`), SQLite3 WAL, PBKDF2-SHA256, $VPD$ Tetens, adaptadores IoT base, carpeta `DEVELOP/` y 47 tests en verde. | ✅ **Completado ([REP-001](DEVELOP/reportes/REP-001_arquitectura_v4_y_resolucion_deuda_tecnica.md))** |
| **v4.1.0a1** | `Fase B1 · Esquema v2 e Ingesta Universal` | Migración SQLite `v2` (7 tablas de eventos, calibración con *rollback*, actuadores, riegos programados, clima y copiloto), parsers de Sigatoka (`MUNDONUEVO.csv`/`buffer_sigatoka.json`), Conservación/Páramos, guardia RTC y 57 tests en verde. | ✅ **Completado ([REP-002](DEVELOP/reportes/REP-002_fase_b1_esquema_v2_e_ingesta_universal.md))** |
| **v4.1.0a2** | `Fase B2 · Motor Analítico y Pulso 24h` | Paquete `aquaterra/core/analitica/` (ventana móvil, tasa de secado OLS, correlación de Pearson $r$, rumbo vectorial circular y Pulso 24h de las 4 familias), Window Functions SQLite3, `NodePulseService` y 64 tests en verde. | ✅ **Completado ([REP-003](DEVELOP/reportes/REP-003_fase_b2_motor_analitico_ventana_movil_y_pulso_24h.md))** |
| **v4.1.0a3** | `Fase B3 · Enclavamientos, Salud de Bomba y Planificador` | Paquete modular `aquaterra/core/control/` (`SafetyInterlockEngine` de 5 candados, diagnóstico de bomba con modo `SIN_SENSOR_ACTUADOR` hoy y vibración/caudal a futuro, incidencia $\Delta\theta_A/\Delta\theta_B$ y recomendador proactivo), `DecisionAndControlService` y 68 tests en verde. | ✅ **Completado ([REP-004](DEVELOP/reportes/REP-004_fase_b3_enclavamientos_salud_bomba_e_incidencia_riego.md))** |
| **v4.1.0** | `Fases B4..B5 · Exportador, Radar y Copiloto IA` | Exportador ejecutivo `.xlsx` multi-hoja, radar de auto-detección de nodos (`StationDiscoveryService`) y orquestador IA híbrido con copiloto de calibración. | 🚧 **Siguiente ([Brújula B4→B5](DEVELOP/ARQUITECTURA_MAESTRA_BRUJULA.md))** |
| **v5.0.0** | `Matrix Telemetry Hub & UI 5 Pestañas` | Nueva interfaz de 5 módulos, recepción local por antena (**Gateway LoRa 915 MHz / ESP-NOW LR / Broker Mosquitto local**), puente `Store & Forward` a Ubidots y modelo físico CC/PMP. | 📋 **Planificado ([PRP-001](DEVELOP/propuestas/PRP-001_ingesta_antena_lora_mqtt_y_ubidots.md) · [PRP-002](DEVELOP/propuestas/PRP-002_modelo_agronomico_riego_vpd_y_suelo.md))** |

---

**Licencia y Propiedad Intelectual:**  
Desarrollado íntegramente por **Daniel Felipe Duque Lizarralde** — Ingeniería UTP / Ecosistema TerraBit.
