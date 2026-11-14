# ADR-001: Adopción de SQLite3 en Modo WAL y Retiro de Pandas del Runtime Principal

- **Estado:** Aceptado e Implementado (`v4.0.0a1`)
- **Fecha:** `2026-11-13`
- **Autor:** Daniel Felipe Duque Lizarralde

---

## 1. Contexto y Problema
En `AquaUTP v3.2`, la persistencia se realizaba sobre dos archivos planos (`data/parcelas.csv` leído y sobrescrito con `pandas.DataFrame.to_csv` y `data/riegos.json` sobrescrito con `json.dump`).
Este enfoque presenta tres limitaciones incompatibles con el **Ecosistema TerraBit**:
1. **Riesgo de Corrupción Total:** Un corte de energía o cierre abrupto a mitad de `to_csv()` o `json.dump()` trunca el archivo completo.
2. **Escalabilidad Nula para Series Temporales:** Una sola estación (**Nodo INTI** o **InBeersa**) muestreando cada 5 minutos genera $288\text{ tramas/día} \times 8\text{ variables} = 2,304\text{ puntos/día}$ ($\sim 840,000\text{ filas/año}$). Cuatro estaciones superan los $3.3\text{ millones de puntos/año}$.
3. **Ausencia de Integridad Referencial:** Permitía anomalías como `DT-01` (renumerar IDs de parcelas dejando huérfano el historial de riegos).

## 2. Decisión
1. Adoptar **SQLite3** (incluido en la librería estándar de Python) configurado en cada conexión (`aquaterra/infrastructure/db/conexion.py`) con:
   - `PRAGMA journal_mode = WAL;` (permite que el futuro daemon de ingesta por antena/MQTT escriba mientras la interfaz gráfica consulta sin bloquearse).
   - `PRAGMA synchronous = NORMAL;`
   - `PRAGMA foreign_keys = ON;`
   - `PRAGMA busy_timeout = 5000;`
2. Modelar las lecturas de sensores en **formato largo (`narrow table`)** en `lecturas_sensor(estacion_id, variable, valor, unidad, ts_epoch, ts_iso, fuente, calidad)` con restricción `UNIQUE (estacion_id, variable, ts_epoch)`.
3. **Retirar `pandas`, `openpyxl` y `tkcalendar` del runtime obligatorio (`requirements.txt`):**
   - Las agregaciones (como `SUM(agua_litros) GROUP BY parcela_id`) las ejecuta el motor C de SQLite en microsegundos, sin cargar `pandas` ($\sim 60\text{ MB}$ en RAM).
   - `ttkbootstrap` ya provee su propio widget `DateEntry` nativo sin requerir `tkcalendar`.

## 3. Consecuencias
- **Positivas:** Arranque más rápido, consumo de memoria reducido, transacciones ACID reales, deduplicación automática entre MicroSD/Ubidots/Antena y cero dependencias externas para la base de datos en Windows o Linux ARM (Raspberry Pi).
- **Compromisos:** Las consultas analíticas se escriben en SQL parametrizado dentro de `repositorios.py` (encapsuladas fuera de la UI).
