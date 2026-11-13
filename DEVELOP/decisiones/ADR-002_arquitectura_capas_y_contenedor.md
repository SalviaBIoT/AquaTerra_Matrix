# ADR-002: Arquitectura en 4 Capas, Contenedor de Dependencias y Ventana Raíz Única

- **Estado:** Aceptado e Implementado (`v4.0.0a1`)
- **Fecha:** `2026-11-13`
- **Autor:** Daniel Felipe Duque Lizarralde

---

## 1. Contexto
En `v3.2`, las vistas de interfaz (`views/*.py`) instanciaban directamente `GestorDatos()`, manipulaban `DataFrames` y contenían reglas de negocio mezcladas con callbacks de botones. Además, `main.py` ejecutaba dos bucles `mainloop()` consecutivos sobre ventanas distintas.

Dado que **AquaTerra Matrix** operará tanto como **aplicación de escritorio interactiva** como **servicio local de ingesta de telemetría por antena y sincronización con Ubidots**, la lógica de negocio e ingesta no puede depender de `tkinter`.

## 2. Decisión
Dividir el paquete `aquaterra` en 4 capas con regla estricta de dependencias hacia adentro:
1. **`aquaterra.core` (Dominio + Ciencia Agronómica):** Entidades inmutables (`dataclass(frozen=True, slots=True)`), validadores puros, manejo temporal ISO-8601 y ecuaciones psicrométricas ($VPD$ Tetens) e hídricas. **Prohibido importar `sqlite3` o `tkinter` aquí.**
2. **`aquaterra.infrastructure` (Adaptadores Técnicos):** SQLite WAL (`db/`), hashing criptográfico (`seguridad/`), migrador de semilla v3.2 (`legacy/`) y parsers de telemetría IoT (`iot_ingest/`).
3. **`aquaterra.application` (Casos de Uso):** `ServicioAutenticacion`, `ServicioParcelas`, `ServicioRiego` y `ServicioMonitor`, ensamblados en `Contenedor` (`contenedor.py`). Cada caso de uso valida permisos (`Rol`), abre una transacción atómica (`with self._db:`) y escribe en la tabla `auditoria`.
4. **`aquaterra.ui` (Presentación):** Una sola raíz `ttk.Window` gobernada por `AplicacionMatrix` (`app.py`) que monta y desmonta vistas derivadas de `ttk.Frame`.

## 3. Consecuencias
- El 100% de las reglas agronómicas, de seguridad y de base de datos se prueba en milisegundos con `pytest` sobre `:memory:` sin abrir ventanas.
- El futuro daemon de recepción por antena (`v5.0`) instanciará `construir_contenedor()` directamente sin cargar `tkinter`.
