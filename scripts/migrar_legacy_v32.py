"""Migración manual de la semilla AquaUTP v3.2 a una base SQLite.

Normalmente NO hace falta: la aplicación siembra la base automáticamente en su
primer arranque. Este script sirve para auditar la migración o generar una base
en otra ruta (p. ej. para la estación base de campo).

Uso:
    .\\.venv\\Scripts\\python.exe scripts\\migrar_legacy_v32.py --db data\\runtime\\prueba.db
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aquaterra.config import Configuracion  # noqa: E402
from aquaterra.infrastructure.db import abrir_conexion, aplicar_migraciones  # noqa: E402
from aquaterra.infrastructure.legacy.migrador_v32 import migrar_semilla_v32  # noqa: E402


def main() -> int:
    config = Configuracion()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=config.ruta_db, help="Ruta del archivo SQLite destino")
    parser.add_argument("--origen", type=Path, default=config.ruta_semilla_legacy,
                        help="Carpeta con usuarios.json, parcelas.csv y riegos.json de v3.2")
    args = parser.parse_args()

    conexion = abrir_conexion(args.db)
    try:
        print(f"Esquema SQLite: v{aplicar_migraciones(conexion)}  ->  {args.db}")
        resumen = migrar_semilla_v32(conexion, args.origen)
        print(resumen.como_texto())
        for huerfano in resumen.riegos_huerfanos:
            print(f"  huérfano: {huerfano}")
    except RuntimeError as exc:
        print(f"ABORTADO: {exc}")
        return 1
    finally:
        conexion.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
