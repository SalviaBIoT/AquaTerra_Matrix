"""Repositorios: traducen filas SQLite <-> entidades de dominio.

Convenciones:
- Los repositorios NO hacen commit. La unidad de trabajo (transacción) la define
  el servicio de aplicación con ``with conexion:``; así un riego (actualizar
  humedad + insertar evento) es atómico. En v3.2 eran dos escrituras de archivo
  independientes: si la segunda fallaba, la parcela quedaba "regada" sin registro.
- Todas las consultas son parametrizadas (``?``): cero concatenación de SQL.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from typing import Any

from aquaterra.core import tiempo
from aquaterra.core.domain import (
    DatosParcela,
    EntidadNoEncontrada,
    Estacion,
    EventoRiego,
    LecturaSensor,
    OrigenRiego,
    Parcela,
    Rol,
    TipoEstacion,
    TipoSuelo,
    Usuario,
)


# ──────────────────────────────────────────────────────────────────────────────
# Usuarios
# ──────────────────────────────────────────────────────────────────────────────
class RepositorioUsuarios:
    def __init__(self, conexion: sqlite3.Connection):
        self._db = conexion

    @staticmethod
    def _a_entidad(fila: sqlite3.Row) -> Usuario:
        return Usuario(
            id=fila["id"], usuario=fila["usuario"], nombre=fila["nombre"],
            rol=Rol(fila["rol"]), activo=bool(fila["activo"]),
        )

    def contar(self) -> int:
        return int(self._db.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0])

    def crear(self, usuario: str, hash_clave: str, rol: Rol, nombre: str) -> Usuario:
        cursor = self._db.execute(
            "INSERT INTO usuarios (usuario, hash_clave, rol, nombre, creado_en) VALUES (?, ?, ?, ?, ?)",
            (usuario.strip(), hash_clave, rol.value, nombre.strip(), tiempo.ahora_iso()),
        )
        return self.obtener(int(cursor.lastrowid))

    def obtener(self, usuario_id: int) -> Usuario:
        fila = self._db.execute("SELECT * FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
        if fila is None:
            raise EntidadNoEncontrada("Usuario", usuario_id)
        return self._a_entidad(fila)

    def credenciales(self, usuario: str) -> tuple[Usuario, str] | None:
        """Devuelve (usuario, hash) de una cuenta ACTIVA, o None."""
        fila = self._db.execute(
            "SELECT * FROM usuarios WHERE usuario = ? AND activo = 1", (usuario.strip(),)
        ).fetchone()
        return (self._a_entidad(fila), fila["hash_clave"]) if fila else None

    def actualizar_hash(self, usuario_id: int, hash_clave: str) -> None:
        self._db.execute("UPDATE usuarios SET hash_clave = ? WHERE id = ?", (hash_clave, usuario_id))


# ──────────────────────────────────────────────────────────────────────────────
# Parcelas
# ──────────────────────────────────────────────────────────────────────────────
class RepositorioParcelas:
    def __init__(self, conexion: sqlite3.Connection):
        self._db = conexion

    @staticmethod
    def _a_entidad(fila: sqlite3.Row) -> Parcela:
        return Parcela(
            id=fila["id"], nombre=fila["nombre"], cultivo=fila["cultivo"],
            area_m2=fila["area_m2"], humedad_pct=fila["humedad_pct"],
            tipo_suelo=TipoSuelo(fila["tipo_suelo"]), riego_auto=bool(fila["riego_auto"]),
            estacion_id=fila["estacion_id"], activa=bool(fila["activa"]),
            creado_en=fila["creado_en"], actualizado_en=fila["actualizado_en"],
        )

    def listar(self, *, solo_activas: bool = True, solo_riego_auto: bool = False) -> list[Parcela]:
        condiciones = []
        if solo_activas:
            condiciones.append("activa = 1")
        if solo_riego_auto:
            condiciones.append("riego_auto = 1")
        donde = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
        filas = self._db.execute(f"SELECT * FROM parcelas {donde} ORDER BY id").fetchall()
        return [self._a_entidad(f) for f in filas]

    def obtener(self, parcela_id: int, *, incluir_archivadas: bool = False) -> Parcela:
        sql = "SELECT * FROM parcelas WHERE id = ?" + ("" if incluir_archivadas else " AND activa = 1")
        fila = self._db.execute(sql, (parcela_id,)).fetchone()
        if fila is None:
            raise EntidadNoEncontrada("Parcela", parcela_id)
        return self._a_entidad(fila)

    def existe_nombre_activo(self, nombre: str, *, excluir_id: int | None = None) -> bool:
        fila = self._db.execute(
            "SELECT 1 FROM parcelas WHERE activa = 1 AND nombre = ? COLLATE NOCASE AND id IS NOT ?",
            (nombre, excluir_id),
        ).fetchone()
        return fila is not None

    def crear(self, datos: DatosParcela, *, creado_en: str | None = None) -> Parcela:
        marca = creado_en or tiempo.ahora_iso()
        cursor = self._db.execute(
            """INSERT INTO parcelas (nombre, cultivo, area_m2, humedad_pct, tipo_suelo,
                                     riego_auto, estacion_id, creado_en, actualizado_en)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (datos.nombre, datos.cultivo, datos.area_m2, datos.humedad_pct, datos.tipo_suelo.value,
             int(datos.riego_auto), datos.estacion_id, marca, marca),
        )
        return self.obtener(int(cursor.lastrowid))

    def actualizar(self, parcela_id: int, datos: DatosParcela) -> Parcela:
        cursor = self._db.execute(
            """UPDATE parcelas SET nombre = ?, cultivo = ?, area_m2 = ?, humedad_pct = ?,
                      tipo_suelo = ?, riego_auto = ?, estacion_id = ?, actualizado_en = ?
               WHERE id = ? AND activa = 1""",
            (datos.nombre, datos.cultivo, datos.area_m2, datos.humedad_pct, datos.tipo_suelo.value,
             int(datos.riego_auto), datos.estacion_id, tiempo.ahora_iso(), parcela_id),
        )
        if cursor.rowcount == 0:
            raise EntidadNoEncontrada("Parcela", parcela_id)
        return self.obtener(parcela_id)

    def actualizar_humedad(self, parcela_id: int, humedad_pct: float) -> None:
        cursor = self._db.execute(
            "UPDATE parcelas SET humedad_pct = ?, actualizado_en = ? WHERE id = ? AND activa = 1",
            (humedad_pct, tiempo.ahora_iso(), parcela_id),
        )
        if cursor.rowcount == 0:
            raise EntidadNoEncontrada("Parcela", parcela_id)

    def archivar(self, parcela_id: int) -> None:
        """Eliminación lógica: conserva id e historial de riegos (fix DT-01)."""
        cursor = self._db.execute(
            "UPDATE parcelas SET activa = 0, actualizado_en = ? WHERE id = ? AND activa = 1",
            (tiempo.ahora_iso(), parcela_id),
        )
        if cursor.rowcount == 0:
            raise EntidadNoEncontrada("Parcela", parcela_id)


# ──────────────────────────────────────────────────────────────────────────────
# Eventos de riego
# ──────────────────────────────────────────────────────────────────────────────
class RepositorioRiegos:
    def __init__(self, conexion: sqlite3.Connection):
        self._db = conexion

    @staticmethod
    def _a_entidad(fila: sqlite3.Row) -> EventoRiego:
        return EventoRiego(
            id=fila["id"], parcela_id=fila["parcela_id"], ts_iso=fila["ts_iso"],
            ts_epoch=fila["ts_epoch"], humedad_inicial_pct=fila["humedad_inicial_pct"],
            humedad_final_pct=fila["humedad_final_pct"], agua_litros=fila["agua_litros"],
            origen=OrigenRiego(fila["origen"]), usuario_id=fila["usuario_id"],
        )

    def registrar(
        self,
        *,
        parcela_id: int,
        momento_iso: str,
        momento_epoch: int,
        agua_litros: float,
        humedad_inicial_pct: float | None,
        humedad_final_pct: float | None,
        origen: OrigenRiego,
        usuario_id: int | None,
    ) -> EventoRiego:
        cursor = self._db.execute(
            """INSERT INTO eventos_riego (parcela_id, ts_iso, ts_epoch, humedad_inicial_pct,
                                          humedad_final_pct, agua_litros, origen, usuario_id, registrado_en)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (parcela_id, momento_iso, momento_epoch, humedad_inicial_pct, humedad_final_pct,
             agua_litros, origen.value, usuario_id, tiempo.ahora_iso()),
        )
        fila = self._db.execute("SELECT * FROM eventos_riego WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return self._a_entidad(fila)

    def listar_por_parcela(self, parcela_id: int) -> list[EventoRiego]:
        filas = self._db.execute(
            "SELECT * FROM eventos_riego WHERE parcela_id = ? ORDER BY ts_epoch", (parcela_id,)
        ).fetchall()
        return [self._a_entidad(f) for f in filas]

    def contar(self) -> int:
        return int(self._db.execute("SELECT COUNT(*) FROM eventos_riego").fetchone()[0])

    def consumo_por_parcela(self) -> list[tuple[int, str, float]]:
        """Litros acumulados agrupados por ID (no por nombre: renombrar ya no parte la serie)."""
        filas = self._db.execute(
            """SELECT p.id, p.nombre, SUM(r.agua_litros) AS litros
               FROM eventos_riego r JOIN parcelas p ON p.id = r.parcela_id
               GROUP BY p.id ORDER BY p.id"""
        ).fetchall()
        return [(f["id"], f["nombre"], float(f["litros"])) for f in filas]


# ──────────────────────────────────────────────────────────────────────────────
# Estaciones y lecturas (base para la ingesta IoT de v4.0 / v5.0)
# ──────────────────────────────────────────────────────────────────────────────
class RepositorioEstaciones:
    def __init__(self, conexion: sqlite3.Connection):
        self._db = conexion

    @staticmethod
    def _a_entidad(fila: sqlite3.Row) -> Estacion:
        return Estacion(
            id=fila["id"], codigo=fila["codigo"], nombre=fila["nombre"], tipo=TipoEstacion(fila["tipo"]),
            latitud=fila["latitud"], longitud=fila["longitud"], altitud_m=fila["altitud_m"],
            activa=bool(fila["activa"]),
        )

    def crear(self, codigo: str, nombre: str, tipo: TipoEstacion, **geo: float | None) -> Estacion:
        cursor = self._db.execute(
            """INSERT INTO estaciones (codigo, nombre, tipo, latitud, longitud, altitud_m, creado_en)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (codigo, nombre, tipo.value, geo.get("latitud"), geo.get("longitud"), geo.get("altitud_m"),
             tiempo.ahora_iso()),
        )
        return self.obtener(int(cursor.lastrowid))

    def obtener(self, estacion_id: int) -> Estacion:
        fila = self._db.execute("SELECT * FROM estaciones WHERE id = ?", (estacion_id,)).fetchone()
        if fila is None:
            raise EntidadNoEncontrada("Estación", estacion_id)
        return self._a_entidad(fila)

    def por_codigo(self, codigo: str) -> Estacion | None:
        fila = self._db.execute("SELECT * FROM estaciones WHERE codigo = ?", (codigo,)).fetchone()
        return self._a_entidad(fila) if fila else None

    def listar(self) -> list[Estacion]:
        return [self._a_entidad(f) for f in self._db.execute("SELECT * FROM estaciones ORDER BY id")]


class RepositorioLecturas:
    def __init__(self, conexion: sqlite3.Connection):
        self._db = conexion

    def insertar_lote(self, lecturas: Iterable[LecturaSensor]) -> int:
        """Inserta ignorando duplicados (misma estación+variable+epoch). Devuelve filas nuevas."""
        antes = self._db.total_changes
        self._db.executemany(
            """INSERT OR IGNORE INTO lecturas_sensor
               (estacion_id, variable, valor, unidad, ts_epoch, ts_iso, fuente, calidad)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [(l.estacion_id, l.variable, l.valor, l.unidad, l.ts_epoch, l.ts_iso, l.fuente, l.calidad)
             for l in lecturas],
        )
        return self._db.total_changes - antes

    def serie(self, estacion_id: int, variable: str, desde_epoch: int = 0) -> list[tuple[int, float]]:
        filas = self._db.execute(
            """SELECT ts_epoch, valor FROM lecturas_sensor
               WHERE estacion_id = ? AND variable = ? AND ts_epoch >= ? AND calidad < 2
               ORDER BY ts_epoch""",
            (estacion_id, variable, desde_epoch),
        ).fetchall()
        return [(f[0], f[1]) for f in filas]

    def ultimo_epoch(self, estacion_id: int) -> int | None:
        """Marca de agua para sincronización incremental (p. ej. pull desde Ubidots)."""
        fila = self._db.execute(
            "SELECT MAX(ts_epoch) FROM lecturas_sensor WHERE estacion_id = ?", (estacion_id,)
        ).fetchone()
        return fila[0]


# ──────────────────────────────────────────────────────────────────────────────
# Auditoría (trazabilidad de quién hizo qué y cuándo)
# ──────────────────────────────────────────────────────────────────────────────
class RepositorioAuditoria:
    def __init__(self, conexion: sqlite3.Connection):
        self._db = conexion

    def registrar(
        self, accion: str, entidad: str, entidad_id: int | None,
        usuario_id: int | None, detalle: dict[str, Any] | None = None,
    ) -> None:
        sql = (
            "INSERT INTO auditoria (ts_iso, usuario_id, accion, entidad, entidad_id, detalle) "
            "VALUES (?, ?, ?, ?, ?, ?)"
        )
        self._db.execute(
            sql,
            (tiempo.ahora_iso(), usuario_id, accion, entidad, entidad_id,
             json.dumps(detalle, ensure_ascii=False, default=str) if detalle else None),
        )

    def listar(self, entidad: str | None = None) -> list[sqlite3.Row]:
        if entidad:
            return self._db.execute(
                "SELECT * FROM auditoria WHERE entidad = ? ORDER BY id", (entidad,)
            ).fetchall()
        return self._db.execute("SELECT * FROM auditoria ORDER BY id").fetchall()
