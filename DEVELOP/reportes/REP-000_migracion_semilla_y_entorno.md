# REP-000: Fase 0 — Migración de Semilla v3.2, Entorno Virtual y Línea Base en GitHub

- **Fecha:** `2026-11-12`
- **Versión:** `v3.2.0-legacy` (Commit `e59fe71`)
- **Rama:** `main` (Tag `v3.2.0-legacy`)
- **Autor:** Daniel Felipe Duque Lizarralde

---

## 1. Objetivo del Corte
Trasladar el proyecto base **AquaUTP v3.2** desde la carpeta documental de asignaturas (`C:\Users\danie\Documents\1. AgroProyectos\3. Software AQUA UTP\AquaUTPFinal (1)`) hacia la arquitectura formal de ingeniería en `C:\Users\danie\Developer\AquaTerra_Matrix`, garantizando:
1. Preservación intacta de la versión original (tanto en carpeta `legacy/aquautp_v3.2` como en tag Git `v3.2.0-legacy` y en `Archivos_Historicos`).
2. Independencia de autoría bajo el liderazgo exclusivo de **Daniel Felipe Duque Lizarralde**.
3. Configuración de entorno virtual reproducible (`.venv` sobre Python 3.13) y validación de ejecución sin errores antes de refactorizar la arquitectura.

---

## 2. Cambios Ejecutados

| Componente | Acción Realizada | Verificación |
|---|---|---|
| **Estructura en `Developer/`** | Creación de `C:\Users\danie\Developer\AquaTerra_Matrix` e inicialización de Git conectado a `https://github.com/dfelipeduquel/AquaTerra_Matrix`. | Push exitoso de `main` y tag `v3.2.0-legacy`. |
| **Preservación Histórica** | Copia congelada en `legacy/aquautp_v3.2/` y en `C:\Users\danie\Developer\Archivos_Historicos\AquaUTP_v3.2_Legacy`. | Archivos verificados sin `.pyc` ni basura de compilación. |
| **Dependencias (`requirements.txt`)** | Se agregó `Pillow>=10.3.0` (omitido en el archivo original pese a ser requerido por `views/login_ui.py`). | Instalación limpia en `.venv` (Python 3.13). |
| **Accesos Rápidos (Junctions)** | Enlaces simbólicos creados en `0. ESTACIONES & DESARROLLO` y en `3. Software AQUA UTP`, más actualización de `Ecosistema_Estaciones.code-workspace`. | Navegación directa desde VS Code y explorador. |

---

## 3. Hallazgos de la Auditoría Forense (Entrada para Fase 1)
1. **DT-01 (Crítico):** `GestorDatos.eliminar_parcela()` reasigna `tabla_filtrada['id'] = range(1, len(tabla_filtrada) + 1)`, corrompiendo las llaves foráneas en `riegos.json`.
2. **DT-02 (Crítico):** Archivos CSV/JSON planos reescritos por completo en cada operación y fechas en formato ambiguo `MM/DD/YY`.
3. **DT-03 (Alto):** `VentanaParcelas._accion_actualizar()` no valida que el nombre no esté vacío ni que el área sea un número válido antes de invocar a la capa de datos.
4. **DT-04 (Medio):** `VentanaMonitor` crea figuras con `plt.subplots()` sin liberarlas al cerrar la ventana, provocando fuga acumulativa de memoria RAM.
5. **DT-05 (Alto):** Doble invocación a `mainloop()` (`VentanaLogin` + `VentanaDashboard`) y almacenamiento de contraseñas en texto plano en `data/usuarios.json`.
