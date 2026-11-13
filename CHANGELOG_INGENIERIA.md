# Bitácora Técnica de Ingeniería: AquaTerra Matrix (Python Architecture)

**Proyecto:** Software Matriz de Administración Ecológica, Agrícola y Bio-IoT (Evolución de AquaUTP v3.2)  
**Ecosistema:** TerraBit / InBeersa / Sigatoka / Conservación Polylepis (Semilleros Kilby & MUCEM — UTP)  
**Autor & Arquitecto Principal:** Daniel Felipe Duque Lizarralde  

---

## [v3.2.0-legacy] - 2026-11-12: Fase 0 — Migración a Developer, Línea Base Git y Auditoría Forense

### 1. Hitos de Infraestructura y Despliegue (Fase 0)
- **Migración Arquitectónica a `C:\Users\danie\Developer\AquaTerra_Matrix`:**
  Se estableció el repositorio oficial dentro del directorio maestro de ingeniería junto a `Estacion_TerraBit_Inti`, `Estacion_InBeersa`, `Estacion_Sigatoka` y `TerraBit_Core`.
- **Preservación de Línea Base (`legacy/aquautp_v3.2` y Tag `v3.2.0-legacy`):**
  Se congeló una copia íntegra de referencia de la versión semilla v3.2 antes de iniciar las refactorizaciones estructurales de la Fase 1.
- **Unificación de Autoría y Liderazgo Técnico:**
  Se independizó el proyecto bajo la autoría exclusiva de **Daniel Felipe Duque Lizarralde**, actualizando los metadatos de interfaz (`views/login_ui.py`) y el registro maestro de operadores (`data/usuarios.json`).
- **Aislamiento de Entorno Virtual (`.venv`) y Dependencias (`requirements.txt`):**
  Se incorporó explícitamente `Pillow>=10.3.0` (requerido por `PIL.Image` e `ImageTk` en `login_ui.py` pero omitido en el `requirements.txt` original) y se configuró el entorno virtual sobre **Python 3.13 (64-bit)**.
- **Integración con el Centro de Operaciones (`0. ESTACIONES & DESARROLLO`):**
  Creación de enlace simbólico de directorio (*Directory Junction*) y archivo `.code-workspace` dedicado y transversal.

---

### 2. Diagnóstico Forense de Deuda Técnica en v3.2 (Objetivos de Fase 1)

| ID | Módulo / Archivo | Hallazgo Técnico (Causa Raíz) | Impacto en Producción | Solución Arquitectónica (v3.3 -> v4.0) |
|---|---|---|---|---|
| **DT-01** | `models/data_manager.py`<br/>`eliminar_parcela()` | Las líneas `100-101` ejecutan `tabla_filtrada['id'] = range(1, len(tabla_filtrada) + 1)`. Al borrar una parcela intermedia, todas las parcelas posteriores cambian de `id`. | **Corrupción de Integridad Referencial:** Los registros históricos en `data/riegos.json` quedan apuntando a `id_parcela` desplazados o inexistentes. | Erradicar la renumeración de llaves primarias. Migrar a secuencia autoincremental inmutable (`INTEGER PRIMARY KEY AUTOINCREMENT` en SQLite) con claves foráneas (`FOREIGN KEY`). |
| **DT-02** | `models/data_manager.py`<br/>`data/*.csv`, `data/*.json` | Persistencia acoplada a reescritura completa de archivos planos (`to_csv` y `json.dump` de toda la lista en cada inserción). Fechas en formato ambiguo `MM/DD/YY` (`11/27/25`). | **Inviabilidad para Series Temporales IoT:** Con 288 muestras/día por estación (cadencia de 5 min en Nodo INTI e InBeersa), reescribir JSON/CSV planos degrada el I/O y arriesga pérdida total ante corte de energía. | Migrar la capa de persistencia a **SQLite3 con modo `WAL` (Write-Ahead Logging)** y estandarizar marcas temporales en **ISO-8601 (`YYYY-MM-DDTHH:MM:SS-05:00`)** + Unix Epoch. |
| **DT-03** | `views/parcelas_ui.py`<br/>`_accion_actualizar()` | A diferencia de `_accion_guardar()`, el método `_accion_actualizar()` (líneas `227-246`) no valida campos vacíos ni verifica que `area` sea convertible a `float`. | **Fallo Silencioso y Excepciones:** Si el usuario introduce texto no numérico en `Área` al actualizar, `float(datos_nuevos['area'])` lanza `ValueError` en `data_manager.py`. | Extraer un validador de dominio centralizado (`validar_datos_parcela()`) reutilizado tanto en creación como en actualización antes de tocar la capa de datos. |
| **DT-04** | `views/monitor_ui.py`<br/>`_grafico_humedad_actual()`<br/>`_grafico_consumo_agua()` | Invocación de `plt.subplots()` dentro del estado global de `pyplot` sin liberar figuras previas (`plt.close(figura)`) al cerrar `VentanaMonitor`. | **Fuga de Memoria (Memory Leak):** Cada apertura del monitor acumula objetos `Figure` en la memoria RAM del proceso Python y contamina estados de ejes (`plt.xticks`). | Instanciar objetos ` matplotlib.figure.Figure` de forma orientada a objetos (sin máquina de estados `pyplot`) o cerrar explícitamente las figuras en `_al_cerrar_ventana()`. |
| **DT-05** | `main.py`, `views/login_ui.py`,<br/>`views/dashboard_ui.py`,<br/>`data/usuarios.json` | 1) Se invoca `mainloop()` dos veces (`app_login.ejecutar()` sobre `ttk.Window` y luego `app_dashboard.ejecutar()` sobre un `ttk.Toplevel` huérfano).<br/>2) Contraseñas almacenadas en texto plano (`"pass": "1234"`). | **Inestabilidad de Eventos Tk y Vulnerabilidad de Seguridad:** Doble bucle de eventos en Tcl/Tk genera cierres fantasmas; credenciales expuestas en texto claro. | Unificar en una sola raíz `ttk.Window` con transición de vistas por `Frame`/controlador, e implementar hashing criptográfico con `hashlib.pbkdf2_hmac('sha256', ...)` + salt. |

---

### 3. Plan de Ejecución Inmediato (Fase 1 -> Fase 2)

1. **Etapa 1A (`v3.3.0-integrity`):**
   - Parche quirúrgico de los 5 puntos de deuda técnica (DT-01 a DT-05) manteniendo 100% operativa la interfaz actual.
2. **Etapa 1B (`v4.0.0-sqlite-core`):**
   - Reestructuración modular limpia:
     - `core/` (modelos de dominio agronómico, cálculo psicrométrico de $VPD$ Tetens, validadores).
     - `infrastructure/` (motor SQLite3 WAL, repositorios transaccionales, ingestadores de `/data.csv` de Nodo INTI y `/data.json` de InBeersa).
     - `ui/` (vistas desacopladas de la persistencia).
3. **Etapa 2 (`v5.0.0-telemetry-hub`):**
   - Recepción local por antena (Gateway Serial/LoRa/ESP-NOW y Broker MQTT Mosquitto local), puente de sincronización con **Ubidots Industrial** y panel de series temporales multi-estación.
