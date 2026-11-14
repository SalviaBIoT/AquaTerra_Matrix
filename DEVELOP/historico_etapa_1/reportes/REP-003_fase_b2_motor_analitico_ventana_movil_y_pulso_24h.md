# REP-003: Fase B2 — Motor Analítico de Series Temporales, Ventana Móvil SQLite y Pulso 24h por Familia

- **Fecha:** `2026-11-13`
- **Versión:** `v4.1.0a2`
- **Rama:** `develop`
- **Autor:** Daniel Felipe Duque Lizarralde

---

## 1. Resumen Ejecutivo

Se ejecutó completamente la **Fase B2** definida en la [Brújula Maestra de Arquitectura (`ARQUITECTURA_MAESTRA_BRUJULA.md`)](../ARQUITECTURA_MAESTRA_BRUJULA.md), implementando el paquete de analítica pura `aquaterra/core/analitica/` (cero I/O), las **Window Functions nativas en C de SQLite3** dentro de `RepositorioLecturas` y el servicio de aplicación `NodePulseService` (`aquaterra/application/pulso_servicio.py`) cableado en `Contenedor`. El sistema ahora calcula ventanas móviles (`30m`, `1h`, `6h`, `24h`, `7d`), tasas de secado edáfico ($\Delta\theta/\Delta t$), tiempo estimado hasta estrés hídrico ($t_{\text{crit}}$), correlaciones bivariadas de Pearson ($r$), promedios vectoriales circulares de dirección del viento ($\operatorname{atan2}$) y un diagnóstico determinista de **Pulso 24h** especializado para cada una de las 4 familias de estaciones (`TerraBit Nodo INTI`, `InBeersa`, `Sigatoka` y `Conservación Polylepis/Páramos`).

---

## 2. Mapeo de Cambios por Capa

| Capa / Archivo | Cambio Implementado | Justificación Técnica / Agronómica |
|---|---|---|
| `aquaterra/__init__.py` | Incremento de `__version__` a `"4.1.0a2"`. | Segundo hito del Backend v4.1 sobre la base de `v4.1.0a1`. |
| `aquaterra/core/analitica/series.py` | Implementación de `PuntoVentanaMovil`, `calcular_ventana_movil_memoria`, `tasa_cambio_por_hora` (OLS), `tiempo_hasta_umbral_horas`, `correlacion_bivariada` (Pearson $r$) y `promedio_vectorial_grados`. | Algoritmos matemáticos y físicos puros en Python sin dependencias de I/O ni `pandas`. |
| `aquaterra/core/analitica/pulso.py`<br/>`aquaterra/core/analitica/__init__.py` | Implementación de `construir_resumen_pulso_24h` e indicadores especializados (`IndicadoresPulsoInti`, `IndicadoresPulsoInBeersa`, `IndicadoresPulsoSigatoka`, `IndicadoresPulsoConservacion`). | Materializa el Nivel 3 garantizado del Riesgo 1 (diagnóstico experto determinista 100 % offline). |
| `aquaterra/infrastructure/db/repositorios.py` | Adición de `serie_rango()`, `series_estacion_rango()`, `serie_ventana_movil()` en `RepositorioLecturas` y filtro `hasta_epoch` en `RepositorioEventosEstacion.listar()`. | Resuelve el Riesgo 5 ejecutando `AVG/MIN/MAX OVER (ORDER BY ts_epoch RANGE BETWEEN ? PRECEDING AND CURRENT ROW)` en SQLite3. |
| `aquaterra/application/pulso_servicio.py`<br/>`aquaterra/application/contenedor.py`<br/>`aquaterra/application/__init__.py` | Creación de `NodePulseService` (`obtener_pulso_24h`, `consultar_ventana_movil`, `comparar_variables`) e inyección en `Contenedor.pulso`. | Orquesta lecturas y eventos de estación para las Pestañas 1 (*Pulso 24h*) y 2 (*Laboratorio Analítico*). |
| `tests/test_analitica_y_pulso.py` | 7 pruebas automatizadas nuevas cubriendo ventana móvil SQLite vs memoria, tasa de secado, correlación de Pearson, rumbo circular y Pulso 24h de las 4 familias. | Garantiza paridad numérica exacta y detección de alertas críticas por ecosistema. |

---

## 3. Detalle Técnico y Científico Implementado

### 3.1. Ventanas Móviles en SQLite3 y Analítica de Series (`series.py` & `repositorios.py`)

1. **Window Functions en C de SQLite3 (Riesgo 5):**
   - `RepositorioLecturas.serie_ventana_movil()` delega el cálculo de `media_movil`, `min_movil` y `max_movil` al motor C de SQLite usando `WINDOW w AS (ORDER BY ts_epoch RANGE BETWEEN ? PRECEDING AND CURRENT ROW)` sobre el índice compuesto `ix_lecturas_estacion_var_ts`, excluyendo automáticamente lecturas con `calidad >= 2`.
   - `calcular_ventana_movil_memoria()` provee el equivalente exacto $O(N)$ con `collections.deque` para evaluación en memoria.
2. **Tasa de Secado Edáfico ($\Delta\theta/\Delta t$) y Tiempo hasta Estrés ($t_{\text{crit}}$):**
   - `tasa_cambio_por_hora()` ajusta una regresión lineal por mínimos cuadrados ordinarios (OLS) expresada en $\text{unidad}/\text{h}$.
   - `tiempo_hasta_umbral_horas()` proyecta en cuántas horas el sustrato alcanzará el umbral crítico si mantiene la pendiente actual de secado.
3. **Correlación Bivariada de Pearson ($r$) y Rumbo Vectorial Circular:**
   - `correlacion_bivariada()` alinea temporalmente dos series con tolerancia configurable al *jitter* de muestreo (`tolerancia_seg = 300`), calcula $r \in [-1, 1]$, la pendiente $\Delta Y / \Delta X$ y su clasificación (`fuerte_positiva`, `fuerte_negativa`, `moderada_*`, `debil_o_nula`).
   - `promedio_vectorial_grados()` aplica $\operatorname{atan2}(\overline{\sin\theta}, \overline{\cos\theta}) \bmod 360^\circ$, resolviendo la discontinuidad norte ($350^\circ$ y $10^\circ$ promedian $0^\circ$, no $180^\circ$).

### 3.2. Síntesis de Pulso 24h por Familia de Estación (`pulso.py` & `NodePulseService`)

- **🌱 TerraBit Nodo INTI (`IndicadoresPulsoInti`):** Calcula `tasa_secado_suelo_a_pct_h`, diferencial entre horizontes ($\theta_A - \theta_B$), horas acumuladas en estrés evaporativo ($VPD > 1.6\text{ kPa}$) y riesgo fúngico ($VPD < 0.4\text{ kPa}$), tiempo restante hasta estrés ($t_{\text{crit}}$) y tensión de batería.
- **🐝 InBeersa (`IndicadoresPulsoInBeersa`):** Evalúa homeostasis térmica del nido de *Melipona eburnea* ($28.0 \le \overline{T_{\text{int}}} \le 32.0\,^\circ\text{C}$), capacidad de termorregulación ($\overline{\Delta T} = \overline{T_{\text{int}} - T_{\text{ext}}}$), desviación estándar térmica ($\sigma$), tasa horaria de actividad en piquera (`PIR/h`) y conteo de grabaciones `.wav` en `eventos_estacion`.
- **🍌 Sigatoka (`IndicadoresPulsoSigatoka`):** Integra horas de humectación foliar, duración continua máxima de hoja mojada (`duracion_humeda_min`), bandera de ventana crítica de infección por *Mycosphaerella fijiensis* ($\ge 360\text{ min}$ o $\ge 6\text{ h}$ bajo régimen higrotérmico favorable), rumbo dominante vectorial del viento y precipitación acumulada en $\text{mm}$.
- **🏔️ Conservación & Páramos (`IndicadoresPulsoConservacion`):** Calcula variación neta del nivel freático ($\Delta h$ en $\text{cm}$), humedad media de turbera (*Sphagnum*), irradiancia solar pico ($\text{W/m}^2$) y balance energético de batería ($\Delta V$).

---

## 4. Pruebas y Verificación

- **Suite `pytest -v`:** `64 passed` (`0` fallos, `0 warnings`), incluyendo las 7 pruebas nuevas de `tests/test_analitica_y_pulso.py`.
- **Linter `ruff check .`:** `All checks passed!` (`0` advertencias o errores).
- **Documentos de referencia:** [ARQUITECTURA_MAESTRA_BRUJULA.md](../ARQUITECTURA_MAESTRA_BRUJULA.md) · [REP-002](REP-002_fase_b1_esquema_v2_e_ingesta_universal.md).

---

## 5. Próximo Paso de Ingeniería

Ejecutar la **Fase B3**: construir `aquaterra/core/control/` con el **Motor de Enclavamientos Duros (`SafetyInterlockEngine` de 5 candados)**, el **Clasificador Mecánico de Vibración de Bomba (RMS/Frecuencia)**, el **Evaluador de Efectividad e Incidencia Post-Riego ($\Delta\theta_A / \Delta\theta_B$)** y el servicio `DecisionAndControlService`.
