# REP-004: Fase B3 — Motor de Enclavamientos Duros, Salud de Bomba (Lista para Futuro) e Incidencia de Riego

- **Fecha:** `2026-11-13`
- **Versión:** `v4.1.0a3`
- **Rama:** `develop`
- **Autor:** Daniel Felipe Duque Lizarralde

---

## 1. Resumen Ejecutivo

Se ejecutó completamente la **Fase B3** definida en la [Brújula Maestra de Arquitectura (`ARQUITECTURA_MAESTRA_BRUJULA.md`)](../ARQUITECTURA_MAESTRA_BRUJULA.md), construyendo el paquete modular `aquaterra/core/control/` (dividido en `enclavamientos.py`, `actuadores.py` y `planificador.py`) y el servicio de aplicación `DecisionAndControlService` (`aquaterra/application/control_servicio.py`) cableado en `Contenedor.control`. La arquitectura fue diseñada para operar **hoy mismo sin motobomba ni sensor de vibración instalados** (`ModoVerificacionRiego.SIN_SENSOR_ACTUADOR` por defecto), dejando simultáneamente habilitada y probada toda la lógica para cuando se integre el hardware hidromecánico (`VIBRACION_RMS` vía MPU6050/ADXL345 o `CORRIENTE_O_CAUDAL`).

---

## 2. Mapeo de Cambios por Capa (Modularización Estricta)

| Capa / Archivo | Cambio Implementado | Justificación Técnica / Agronómica |
|---|---|---|
| `aquaterra/__init__.py` | Incremento de `__version__` a `"4.1.0a3"`. | Tercer corte incremental del Backend v4.1. |
| `aquaterra/core/control/enclavamientos.py` | Implementación de `SafetyInterlockEngine`, `ContextoSeguridadRiego`, `VeredictoEnclavamientos` y `CodigoCandado`. | Evalúa los 5 candados deterministas (lluvia, saturación CC, volumen máximo por textura USDA, tensión de nodo y salud de bomba). |
| `aquaterra/core/control/actuadores.py` | Implementación de `diagnosticar_salud_bomba()`, `UmbralesSaludBomba`, `evaluar_incidencia_riego()` y `ResultadoIncidenciaRiego`. | Soporta operación actual sin sensor de actuador y diagnóstico futuro por vibración RMS/frecuencia, corriente/caudal o impacto diferido en suelo. |
| `aquaterra/core/control/planificador.py`<br/>`aquaterra/core/control/__init__.py` | Implementación de `generar_recomendacion_proactiva()`, `calcular_litros_reposicion()`, `RecomendacionRiego` y `AccionRecomendadaRiego`. | Cruza humedad actual, pendiente de secado ($\Delta\theta_A/\Delta t$), pronóstico de lluvia 24h y `SafetyInterlockEngine`. |
| `aquaterra/infrastructure/db/repositorios.py` | Adición de `ultimo_por_parcela()` en `RepositorioSaludActuadores`. | Permite recuperar el último diagnóstico mecánico de la bomba asociado a una parcela. |
| `aquaterra/application/control_servicio.py`<br/>`aquaterra/application/contenedor.py`<br/>`aquaterra/application/__init__.py` | Creación de `DecisionAndControlService` (`recomendar_riego_parcela`, `programar_riego_validado`, `registrar_verificacion_e_incidencia`) e inyección en `Contenedor.control`. | Orquesta recomendaciones proactivas, cola de riegos con bloqueo automático por *interlock* y auditoría. |
| `tests/test_control_y_decisiones.py` | 4 pruebas integrales cubriendo los 5 candados, los 4 modos de verificación de bomba, las 4 clases de incidencia post-riego y la planificación proactiva. | Verifica recortes de volumen/apertura, posposición por lluvia y transparencia del modo sin bomba. |

---

## 3. Detalle Técnico y Científico Implementado

### 3.1. Motor de 5 Enclavamientos Duros (`enclavamientos.py`)

1. **`CANDADO_LLUVIA_ACTIVA`:** Si la intensidad actual es $\ge 0.15\text{ mm/min}$ o la lluvia pronosticada en 24h es $\ge 10.0\text{ mm}$, bloquea el riego (`apertura_autorizada_pct = 0.0`). Bajo llovizna o probabilidad $\ge 75\%$, recorta la apertura máxima al `50 %`.
2. **`CANDADO_SATURACION`:** Impide regar si $\theta_{\text{actual}} \ge \theta_{CC}$ (`Arenoso = 70%`, `Franco = 80%`, `Arcilloso = 85%` o el valor calibrado en `calibraciones_nodo`).
3. **`CANDADO_VOLUMEN_MAXIMO` (Riesgo 2):** Acota automáticamente el volumen solicitado a la lámina máxima segura por textura (`Arenoso = 4.5 L/m²`, `Franco = 6.0 L/m²`, `Arcilloso = 5.0 L/m²`).
4. **`CANDADO_ENERGIA_NODO`:** Bloquea la actuación si `voltaje < 3.45 V`, evitando *brownout* en el ESP32 al conmutar relés o electroválvulas.
5. **`CANDADO_SALUD_BOMBA` (Adaptado a Hardware Actual y Futuro):**
   - En `ModoVerificacionRiego.SIN_SENSOR_ACTUADOR` (por defecto hoy mientras no exista la motobomba física), el candado permanece transparente y autoriza el mando lógico.
   - En `VIBRACION_RMS` o `CORRIENTE_O_CAUDAL`, bloquea reintentos si el último ciclo registró `FALLO_NO_ARRANCO`, `CAVITACION_O_VACIO` o `SOBRECARGA_MECANICA` sin confirmación de mantenimiento.

### 3.2. Clasificador de Salud de Bomba e Incidencia Post-Riego (`actuadores.py`)

- **`diagnosticar_salud_bomba()`:** Soporta los 4 modos (`SIN_SENSOR_ACTUADOR`, `VIBRACION_RMS`, `CORRIENTE_O_CAUDAL`, `IMPACTO_SUELO_DIFERIDO`).
- **`evaluar_incidencia_riego()`:** Calcula $\Delta\theta_A$ y $\Delta\theta_B$ tras el riego y clasifica el resultado en `SIN_RESPUESTA_EN_SUELO` ($\Delta\theta_A < 2\%$), `INFILTRACION_PARCIAL` ($2\% \le \Delta\theta_A < 5\%$), `EXCESO_PERCOLACION` ($\Delta\theta_B \ge 8\%$ y $\Delta\theta_B > 0.6\,\Delta\theta_A$) o `EFECTIVO`.

### 3.3. Planificador Proactivo (`planificador.py` & `DecisionAndControlService`)

- Emite `NO_REGAR_HUMEDAD_SUFICIENTE`, `POSPONER_POR_LLUVIA` (cuando el pronóstico $\ge 6\text{ mm}$ con probabilidad $\ge 65\%$ suplirá la demanda), `PROGRAMAR_PREVENTIVO` (cuando la tasa de secado $\Delta\theta_A/\Delta t$ llevará la parcela al umbral crítico en $\le 18\text{ h}$), `REGAR_INMEDIATO` o `BLOQUEADO_POR_SEGURIDAD`.

---

## 4. Pruebas y Verificación

- **Suite `pytest -v`:** `68 passed` (`0` fallos, `0 warnings`), incluyendo las 4 pruebas de `tests/test_control_y_decisiones.py`.
- **Linter `ruff check .`:** `All checks passed!`.
- **Documentos de referencia:** [ARQUITECTURA_MAESTRA_BRUJULA.md](../ARQUITECTURA_MAESTRA_BRUJULA.md) · [REP-003](REP-003_fase_b2_motor_analitico_ventana_movil_y_pulso_24h.md).

---

## 5. Próximo Paso de Ingeniería

Ejecutar la **Fase B4**: construir el **Exportador Ejecutivo `.xlsx` Multi-Hoja y `.csv`** (`aquaterra/infrastructure/exportacion/`) junto con el **Radar de Estaciones y Auto-Detección (`StationDiscoveryService`)** que prioriza nodos por criticidad y detecta unidades MicroSD / tramas locales.
