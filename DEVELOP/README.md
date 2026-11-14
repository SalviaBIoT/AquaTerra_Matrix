# Centro de Trazabilidad de Ingeniería (`DEVELOP/`) — AquaTerra Matrix

**Proyecto:** AquaTerra Matrix — Ecosistema TerraBit (Nodo INTI · InBeersa · Sigatoka · Conservación Polylepis)  
**Autor y Arquitecto:** Daniel Felipe Duque Lizarralde  
**Versión Actual:** `v6.0.0` (FastAPI Local-First + React 19 + Mandarino IA Studio)

---

## 1. Estructura Documental

```text
DEVELOP/
├── README.md                                     # Este índice maestro
├── ARQUITECTURA_MAESTRA_BRUJULA.md               # Brújula de dominio agronómico, Bio-IoT y Backend (B1 -> B5)
├── ARQUITECTURA_FRONTEND_V5_MAESTRA.md           # Arquitectura base del App Shell v5.0
├── PLAN_MAESTRO_FRONTEND_V6_ELITE.md             # Plan maestro de evolución hacia Web Local-First v6.0
├── GUIA_INTEGRACION_IA_AISTUDIO_Y_OLLAMA.md      # Manual para conectar Gemini AI Studio y Ollama Local
├── reportes/                                     # Reportes de fases técnicas y diagnóstico del sistema
│   ├── REP-000 .. REP-008                        # Fases 0, Arquitectura v4, B1..B5, Sprint v4.2 y Frontend v5.0
│   └── REPORTE_SISTEMA_Y_PROYECTO_COMPLETO.md    # Fotografía integral de hardware, arquitectura IA y proyecto
├── sprints/                                      # Bitácora secuencial de Sprints v6.0 + Mandarino IA
│   └── SPRINT_01 .. SPRINT_13                    # Concurrencia, FastAPI, React, ECharts, Empaquetado y Mandarino
├── decisiones/                                   # Architecture Decision Records (ADR-001 .. ADR-004)
├── propuestas/                                   # Especificaciones futuras (PRP-001, PRP-002)
└── plantillas/                                   # Plantillas base de propuestas y reportes
```

---

## 2. Fases Fundamentales (`reportes/`)

| ID | Versión | Título | Enlace |
|---|---|---|---|
| **REP-000** | `v3.2.0-legacy` | Migración de Semilla, `.venv` y Línea Base | [Ver reporte](reportes/REP-000_migracion_semilla_y_entorno.md) |
| **REP-001** | `v4.0.0a1` | Arquitectura 4 Capas, SQLite WAL y Cierre DT-01..05 | [Ver reporte](reportes/REP-001_arquitectura_v4_y_resolucion_deuda_tecnica.md) |
| **REP-002** | `v4.1.0a1` | Esquema v2 e Ingesta Universal (4 Familias IoT) | [Ver reporte](reportes/REP-002_fase_b1_esquema_v2_e_ingesta_universal.md) |
| **REP-003** | `v4.1.0a2` | Motor Analítico, Ventana Móvil y Pulso 24h | [Ver reporte](reportes/REP-003_fase_b2_motor_analitico_ventana_movil_y_pulso_24h.md) |
| **REP-004** | `v4.1.0a3` | Enclavamientos (5 Candados), Bomba e Incidencia de Riego | [Ver reporte](reportes/REP-004_fase_b3_enclavamientos_salud_bomba_e_incidencia_riego.md) |
| **REP-005** | `v4.1.0a4` | Exportador `.xlsx` Multi-Hoja y Radar de Nodos | [Ver reporte](reportes/REP-005_fase_b4_exportador_xlsx_y_radar_estaciones.md) |
| **REP-006** | `v4.1.0` | Orquestador IA Híbrido, Copiloto de Calibración y Rollback | [Ver reporte](reportes/REP-006_fase_b5_orquestador_ia_y_copiloto_calibracion.md) |
| **REP-007** | `v4.2.0` | Conectores Ubidots, Open-Meteo, `nRF24L01+` y Notificaciones | [Ver reporte](reportes/REP-007_sprint_v42_conectores_activos_ubidots_clima_nrf24_y_notificaciones.md) |
| **REP-008** | `v5.0.0` | App Shell Híbrido Local-First y Tema Dual | [Ver reporte](reportes/REP-008_frontend_v50_app_shell_hibrido_y_consolidacion.md) |
| **SIS-v6** | `v6.0.0` | Reporte Integral de Sistema, Hardware y Ecosistema | [Ver reporte](reportes/REPORTE_SISTEMA_Y_PROYECTO_COMPLETO.md) |

---

## 3. Sprints v6.0 & Mandarino IA Studio (`sprints/`)

| Sprint | Alcance | Enlace |
|---|---|---|
| **Sprint 01** | Concurrencia SQLite WAL, `.env` y entorno v6 | [SPRINT_01](sprints/SPRINT_01_FASE_0_CONCURRENCIA_Y_ENTORNO.md) |
| **Sprint 02** | API REST FastAPI v6 con autenticación y RBAC | [SPRINT_02](sprints/SPRINT_02_FASE_1_API_FASTAPI.md) |
| **Sprint 03** | Fundación Shell React 19, Vite y Login | [SPRINT_03](sprints/SPRINT_03_FASE_2_FUNDACION_SHELL_LOGIN.md) |
| **Sprint 04** | Radar General, Telemetría ECharts y Parcelas | [SPRINT_04](sprints/SPRINT_04_FASE_3_RADAR_ECHARTS_PARCELAS.md) |
| **Sprint 05** | Control de Riego, Copiloto IA, Hardware y Configuración | [SPRINT_05](sprints/SPRINT_05_FASE_4_CONTROL_COPILOTO_HARDWARE_CONFIG.md) |
| **Sprint 06** | Empaquetado nativo PyWebView, accesos directos e íconos | [SPRINT_06](sprints/SPRINT_06_FASE_5_EMPAQUETADO_NATIVO_E2E.md) |
| **Sprint 07** | Auditoría funcional de sesión, rutas SPA y accesos directos | [SPRINT_07](sprints/SPRINT_07_AUDITORIA_FUNCIONAL_Y_SESION.md) |
| **Sprint 08** | Paridad de contratos API y pruebas Chrome CDP | [SPRINT_08](sprints/SPRINT_08_PARIDAD_CONTRATOS_Y_E2E_CHROME.md) |
| **Sprint 09** | Telemetría normalizada/selector, concurrencia y narrativa IA | [SPRINT_09](sprints/SPRINT_09_TELEMETRIA_CONCURRENCIA_Y_NARRATIVA_IA.md) |
| **Sprint 10** | Nacimiento y estética de **Mandarino IA Studio** | [SPRINT_10](sprints/SPRINT_10_MANDARINO_IA_STUDIO.md) |
| **Sprint 11** | Identidad de Mandarino, diseño en 3 columnas e hilos aislados | [SPRINT_11](sprints/SPRINT_11_IDENTIDAD_MANDARINO_3_COLUMNAS.md) |
| **Sprint 12** | Refactorización modular, `gemini-3.5-flash-lite` y prewarm Ollama | [SPRINT_12](sprints/SPRINT_12_MANDARINO_MODULAR_Y_FLASH_LITE.md) |
| **Sprint 13** | Enlace climático Open-Meteo en Mandarino y preparación pública GitHub | [SPRINT_13](sprints/SPRINT_13_CLIMA_MANDARINO_Y_PUBLICACION_GITHUB.md) |
