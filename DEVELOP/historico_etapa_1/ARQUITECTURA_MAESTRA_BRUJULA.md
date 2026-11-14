# 🧭 Brújula Maestra de Arquitectura e Ingeniería — AquaTerra Matrix (v4.0 $\to$ v5.0 Final)

**Proyecto:** AquaTerra Matrix — Centro Matriz de Administración Ecológica, Agrícola y Bio-IoT  
**Ecosistema:** TerraBit (Nodo INTI · InBeersa · Sigatoka · Conservación Polylepis)  
**Autor y Arquitecto Principal:** Daniel Felipe Duque Lizarralde (Ingeniería Electrónica — UTP)  
**Estado del Documento:** Especificación Maestra Viva (Referencia Obligatoria de Backend y Producto)  
**Última Actualización:** `2026-11-13`

---

## 1. Propósito del Sistema Matriz

**AquaTerra Matrix** es un **Sistema de Soporte a la Decisión Agro-Ecológica (DSS), SCADA Ligero Local-First y Copiloto de Calibración Asistido por IA**, diseñado en Python para operar como el cerebro central de todas las estaciones de hardware embebido (ESP32 / ESP32-S3) del Ecosistema TerraBit.

### Principios Innegociables de Diseño
1. **Backend Primero (*Headless-Ready*):** Toda la ingesta, validación física, cálculo científico, motor de enclavamientos de seguridad y generación de contexto para IA vive en `aquaterra/core`, `aquaterra/infrastructure` y `aquaterra/application`. Puede correr en un servidor sin pantalla (MiniPC / Raspberry Pi en finca) o bajo la interfaz gráfica de escritorio (`aquaterra/ui`).
2. **Polimorfismo de Estación:** El software no está atado a un solo cultivo ni a un solo tipo de nodo. Cada estación declara su `TipoEstacion` y su **Manifiesto de Variables y Capacidades** (sensores activos, actuadores disponibles, artefactos multimedia como audios `.wav` o fotos foliares).
3. **Soberanía de Datos (*Local-First & Offline-First*):** SQLite3 en modo `WAL` es la única fuente de la verdad (*Single Source of Truth*). La nube (Ubidots) y las APIs externas (clima, IA en nube) son espejos o enriquecedores asíncronos; si se corta el Internet durante semanas, la estación base opera al 100%.
4. **La IA Aconseja, la Física y los Enclavamientos Deterministas Deciden:** Ningún modelo de lenguaje (LLM) tiene permiso directo para accionar válvulas o bombas sin pasar por el validador determinista de seguridad (`SafetyInterlockEngine`).

---

## 2. Catálogo Maestro de Variables y Mediciones por Familia de Estación

Ninguna variable medida en el silicio (C++17) queda fuera del esquema de `AquaTerra Matrix`. El modelo híbrido combina `lecturas_sensor` (variables numéricas indexadas por `(estacion_id, variable, ts_epoch)`) con `eventos_estacion` (eventos discretos, estados categóricos como dirección del viento y rutas a archivos `.wav` / `.jpg`).

### 2.1. 🌱 Familia 1: TerraBit Nodo INTI (`terrabit_inti` — Agrotech & Riego de Precisión)
Origen en firmware: `Estacion_TerraBit_Inti/include/globals.h` (`struct DatosNodo`) + Expansión de Control Hidromecánico.

| Variable Canónica | Unidad | Tipo / Rango Físico Válido | Significado Agronómico y Físico |
|---|---|---|---|
| `suelo_a` | `%` | `0.0 .. 100.0` | Humedad volumétrica relativa Horizonte A (raíz activa, 15 cm), calibrada seco/agua + filtro EMA. |
| `suelo_b` | `%` | `0.0 .. 100.0` | Humedad volumétrica relativa Horizonte B (percolación profunda, 30–40 cm), filtro EMA. |
| `temp_raiz` | `°C` | `-10.0 .. 60.0` | Temperatura en zona radicular (sonda impermeable DS18B20). |
| `temp_aire` | `°C` | `-20.0 .. 65.0` | Temperatura del aire en dosel del cultivo. |
| `hum_aire` | `%` | `0.0 .. 100.0` | Humedad relativa del aire en dosel. |
| `presion` | `hPa` | `300.0 .. 1100.0` | Presión barométrica local (corrección altitudinal y tendencia de frente de lluvia). |
| `vpd` | `kPa` | `0.0 .. 10.0` | Déficit de Presión de Vapor (Tetens FAO-56): demanda evaporativa real de la atmósfera. |
| `voltaje` | `V` | `2.5 .. 15.0` | Tensión del banco de energía (celda LiPo/LiFePO4 3.2–4.2 V o batería 12 V). |
| `id_sesion` | `conteo` | `1 .. 65535` | Contador RTC de continuidad; un incremento indica reinicio o brecha $> 46\text{ min}$. |
| `vibracion_bomba_rms` | `g` | `0.0 .. 16.0` | Aceleración RMS en carcasa de motobomba (MPU6050/ADXL345) para diagnóstico mecánico. |
| `vibracion_freq_hz` | `Hz` | `0.0 .. 500.0` | Frecuencia dominante de vibración (detección de cavitación / giro en vacío vs operación nominal). |
| `corriente_bomba_a` | `A` | `0.0 .. 30.0` | Corriente AC/DC consumida por la bomba (pinza SCT-013 / INA219). |
| `caudal_lpm` | `L/min` | `0.0 .. 200.0` | Caudal instantáneo en línea principal de riego. |
| `apertura_valvula_pct` | `%` | `0.0 .. 100.0` | Estado de apertura de electroválvula / válvula motorizada. |

---

### 2.2. 🐝 Familia 2: InBeersa (`inbeersa` — Bio-IoT & Meliponicultura *Melipona eburnea*)
Origen en firmware: `Estacion_InBeersa/include/globals.h` (`struct TelemetriaInBeersa`).

| Variable Canónica | Unidad | Tipo / Rango Físico Válido | Significado Biológico y Bioacústico |
|---|---|---|---|
| `temperatura_interna` | `°C` | `-10.0 .. 60.0` | Temperatura del nido de cría (DHT22 interno; óptimo *M. eburnea*: $28 - 32\,^\circ\text{C}$). |
| `humedad_interna` | `%` | `0.0 .. 100.0` | Humedad relativa dentro de la colmena (maduración de miel en potes). |
| `temperatura_externa` | `°C` | `-20.0 .. 65.0` | Temperatura ambiental exterior al meliponario. |
| `humedad_externa` | `%` | `0.0 .. 100.0` | Humedad relativa ambiental exterior. |
| `delta_temp` | `°C` | `-30.0 .. 40.0` | $\Delta T = T_{\text{interna}} - T_{\text{externa}}$: índice directo de capacidad de termorregulación de la colonia. |
| `vpd_nido` | `kPa` | `0.0 .. 10.0` | Déficit de presión de vapor interno del nido (riesgo de deshidratación de cría). |
| `calidad_aire_adc` | `adc/ppm` | `0.0 .. 4095.0` | Concentración relativa de gases/$\text{CO}_2$/VOCs (MQ-135 con promedio de 8 muestras y EMA $\alpha=0.2$). |
| `actividad_pir` | `evento` | `0 ó 1` | Detección instantánea de tráfico de abejas o intrusos en piquera (GPIO 27). |
| `eventos_pir_total` | `conteo` | `>= 0` | Actividad acumulada de pecoreo/defensa en piquera durante la sesión. |
| `lluvia_evento` | `evento` | `0 ó 1` | Presencia de precipitación en el meliponario. |
| `uptime_seg` | `s` | `>= 0` | Tiempo continuo de operación del nodo. |
| `audio_wav_evento` | `archivo` | Ruta `.wav` + metadatos | Grabación bioacústica I2S DMA (INMP441, PCM 32-bit @ 16 kHz) en `/Audios_Normal` o `/Audios_PIR`. |

---

### 2.3. 🍌 Familia 3: Sigatoka (`sigatoka` — Vigilancia Fitosanitaria y Mojado Foliar)
Origen en firmware: `Estacion_Sigatoka/include/sigatok_types.h` (`struct RegistroCompletoEstacion`).

| Variable Canónica | Unidad | Tipo / Rango Físico Válido | Significado Fitosanitario (*Mycosphaerella fijiensis*) |
|---|---|---|---|
| `lluvia_mm_min` | `mm/min` | `0.0 .. 50.0` | Intensidad de precipitación en la ventana de muestreo (lavado de esporas / salpicadura). |
| `velocidad_viento_ms` | `m/s` | `0.0 .. 60.0` | Velocidad media del viento (dispersión anemófila de ascosporas). |
| `direccion_viento_grados` | `°` | `0.0 .. 360.0` | Rosa de los vientos convertida a acimut (`N=0°, NE=45°, E=90°, SE=135°, S=180°, SW=225°, W=270°, NW=315°`) + etiqueta textual en metadatos. |
| `temp_aire` | `°C` | `-20.0 .. 65.0` | Temperatura ambiente en plantación de musáceas (rango crítico germinación: $25 - 28\,^\circ\text{C}$). |
| `hum_aire` | `%` | `0.0 .. 100.0` | Humedad relativa ambiente (crítico $> 90\%$). |
| `foliar_adc_crudo` | `adc` | `0 .. 4095` | Lectura cruda del sensor de humectación de hoja (trazabilidad de calibración). |
| `foliar_voltaje_ema` | `V` | `0.0 .. 3.3` | Voltaje filtrado por media móvil exponencial (EMA) del sensor foliar. |
| `foliar_humedad_pct` | `%` | `0.0 .. 100.0` | Porcentaje de película de agua libre / rocío sobre la lámina foliar. |
| `hoja_humectada` | `estado` | `0 ó 1` | Bandera binaria: `1` cuando supera el umbral físico de germinación fúngica. |
| `duracion_humeda_min` | `min` | `>= 0` | Minutos continuos acumulados con hoja mojada (variable crítica de infección). |
| `captura_foliar_img` | `archivo` | Ruta `.jpg/.png` | Evidencia visual activada por estado `ACTIVACION_CAMARA`. |

---

### 2.4. 🏔️ Familia 4: Conservación & Páramos (`conservacion` — Expedición Polylepis y Turberas)

| Variable Canónica | Unidad | Tipo / Rango Físico Válido | Significado Eco-Hidrológico |
|---|---|---|---|
| `nivel_freatico_cm` | `cm` | `-200.0 .. 100.0` | Profundidad de la lámina de agua en turbera de páramo. |
| `humedad_turba_a` / `b` | `%` | `0.0 .. 100.0` | Retención hídrica gravimétrica/volumétrica del colchón de *Sphagnum*. |
| `radiacion_solar_wm2` | `W/m²` | `0.0 .. 1500.0` | Irradiancia global incidente en alta montaña. |
| `temp_suelo_paramo` | `°C` | `-15.0 .. 40.0` | Régimen térmico edáfico bajo dosel de *Polylepis*. |
| `temp_aire` / `hum_aire` / `presion` / `vpd` | Estándar | Estándar | Microclima altoandino y gradiente adiabático. |

---

## 3. Auditoría Forense de Riesgos de la Propuesta y Soluciones de Ingeniería

Antes de escribir el nuevo Backend, auditamos los **8 puntos donde nuestra propuesta podría fallar en el mundo real** y definimos la solución técnica exacta:

### Riesgo 1: Dependencia de Internet para la IA y el Clima en Zonas Rurales
- **Modo de fallo:** Estás en una finca o en el páramo sin Internet. El usuario abre la Pestaña 1 (*Resumen IA*) o la Pestaña 3 (*Recomendación de Riego*), el software intenta llamar a la API de Google AI Studio / Gemini o a la API de clima, se congela 30 segundos esperando red y lanza error.
- **Solución de Ingeniería (Arquitectura en Cascada con Degradación Elegante):**
  1. **Caché Meteorológico Local (`pronostico_clima_cache`):** Cada vez que el PC tiene Internet, descarga y guarda en SQLite el pronóstico horario de los próximos 7 días para las coordenadas de cada estación. Si luego vas al campo sin Internet, el motor de decisiones usa el último pronóstico cacheado válido.
  2. **Triple Proveedor de Inteligencia (`OrquestadorIA`):**
     - *Nivel 1 (Online):* **Google Gemini API (AI Studio)** con salida estructurada JSON.
     - *Nivel 2 (Offline Local GPU/CPU):* **Ollama local** (ej. `gemma3:4b` o `llama3.2:3b` corriendo en `localhost:11434`).
     - *Nivel 3 (Garantizado 100% Determinista):* **Motor Experto Basado en Reglas Físicas (`RuleBasedAdvisor`)** escrito en Python puro en `aquaterra/core/agronomia/`. Si no hay Internet ni Ollama instalado, este motor redacta el diagnóstico y las recomendaciones basándose en ecuaciones agronómicas exactas. **El usuario jamás ve una pantalla rota ni un spinner infinito.**

### Riesgo 2: "Alucinaciones" de la IA en Recomendaciones de Riego o Calibración
- **Modo de fallo:** Un LLM sugiere regar `2,000 Litros` en una parcela de `20 m²` (inundándola) o cambiar el umbral de suelo a un valor absurdo como `-10%` o `110%`.
- **Solución de Ingeniería (Doble Candado Determinista):**
  1. La IA nunca entrega texto libre para ejecutar acciones; entrega un objeto estructurado `PropuestaAccion` que es validado inmediatamente por `SafetyInterlockEngine`.
  2. Todo parámetro de calibración tiene **cotas duras físicas** (`MIN_UMBRAL = 10%`, `MAX_UMBRAL = 90%`, `MAX_CAMBIO_POR_CALIBRACION = ±15%`). Si la IA propone algo fuera de rango, el motor lo recorta (*clamp*) o lo rechaza explicando el motivo.

### Riesgo 3: Falsos Positivos o Falla del Sensor de Vibración de la Bomba
- **Modo de fallo:** El sensor de vibración (MPU6050) en la bomba se suelta del chasis, o pasa un tractor cerca generando vibración ambiental, o aún no está instalado en una parcela que solo tiene electroválvula por gravedad.
- **Solución de Ingeniería:**
  - En la configuración de cada parcela/estación se define el **`ModoVerificacionRiego`**:
    - `SIN_SENSOR_ACTUADOR` (solo mando lógico, para riego por gravedad o fase inicial).
    - `VIBRACION_RMS` (verifica que $a_{\text{rms}}$ suba sobre el umbral basal $\mu_{\text{reposo}} + 3\sigma$ cuando el relé se activa, y que no supere el techo de cavitación $a_{\text{max}}$).
    - `CORRIENTE_O_CAUDAL` (si se usa pinza amperimétrica o caudalímetro).
    - `IMPACTO_SUELO_DIFERIDO` (incluso sin sensor en la bomba, el sistema verifica a los 30–45 minutos si `suelo_a` subió al menos $+\Delta\theta_{\text{min}}$; si no subió, levanta alerta de *"Riego sin respuesta en suelo: posible fallo de bomba, válvula cerrada o tubería rota"*).

### Riesgo 4: Variables No Numéricas (Dirección de Viento `NE`, Rutas de Audio `.wav`, Fotos)
- **Modo de fallo:** La tabla actual `lecturas_sensor` tiene `valor REAL NOT NULL`. ¿Dónde guardamos `"direccion_viento": "NE"` de **Sigatoka** o la ruta `"Audios_PIR/pir_0042.wav"` de **InBeersa**?
- **Solución de Ingeniería:**
  1. Para **dirección de viento**: convertimos el rumbo cardinal a grados acimutales numéricos (`0..360°`) en `lecturas_sensor` (lo que permite promediar vectorialmente con $\arctan2(\overline{\sin\theta}, \overline{\cos\theta})$), y además creamos la tabla **`eventos_estacion`** para eventos discretos, alertas de nodo y archivos multimedia (`.wav`, `.jpg`).

### Riesgo 5: Cuello de Botella al Calcular Ventanas Móviles sobre Millones de Datos
- **Modo de fallo:** Cuando tengas 1 año de datos (3 millones de filas) y el usuario mueva el selector de ventana móvil en la Pestaña 2, hacer el cálculo en bucles de Python sobre toda la tabla congelaría la interfaz.
- **Solución de Ingeniería:**
  - Usar **Window Functions nativas de SQLite3 (escritas en C):**
    `AVG(valor) OVER (ORDER BY ts_epoch RANGE BETWEEN 3600 PRECEDING AND CURRENT ROW)`
    junto con el índice compuesto `ix_lecturas_estacion_var_ts (estacion_id, variable, ts_epoch)`. SQLite calcula la media móvil, el mínimo móvil y el máximo móvil en menos de `15 ms` directamente desde el disco.

### Riesgo 6: Reloj Desconfigurado en Nodos sin Batería RTC (`1970-01-01` o `2000-01-01`)
- **Modo de fallo:** Si a un nodo en campo se le agota la pila CR2032 del DS3231/DS1307 y no alcanza WiFi para NTP, guarda fechas en el año `2000` o `1970`. Si esas fechas entran sin filtro, dañan el eje X de todas las gráficas y la ventana móvil.
- **Solución de Ingeniería (Guardia de Sanidad Temporal en Ingesta):**
  - Toda lectura con `ts_epoch < 1704067200` (`2024-01-01T00:00:00Z`) o en el futuro (`> ahora + 1 hora`) se marca con `calidad = 2` (reloj desincronizado) y se encola en una bandeja de **"Tramas con Reloj Desfasado (Reparables)"**, permitiendo que el usuario les asigne la fecha de descarga si conoce cuándo se inició la sesión (`id_sesion`).

### Riesgo 7: Bloqueo de la Interfaz (UI Freeze) Durante Sincronización, Exportación Excel o Consulta IA
- **Modo de fallo:** `tkinter` corre en un solo hilo. Si una consulta a la IA o una descarga de Ubidots tarda 3 segundos en el hilo principal, la ventana dice *"No responde"* en Windows.
- **Solución de Ingeniería:**
  - El Backend expone un **Ejecutor de Tareas en Segundo Plano (`concurrent.futures.ThreadPoolExecutor`)**. Cada trabajador abre su propia conexión SQLite de corta duración (seguro gracias a `WAL` + `busy_timeout=5000`) y devuelve el resultado al hilo de la UI mediante `raiz.after()`.

### Riesgo 8: Sobreescritura Accidental en la Auto-Recalibración del Chatbot
- **Modo de fallo:** Un operador novato acepta una sugerencia en el chat y descalibra un nodo crítico sin saber cómo volver atrás.
- **Solución de Ingeniería (Versionado de Calibración con Rollback en 1 Clic):**
  - Ningún parámetro de calibración se sobrescribe destructivamente. La tabla `calibraciones_nodo` funciona como una pila de versiones inmutables (`version`, `parametros_json`, `motivo`, `autor`, `ts_iso`, `activa`). Volver a la calibración anterior es un simple cambio de puntero en 1 clic.

---

## 4. Arquitectura de los 6 Módulos del Aplicativo y Sus Motores de Backend

### Módulo 0: Radar de Estaciones y Auto-Detección (`StationDiscoveryService`)
- **Detectores automáticos (en orden de prioridad):**
  1. **Detector USB/Serial y Unidades Removibles:** Detecta si insertaste una tarjeta MicroSD con `/data.csv` o `/data.json`, o un Gateway ESP32 por USB.
  2. **Detector LAN / SoftAP (`192.168.4.1` / `inbeersa.local`):** Sondeo no bloqueante de 400 ms para saber si el portátil está conectado directamente al WiFi de una estación en campo.
  3. **Priorizador por Criticidad:** Ordena todas las estaciones registradas poniendo primero las que tienen alertas activas (estrés hídrico, hoja humectada prolongada en Sigatoka, anomalía térmica en InBeersa o batería baja).
- **Buscador Puntual:** Filtrado instantáneo por código, nombre, tipo de ecosistema (`Agrotech`, `Meliponario`, `Fitosanitario`, `Conservación`) o parcela asociada.

---

### Módulo 1 (Pestaña 1): Pulso del Nodo y Síntesis Ejecutiva (`NodePulseService`)
- **Calculador Determinista de Resumen (`Resumen24h`):**
  - Para cada variable activa de la estación: último valor, tendencia ($\uparrow / \downarrow / \rightarrow$), media 24h, mínimo, máximo y completitud de muestreo ($\text{muestras recibidas} / 288$).
  - Indicadores derivados específicos por tipo de estación:
    - **Nodo INTI:** Tasa de secado edáfico ($\Delta\theta / \Delta t$ en $\%/\text{h}$), diferencia superficial-profunda ($\theta_A - \theta_B$) y horas en estrés de $VPD$.
    - **InBeersa:** Estabilidad de termorregulación ($\overline{\Delta T}$), índice de actividad en piquera (eventos PIR/hora) y conteo de grabaciones bioacústicas.
    - **Sigatoka:** Horas acumuladas de humectación foliar continua y alerta de ventana de infección fúngica.
    - **Conservación:** Variación de nivel freático y balance energético solar de la batería.
- **Generador de Parte Ejecutivo IA:** Toma el `Resumen24h` y produce un diagnóstico ejecutivo claro (vía Gemini / Ollama / Motor Experto Offline).

---

### Módulo 2 (Pestaña 2): Laboratorio Analítico, Ventana Móvil y Exportador `.xlsx` (`AnalyticsAndExportService`)
- **Consultor de Series con Ventana Móvil:**
  - Rango de fechas arbitrario (`desde`, `hasta`).
  - Cálculo en SQLite de serie cruda + **media móvil (`rolling_mean`)**, **mínimo móvil (`rolling_min`)** y **máximo móvil (`rolling_max`)** para ventanas configurables (`30m`, `1h`, `6h`, `24h`, `7d`).
- **Comparador Bivariado ($Y_1$ vs $Y_2$):**
  - Cruce temporal de cualesquiera dos variables de la estación (con coeficiente de correlación de Pearson $r$ y superposición de eventos de riego/lluvia/PIR).
- **Exportador Profesional Multi-Hoja (`.xlsx` y `.csv`):**
  - Genera archivos `.xlsx` listos para entregar a clientes o grupos de investigación con 3 hojas:
    1. `1_Ficha_y_Resumen`: Metadatos de la estación, estadísticas por variable (media, mín, máx, desviación estándar) y diagnóstico del periodo.
    2. `2_Series_Temporales`: Tabla limpia en formato ancho (una columna por variable con su unidad) + columnas de media móvil.
    3. `3_Eventos_y_Riegos`: Historial de riegos, alertas y eventos del periodo.

---

### Módulo 3 (Pestaña 3): Orquestador de Decisiones, Riego Proactivo y Salud de Bomba (`DecisionAndControlService`)
- **Motor Proactivo de Recomendación:**
  - Cruza el estado actual del suelo/planta + la pendiente de secado ($\Delta\theta/\Delta t$) + el pronóstico meteorológico (`probabilidad_lluvia_pct`, `lluvia_esperada_mm`, `et0_mm`).
  - Calcula el **Tiempo Estimado hasta Estrés Hídrico ($t_{\text{crit}}$)**: cuántas horas faltan para que la humedad toque el umbral crítico si no llueve ni se riega.
- **Motor de Enclavamientos Duros (`SafetyInterlockEngine`):**
  - Evalúa 5 candados antes de autorizar cualquier apertura de válvula:
    1. `CANDADO_LLUVIA_ACTIVA`: Si está lloviendo o el pronóstico inmediato supera el umbral de precipitación efectiva, bloquea o limita el porcentaje máximo de apertura.
    2. `CANDADO_SATURACION`: Si $\theta_{\text{actual}} \ge \theta_{CC}$ (Capacidad de Campo), impide regar.
    3. `CANDADO_VOLUMEN_MAXIMO`: Limita los litros máximos por aplicación según el área y textura de la parcela.
    4. `CANDADO_ENERGIA_NODO`: Verifica que `voltaje >= voltaje_minimo_actuacion`.
    5. `CANDADO_SALUD_BOMBA`: Si el último ciclo registró `ALERTA_CAVITACION_VACIO` o `FALLO_NO_ARRANCO`, exige confirmación de mantenimiento antes de reintentar.
- **Evaluador de Salud de Bomba y Efectividad Post-Riego:**
  - Clasifica la telemetría de la bomba (`vibracion_bomba_rms`, `vibracion_freq_hz`, `corriente_bomba_a`) en: `NOMINAL`, `SIN_TELEMETRIA`, `FALLO_NO_ARRANCO`, `CAVITACION_O_VACIO`, `SOBRECARGA_MECANICA`.
  - Calcula la **Incidencia Real del Riego**: $\Delta\theta_A = \theta_A(t_0 + 45\text{ min}) - \theta_A(t_0)$ y $\Delta\theta_B$, calificando cada riego histórico como `EFECTIVO`, `INFILTRACION_PARCIAL`, `EXCESO_PERCOLACION` (cuando sube demasiado $\theta_B$) o `SIN_RESPUESTA_EN_SUELO`.
- **Calendario de Riegos Programados:** Cola de riegos futuros sugeridos o programados, reevaluados dinámicamente si cambia el clima.

---

### Módulo 4 (Pestaña 4): Copiloto de Calibración y Soporte Conversacional (`CalibrationCopilotService`)
- **Inyección Automática de Contexto Técnico:**
  - Cuando el usuario escribe un reporte de campo (ej. *"la última vez regué pero se nos pasó la mano y quedó encharcado"*), el servicio empaqueta automáticamente:
    - Los últimos eventos de riego con su incidencia $\Delta\theta_A$ y $\Delta\theta_B$.
    - Los parámetros vigentes de calibración de la estación/parcela (`umbral_disparo_pct`, `capacidad_campo_pct`, `punto_marchitez_pct`, `litros_max_m2`, `adc_seco_a`, `adc_agua_a`).
- **Diagnóstico + Propuesta de Ajuste Parametrizada:**
  - El copiloto devuelve:
    1. Explicación técnica de por qué ocurrió la discrepancia (p. ej. percolación profunda detectada en `suelo_b` o sobreestimación de $\theta_{CC}$).
    2. Un diccionario de **Ajustes Propuestos** (`{"capacidad_campo_pct": 65.0, "umbral_disparo_pct": 38.0}`) validado dentro de cotas seguras.
  - Al aprobar el ajuste, se crea una nueva versión en `calibraciones_nodo` con trazabilidad completa y opción de *rollback*.

---

### Módulo 5 (Pestaña 5): Centro de Enlace, Ingesta y Flota (`IngestAndFleetService`)
- Gestión de alta y configuración de estaciones (`Nodo INTI`, `InBeersa`, `Sigatoka`, `Conservación`) y su vínculo con parcelas.
- Importación unificada desde MicroSD (`/data.csv`, `/data.json`, CSV de Sigatoka) con reporte de muestras nuevas vs deduplicadas.
- Sincronización bajo demanda y periódica con **Ubidots** y monitor de puerto Serial/MQTT local para la antena receptora.

---

## 5. Evolución del Esquema SQLite (`Migración 002` Planificada)

Sobre las 6 tablas actuales de `Migración 001` (`usuarios`, `estaciones`, `parcelas`, `eventos_riego`, `lecturas_sensor`, `auditoria`), la `Migración 002` añadirá:

1. **`eventos_estacion`**: Para datos no escalares y eventos discretos (`estacion_id`, `tipo_evento`, `valor_texto`, `archivo_ruta`, `metadatos_json`, `ts_epoch`, `ts_iso`) — almacena dirección de viento, capturas de cámara de Sigatoka y rutas de audios `.wav` de InBeersa.
2. **`calibraciones_nodo`**: Versionado de parámetros agronómicos, físicos y de sensores por estación/parcela (`version`, `parametros_json`, `motivo`, `autor_id`, `activa`, `creado_en`).
3. **`salud_actuadores_log`**: Telemetría de verificación de bombas y válvulas asociada a cada evento de riego (`evento_riego_id`, `vibracion_rms_g`, `vibracion_freq_hz`, `corriente_a`, `caudal_lpm`, `apertura_max_pct`, `diagnostico_mecanico`).
4. **`incidencia_riego`**: Evaluación post-riego (`evento_riego_id`, `humedad_a_antes`, `humedad_a_despues`, `humedad_b_antes`, `humedad_b_despues`, `efectividad`, `observaciones`).
5. **`riegos_programados`**: Cola de riegos futuros (`parcela_id`, `ts_programado_epoch`, `ts_programado_iso`, `litros_propuestos`, `apertura_max_pct`, `origen`, `estado`, `motivo_bloqueo`).
6. **`pronostico_clima_cache`**: Caché local de pronóstico meteorológico por estación (`estacion_id`, `ts_objetivo_epoch`, `temp_c`, `lluvia_prob_pct`, `lluvia_mm`, `et0_mm`, `actualizado_en`).
7. **`conversaciones_copiloto`**: Historial de consultas de soporte, diagnósticos y propuestas de recalibración generadas.

---

## 6. Orden de Implementación del Backend (Fases B1 $\to$ B5)

| Fase | Nombre | Entregables de Código y Pruebas (`pytest`) |
|---|---|---|
| **Fase B1** | **Esquema SQLite v2 + Ingesta Sigatoka/Eventos** | `Migración 002` en `esquema.py`, repositorios de eventos/calibración/actuadores, y `parsear_csv_sigatoka()` en `iot_ingest/adaptadores.py`. |
| **Fase B2** | **Motor Analítico, Ventana Móvil y Pulso 24h** | `aquaterra/core/analitica/` (ventanas móviles, tasa de secado $\Delta\theta/\Delta t$, correlación bivariada, resumen 24h por tipo de estación) + `NodePulseService`. |
| **Fase B3** | **Motor de Enclavamientos, Vibración de Bomba e Incidencia de Riego** | `aquaterra/core/control/` (`SafetyInterlockEngine`, clasificador mecánico de vibración RMS/frecuencia, evaluador de efectividad $\Delta\theta$ post-riego y planificador proactivo). |
| **Fase B4** | **Exportador Ejecutivo `.xlsx` Multi-Hoja + Radar de Nodos** | `aquaterra/infrastructure/exportacion/excel_exporter.py` (3 hojas profesionales) + `StationDiscoveryService` (auto-detección y priorización por criticidad). |
| **Fase B5** | **Orquestador IA Híbrido (Gemini / Ollama / Reglas) + Copiloto de Calibración** | `aquaterra/application/copiloto/` (resúmenes ejecutivos, recomendaciones proactivas y recalibración conversacional con *rollback* en 1 clic). |
| **Fase UI** | **Rediseño Visual de las 5 Pestañas + Radar** | Con todo el Backend probado al 100% en `pytest`, montaje de la nueva experiencia visual fluida sobre `aquaterra/ui/`. |
