# ADR-004: Estandarización Temporal Dual (ISO-8601 UTC-05:00 + Unix Epoch)

- **Estado:** Aceptado e Implementado (`v4.0.0a1`)
- **Fecha:** `2026-11-13`
- **Autor:** Daniel Felipe Duque Lizarralde

---

## 1. Contexto
En `v3.2`, las fechas de riego se guardaban como cadenas `MM/DD/YY` (`"11/27/25"`) y horas sin ceros a la izquierda (`"8:00"`), imposibilitando el ordenamiento cronológico directo en texto y causando ambigüedad día/mes.
Por su parte, las estaciones ESP32 del ecosistema trabajan con:
- **Nodo INTI:** RTC DS3231 sincronizado por NTP a hora de Colombia (`UTC-5`), guardando `YYYY/MM/DD HH:MM:SS` en MicroSD y enviando `unixtime()` en segundos (multiplicado por `1000` para milisegundos en Ubidots).
- **InBeersa:** RTC DS1307 sincronizado por NTP a `UTC-5`, guardando `YYYY-MM-DD` y `HH:MM:SS` en `/data.json`.

## 2. Decisión
Centralizar todo el manejo de fechas y horas en `aquaterra/core/tiempo.py`:
1. **Zona Horaria Oficial:** `ZONA_COLOMBIA = timezone(timedelta(hours=-5), name="COT")` (Colombia no utiliza horario de verano, por lo que el desfase fijo `-05:00` es exacto y no requiere la base de datos IANA externa).
2. **Persistencia Dual en Tablas de Eventos y Series Temporales (`eventos_riego`, `lecturas_sensor`):**
   - `ts_iso` (`TEXT`): `YYYY-MM-DDTHH:MM:SS-05:00` (legible para humanos, reportes y auditoría).
   - `ts_epoch` (`INTEGER`): Segundos Unix UTC (óptimo para índices B-Tree de SQLite, consultas por ventana temporal y llave `UNIQUE (estacion_id, variable, ts_epoch)` de deduplicación).

## 3. Consecuencias
- Compatibilidad directa bit a bit con `rtc.now().unixtime()` de los firmwares ESP32 y con los timestamps de Ubidots (`ts_ms // 1000`).
