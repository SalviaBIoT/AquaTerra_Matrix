"""Migrador único de la semilla AquaUTP v3.2 (CSV/JSON planos) hacia SQLite.

Transformaciones aplicadas:

| Origen v3.2                              | Destino v4.0                                  |
|------------------------------------------|-----------------------------------------------|
| ``usuarios.json`` ``pass`` en claro      | ``usuarios.hash_clave`` PBKDF2-SHA256         |
| rol ``user``                             | rol ``operador``                              |
| ``parcelas.csv`` id 1..n                 | ``parcelas`` CONSERVANDO el id original       |
| ``riego_auto`` "Activo"/"Inactivo"       | ``riego_auto`` 1/0                            |
| ``riegos.json`` fecha ``MM/DD/YY`` + hora| ``ts_iso`` ISO-8601 -05:00 + ``ts_epoch``     |
| ``riegos.json`` id_parcela (+ nombre)    | ``parcela_id`` FK validada                    |

Se conservan los ids de parcela de v3.2 porque ``riegos.json`` los referencia.
Si un riego apunta a un id inexistente (síntoma del bug DT-01 de renumeración),
se reporta como huérfano en vez de asignarlo a la parcela equivocada.

Toda la migración ocurre en UNA transacción: o entra completa o no entra nada.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from aquaterra.core import tiempo
from aquaterra.core.domain import OrigenRiego, Rol
from aquaterra.core.domain.validadores import validar_datos_parcela
from aquaterra.infrastructure.db.repositorios import (
    RepositorioAuditoria,
    RepositorioParcelas,
    RepositorioRiegos,
    RepositorioUsuarios,
)
from aquaterra.infrastructure.seguridad import generar_hash

_MAPA_ROLES = {"admin": Rol.ADMIN, "user": Rol.OPERADOR}


@dataclass
class ResumenMigracion:
    usuarios: int = 0
    parcelas: int = 0
    riegos: int = 0
    riegos_huerfanos: list[dict] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)

    def como_texto(self) -> str:
        lineas = [
            f"Usuarios migrados : {self.usuarios}",
            f"Parcelas migradas : {self.parcelas}",
            f"Riegos migrados   : {self.riegos}",
            f"Riegos huérfanos  : {len(self.riegos_huerfanos)}",
        ]
        lineas += [f"ADVERTENCIA: {a}" for a in self.advertencias]
        return "\n".join(lineas)


def migrar_semilla_v32(
    conexion: sqlite3.Connection,
    carpeta_datos: Path,
    *,
    iteraciones_hash: int | None = None,
) -> ResumenMigracion:
    """Importa ``usuarios.json``, ``parcelas.csv`` y ``riegos.json`` de v3.2.

    Raises:
        RuntimeError: si la base ya contiene usuarios o parcelas (evita duplicar).
        FileNotFoundError: si falta alguno de los tres archivos de origen.
    """
    repo_u = RepositorioUsuarios(conexion)
    repo_p = RepositorioParcelas(conexion)
    repo_r = RepositorioRiegos(conexion)
    repo_a = RepositorioAuditoria(conexion)

    if repo_u.contar() or repo_p.listar(solo_activas=False):
        raise RuntimeError("La base de datos no está vacía; la migración v3.2 solo se ejecuta una vez.")

    ruta_usuarios = carpeta_datos / "usuarios.json"
    ruta_parcelas = carpeta_datos / "parcelas.csv"
    ruta_riegos = carpeta_datos / "riegos.json"
    for ruta in (ruta_usuarios, ruta_parcelas, ruta_riegos):
        if not ruta.exists():
            raise FileNotFoundError(ruta)

    kwargs_hash = {"iteraciones": iteraciones_hash} if iteraciones_hash else {}
    resumen = ResumenMigracion()

    with conexion:  # transacción atómica
        # 1. Usuarios ──────────────────────────────────────────────────────────
        for registro in json.loads(ruta_usuarios.read_text(encoding="utf-8")):
            rol = _MAPA_ROLES.get(registro.get("rol", ""), Rol.OPERADOR)
            repo_u.crear(registro["usuario"], generar_hash(str(registro["pass"]), **kwargs_hash),
                         rol, registro.get("nombre") or registro["usuario"])
            resumen.usuarios += 1

        # 2. Parcelas (conservando id) ───────────────────────────────────────
        marca = tiempo.ahora_iso()
        with ruta_parcelas.open(encoding="utf-8", newline="") as archivo:
            for fila in csv.DictReader(archivo):
                datos = validar_datos_parcela(
                    nombre=fila["nombre"], cultivo=fila["cultivo"], area=fila["area"],
                    humedad=fila["humedad"], suelo=fila["suelo"],
                    riego_auto=fila["riego_auto"].strip() == "Activo",
                )
                conexion.execute(
                    """INSERT INTO parcelas (id, nombre, cultivo, area_m2, humedad_pct, tipo_suelo,
                                             riego_auto, creado_en, actualizado_en)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (int(fila["id"]), datos.nombre, datos.cultivo, datos.area_m2, datos.humedad_pct,
                     datos.tipo_suelo.value, int(datos.riego_auto), marca, marca),
                )
                resumen.parcelas += 1

        nombres_por_id = {p.id: p.nombre for p in repo_p.listar(solo_activas=False)}

        # 3. Riegos ───────────────────────────────────────────────────────────
        for evento in json.loads(ruta_riegos.read_text(encoding="utf-8")):
            pid = int(evento["id_parcela"])
            if pid not in nombres_por_id:
                resumen.riegos_huerfanos.append(evento)
                continue
            if nombres_por_id[pid] != evento.get("nombre_parcela"):
                resumen.advertencias.append(
                    f"Riego de '{evento.get('nombre_parcela')}' apunta a id {pid} "
                    f"('{nombres_por_id[pid]}'): posible desfase por renumeración DT-01."
                )
            momento = tiempo.parsear_fecha_legacy_v32(evento["fecha"], evento["hora"])
            repo_r.registrar(
                parcela_id=pid, momento_iso=tiempo.a_iso(momento), momento_epoch=tiempo.a_epoch(momento),
                agua_litros=float(evento["agua_litros"]),
                humedad_inicial_pct=float(evento["humedad_inicial"]),
                humedad_final_pct=float(evento["humedad_final"]),
                origen=OrigenRiego.LEGACY_V32, usuario_id=None,
            )
            resumen.riegos += 1

        repo_a.registrar("migracion_v32", "sistema", None, None, {
            "origen": str(carpeta_datos), "usuarios": resumen.usuarios, "parcelas": resumen.parcelas,
            "riegos": resumen.riegos, "huerfanos": len(resumen.riegos_huerfanos),
        })

    return resumen
