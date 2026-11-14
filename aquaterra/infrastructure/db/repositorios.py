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
    DiagnosticoMecanicoBomba,
    EfectividadRiego,
    EntidadNoEncontrada,
    Estacion,
    EstadoRiegoProgramado,
    EventoEstacion,
    EventoRiego,
    IncidenciaRiego,
    InteraccionCopiloto,
    LecturaSensor,
    ModoVerificacionRiego,
    OrigenRiego,
    Parcela,
    PuntoPronosticoClima,
    RegistroSaludActuador,
    RiegoProgramado,
    Rol,
    TipoEstacion,
    TipoSuelo,
    Usuario,
    VersionCalibracion,
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


# ──────────────────────────────────────────────────────────────────────────────
# Eventos discretos de estación, calibraciones versionadas y control físico (v2)
# ──────────────────────────────────────────────────────────────────────────────
class RepositorioEventosEstacion:
    def __init__(self, conexion: sqlite3.Connection):
        self._db = conexion

    @staticmethod
    def _a_entidad(fila: sqlite3.Row) -> EventoEstacion:
        metadatos = json.loads(fila["metadatos_json"]) if fila["metadatos_json"] else None
        return EventoEstacion(
            id=fila["id"],
            estacion_id=fila["estacion_id"],
            tipo_evento=fila["tipo_evento"],
            ts_epoch=fila["ts_epoch"],
            ts_iso=fila["ts_iso"],
            valor_texto=fila["valor_texto"],
            archivo_ruta=fila["archivo_ruta"],
            metadatos=metadatos,
        )

    def insertar_lote(self, eventos: Iterable[EventoEstacion]) -> int:
        antes = self._db.total_changes
        self._db.executemany(
            """INSERT OR IGNORE INTO eventos_estacion
               (estacion_id, tipo_evento, valor_texto, archivo_ruta, metadatos_json, ts_epoch, ts_iso)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    ev.estacion_id,
                    ev.tipo_evento,
                    ev.valor_texto,
                    ev.archivo_ruta,
                    json.dumps(ev.metadatos, ensure_ascii=False, default=str) if ev.metadatos else None,
                    ev.ts_epoch,
                    ev.ts_iso,
                )
                for ev in eventos
            ],
        )
        return self._db.total_changes - antes

    def listar(
        self,
        estacion_id: int,
        *,
        tipo_evento: str | None = None,
        desde_epoch: int = 0,
    ) -> list[EventoEstacion]:
        if tipo_evento is not None:
            filas = self._db.execute(
                """SELECT * FROM eventos_estacion
                   WHERE estacion_id = ? AND tipo_evento = ? AND ts_epoch >= ?
                   ORDER BY ts_epoch, id""",
                (estacion_id, tipo_evento, desde_epoch),
            ).fetchall()
        else:
            filas = self._db.execute(
                """SELECT * FROM eventos_estacion
                   WHERE estacion_id = ? AND ts_epoch >= ?
                   ORDER BY ts_epoch, id""",
                (estacion_id, desde_epoch),
            ).fetchall()
        return [self._a_entidad(f) for f in filas]


class RepositorioCalibraciones:
    def __init__(self, conexion: sqlite3.Connection):
        self._db = conexion

    @staticmethod
    def _a_entidad(fila: sqlite3.Row) -> VersionCalibracion:
        return VersionCalibracion(
            id=fila["id"],
            estacion_id=fila["estacion_id"],
            parcela_id=fila["parcela_id"],
            version=fila["version"],
            parametros=json.loads(fila["parametros_json"]),
            motivo=fila["motivo"],
            autor_id=fila["autor_id"],
            activa=bool(fila["activa"]),
            creado_en=fila["creado_en"],
        )

    def guardar_nueva_version(
        self,
        *,
        estacion_id: int | None = None,
        parcela_id: int | None = None,
        parametros: dict[str, Any],
        motivo: str,
        autor_id: int | None = None,
    ) -> VersionCalibracion:
        if estacion_id is None and parcela_id is None:
            raise ValueError("Debe especificar al menos estacion_id o parcela_id.")

        fila_max = self._db.execute(
            """SELECT COALESCE(MAX(version), 0) FROM calibraciones_nodo
               WHERE estacion_id IS ? AND parcela_id IS ?""",
            (estacion_id, parcela_id),
        ).fetchone()
        nueva_version = int(fila_max[0]) + 1

        self._db.execute(
            """UPDATE calibraciones_nodo SET activa = 0
               WHERE estacion_id IS ? AND parcela_id IS ? AND activa = 1""",
            (estacion_id, parcela_id),
        )
        cursor = self._db.execute(
            """INSERT INTO calibraciones_nodo
               (estacion_id, parcela_id, version, parametros_json, motivo, autor_id, activa, creado_en)
               VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
            (
                estacion_id,
                parcela_id,
                nueva_version,
                json.dumps(parametros, ensure_ascii=False, sort_keys=True),
                motivo.strip(),
                autor_id,
                tiempo.ahora_iso(),
            ),
        )
        fila = self._db.execute(
            "SELECT * FROM calibraciones_nodo WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return self._a_entidad(fila)

    def obtener_activa(
        self,
        *,
        estacion_id: int | None = None,
        parcela_id: int | None = None,
    ) -> VersionCalibracion | None:
        fila = self._db.execute(
            """SELECT * FROM calibraciones_nodo
               WHERE estacion_id IS ? AND parcela_id IS ? AND activa = 1
               ORDER BY version DESC LIMIT 1""",
            (estacion_id, parcela_id),
        ).fetchone()
        return self._a_entidad(fila) if fila else None

    def listar_versiones(
        self,
        *,
        estacion_id: int | None = None,
        parcela_id: int | None = None,
    ) -> list[VersionCalibracion]:
        filas = self._db.execute(
            """SELECT * FROM calibraciones_nodo
               WHERE estacion_id IS ? AND parcela_id IS ?
               ORDER BY version ASC""",
            (estacion_id, parcela_id),
        ).fetchall()
        return [self._a_entidad(f) for f in filas]

    def restaurar_version(
        self,
        version_id: int,
        *,
        autor_id: int | None = None,
    ) -> VersionCalibracion:
        fila = self._db.execute(
            "SELECT * FROM calibraciones_nodo WHERE id = ?", (version_id,)
        ).fetchone()
        if fila is None:
            raise EntidadNoEncontrada("VersionCalibracion", version_id)
        anterior = self._a_entidad(fila)
        return self.guardar_nueva_version(
            estacion_id=anterior.estacion_id,
            parcela_id=anterior.parcela_id,
            parametros=anterior.parametros,
            motivo=f"Rollback a versión v{anterior.version}",
            autor_id=autor_id,
        )


class RepositorioSaludActuadores:
    def __init__(self, conexion: sqlite3.Connection):
        self._db = conexion

    @staticmethod
    def _a_entidad(fila: sqlite3.Row) -> RegistroSaludActuador:
        return RegistroSaludActuador(
            id=fila["id"],
            evento_riego_id=fila["evento_riego_id"],
            modo_verificacion=ModoVerificacionRiego(fila["modo_verificacion"]),
            vibracion_rms_g=fila["vibracion_rms_g"],
            vibracion_freq_hz=fila["vibracion_freq_hz"],
            corriente_a=fila["corriente_a"],
            caudal_lpm=fila["caudal_lpm"],
            apertura_max_pct=fila["apertura_max_pct"],
            diagnostico_mecanico=DiagnosticoMecanicoBomba(fila["diagnostico_mecanico"]),
            registrado_en=fila["registrado_en"],
        )

    def registrar(
        self,
        *,
        evento_riego_id: int,
        modo_verificacion: ModoVerificacionRiego,
        diagnostico_mecanico: DiagnosticoMecanicoBomba,
        apertura_max_pct: float = 100.0,
        vibracion_rms_g: float | None = None,
        vibracion_freq_hz: float | None = None,
        corriente_a: float | None = None,
        caudal_lpm: float | None = None,
    ) -> RegistroSaludActuador:
        cursor = self._db.execute(
            """INSERT INTO salud_actuadores_log
               (evento_riego_id, modo_verificacion, vibracion_rms_g, vibracion_freq_hz,
                corriente_a, caudal_lpm, apertura_max_pct, diagnostico_mecanico, registrado_en)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                evento_riego_id,
                modo_verificacion.value,
                vibracion_rms_g,
                vibracion_freq_hz,
                corriente_a,
                caudal_lpm,
                apertura_max_pct,
                diagnostico_mecanico.value,
                tiempo.ahora_iso(),
            ),
        )
        fila = self._db.execute(
            "SELECT * FROM salud_actuadores_log WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return self._a_entidad(fila)

    def por_evento(self, evento_riego_id: int) -> RegistroSaludActuador | None:
        fila = self._db.execute(
            "SELECT * FROM salud_actuadores_log WHERE evento_riego_id = ?", (evento_riego_id,)
        ).fetchone()
        return self._a_entidad(fila) if fila else None


class RepositorioIncidenciaRiego:
    def __init__(self, conexion: sqlite3.Connection):
        self._db = conexion

    @staticmethod
    def _a_entidad(fila: sqlite3.Row) -> IncidenciaRiego:
        return IncidenciaRiego(
            id=fila["id"],
            evento_riego_id=fila["evento_riego_id"],
            humedad_a_antes=fila["humedad_a_antes"],
            humedad_a_despues=fila["humedad_a_despues"],
            humedad_b_antes=fila["humedad_b_antes"],
            humedad_b_despues=fila["humedad_b_despues"],
            delta_a_pct=fila["delta_a_pct"],
            delta_b_pct=fila["delta_b_pct"],
            efectividad=EfectividadRiego(fila["efectividad"]),
            observaciones=fila["observaciones"],
            evaluado_en=fila["evaluado_en"],
        )

    def registrar(
        self,
        *,
        evento_riego_id: int,
        humedad_a_antes: float,
        humedad_a_despues: float,
        efectividad: EfectividadRiego,
        humedad_b_antes: float | None = None,
        humedad_b_despues: float | None = None,
        observaciones: str | None = None,
    ) -> IncidenciaRiego:
        delta_a = round(humedad_a_despues - humedad_a_antes, 2)
        delta_b = (
            round(humedad_b_despues - humedad_b_antes, 2)
            if humedad_b_antes is not None and humedad_b_despues is not None
            else None
        )
        cursor = self._db.execute(
            """INSERT INTO incidencia_riego
               (evento_riego_id, humedad_a_antes, humedad_a_despues, humedad_b_antes, humedad_b_despues,
                delta_a_pct, delta_b_pct, efectividad, observaciones, evaluado_en)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                evento_riego_id,
                humedad_a_antes,
                humedad_a_despues,
                humedad_b_antes,
                humedad_b_despues,
                delta_a,
                delta_b,
                efectividad.value,
                observaciones,
                tiempo.ahora_iso(),
            ),
        )
        fila = self._db.execute(
            "SELECT * FROM incidencia_riego WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return self._a_entidad(fila)

    def por_evento(self, evento_riego_id: int) -> IncidenciaRiego | None:
        fila = self._db.execute(
            "SELECT * FROM incidencia_riego WHERE evento_riego_id = ?", (evento_riego_id,)
        ).fetchone()
        return self._a_entidad(fila) if fila else None

    def listar_por_parcela(self, parcela_id: int) -> list[IncidenciaRiego]:
        filas = self._db.execute(
            """SELECT i.* FROM incidencia_riego i
               JOIN eventos_riego r ON r.id = i.evento_riego_id
               WHERE r.parcela_id = ?
               ORDER BY r.ts_epoch ASC""",
            (parcela_id,),
        ).fetchall()
        return [self._a_entidad(f) for f in filas]


class RepositorioRiegosProgramados:
    def __init__(self, conexion: sqlite3.Connection):
        self._db = conexion

    @staticmethod
    def _a_entidad(fila: sqlite3.Row) -> RiegoProgramado:
        return RiegoProgramado(
            id=fila["id"],
            parcela_id=fila["parcela_id"],
            ts_programado_epoch=fila["ts_programado_epoch"],
            ts_programado_iso=fila["ts_programado_iso"],
            litros_propuestos=fila["litros_propuestos"],
            apertura_max_pct=fila["apertura_max_pct"],
            origen=fila["origen"],
            estado=EstadoRiegoProgramado(fila["estado"]),
            motivo_bloqueo=fila["motivo_bloqueo"],
            creado_en=fila["creado_en"],
        )

    def programar(
        self,
        *,
        parcela_id: int,
        ts_programado_epoch: int,
        ts_programado_iso: str,
        litros_propuestos: float,
        apertura_max_pct: float = 100.0,
        origen: str = "ia_proactivo",
    ) -> RiegoProgramado:
        cursor = self._db.execute(
            """INSERT INTO riegos_programados
               (parcela_id, ts_programado_epoch, ts_programado_iso, litros_propuestos,
                apertura_max_pct, origen, estado, creado_en)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                parcela_id,
                ts_programado_epoch,
                ts_programado_iso,
                litros_propuestos,
                apertura_max_pct,
                origen,
                EstadoRiegoProgramado.PENDIENTE.value,
                tiempo.ahora_iso(),
            ),
        )
        fila = self._db.execute(
            "SELECT * FROM riegos_programados WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return self._a_entidad(fila)

    def actualizar_estado(
        self,
        riego_prog_id: int,
        estado: EstadoRiegoProgramado,
        *,
        motivo_bloqueo: str | None = None,
    ) -> RiegoProgramado:
        cursor = self._db.execute(
            "UPDATE riegos_programados SET estado = ?, motivo_bloqueo = ? WHERE id = ?",
            (estado.value, motivo_bloqueo, riego_prog_id),
        )
        if cursor.rowcount == 0:
            raise EntidadNoEncontrada("RiegoProgramado", riego_prog_id)
        fila = self._db.execute(
            "SELECT * FROM riegos_programados WHERE id = ?", (riego_prog_id,)
        ).fetchone()
        return self._a_entidad(fila)

    def listar_pendientes(self, parcela_id: int | None = None) -> list[RiegoProgramado]:
        if parcela_id is not None:
            filas = self._db.execute(
                """SELECT * FROM riegos_programados
                   WHERE parcela_id = ? AND estado = 'pendiente'
                   ORDER BY ts_programado_epoch ASC""",
                (parcela_id,),
            ).fetchall()
        else:
            filas = self._db.execute(
                """SELECT * FROM riegos_programados
                   WHERE estado = 'pendiente'
                   ORDER BY ts_programado_epoch ASC"""
            ).fetchall()
        return [self._a_entidad(f) for f in filas]


class RepositorioPronosticoClima:
    def __init__(self, conexion: sqlite3.Connection):
        self._db = conexion

    @staticmethod
    def _a_entidad(fila: sqlite3.Row) -> PuntoPronosticoClima:
        return PuntoPronosticoClima(
            estacion_id=fila["estacion_id"],
            ts_objetivo_epoch=fila["ts_objetivo_epoch"],
            ts_objetivo_iso=fila["ts_objetivo_iso"],
            temp_c=fila["temp_c"],
            hum_relativa_pct=fila["hum_relativa_pct"],
            lluvia_prob_pct=fila["lluvia_prob_pct"],
            lluvia_mm=fila["lluvia_mm"],
            viento_ms=fila["viento_ms"],
            et0_mm=fila["et0_mm"],
        )

    def guardar_lote(self, puntos: Iterable[PuntoPronosticoClima]) -> int:
        antes = self._db.total_changes
        marca = tiempo.ahora_iso()
        self._db.executemany(
            """INSERT OR REPLACE INTO pronostico_clima_cache
               (estacion_id, ts_objetivo_epoch, ts_objetivo_iso, temp_c, hum_relativa_pct,
                lluvia_prob_pct, lluvia_mm, viento_ms, et0_mm, actualizado_en)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    p.estacion_id,
                    p.ts_objetivo_epoch,
                    p.ts_objetivo_iso,
                    p.temp_c,
                    p.hum_relativa_pct,
                    p.lluvia_prob_pct,
                    p.lluvia_mm,
                    p.viento_ms,
                    p.et0_mm,
                    marca,
                )
                for p in puntos
            ],
        )
        return self._db.total_changes - antes

    def ventana(
        self,
        estacion_id: int,
        *,
        desde_epoch: int,
        hasta_epoch: int,
    ) -> list[PuntoPronosticoClima]:
        filas = self._db.execute(
            """SELECT * FROM pronostico_clima_cache
               WHERE estacion_id = ? AND ts_objetivo_epoch BETWEEN ? AND ?
               ORDER BY ts_objetivo_epoch ASC""",
            (estacion_id, desde_epoch, hasta_epoch),
        ).fetchall()
        return [self._a_entidad(f) for f in filas]


class RepositorioCopiloto:
    def __init__(self, conexion: sqlite3.Connection):
        self._db = conexion

    @staticmethod
    def _a_entidad(fila: sqlite3.Row) -> InteraccionCopiloto:
        ajustes = (
            json.loads(fila["ajustes_propuestos_json"])
            if fila["ajustes_propuestos_json"]
            else None
        )
        return InteraccionCopiloto(
            id=fila["id"],
            estacion_id=fila["estacion_id"],
            parcela_id=fila["parcela_id"],
            usuario_id=fila["usuario_id"],
            mensaje_usuario=fila["mensaje_usuario"],
            diagnostico_ia=fila["diagnostico_ia"],
            ajustes_propuestos=ajustes,
            calibracion_aplicada_id=fila["calibracion_aplicada_id"],
            proveedor_ia=fila["proveedor_ia"],
            ts_iso=fila["ts_iso"],
        )

    def registrar(
        self,
        *,
        mensaje_usuario: str,
        diagnostico_ia: str,
        proveedor_ia: str,
        estacion_id: int | None = None,
        parcela_id: int | None = None,
        usuario_id: int | None = None,
        ajustes_propuestos: dict[str, Any] | None = None,
        calibracion_aplicada_id: int | None = None,
    ) -> InteraccionCopiloto:
        cursor = self._db.execute(
            """INSERT INTO conversaciones_copiloto
               (estacion_id, parcela_id, usuario_id, mensaje_usuario, diagnostico_ia,
                ajustes_propuestos_json, calibracion_aplicada_id, proveedor_ia, ts_iso)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                estacion_id,
                parcela_id,
                usuario_id,
                mensaje_usuario,
                diagnostico_ia,
                (
                    json.dumps(ajustes_propuestos, ensure_ascii=False)
                    if ajustes_propuestos is not None
                    else None
                ),
                calibracion_aplicada_id,
                proveedor_ia,
                tiempo.ahora_iso(),
            ),
        )
        fila = self._db.execute(
            "SELECT * FROM conversaciones_copiloto WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return self._a_entidad(fila)

    def listar(
        self,
        *,
        estacion_id: int | None = None,
        parcela_id: int | None = None,
    ) -> list[InteraccionCopiloto]:
        if estacion_id is not None and parcela_id is not None:
            filas = self._db.execute(
                """SELECT * FROM conversaciones_copiloto
                   WHERE estacion_id = ? AND parcela_id = ?
                   ORDER BY id ASC""",
                (estacion_id, parcela_id),
            ).fetchall()
        elif estacion_id is not None:
            filas = self._db.execute(
                "SELECT * FROM conversaciones_copiloto WHERE estacion_id = ? ORDER BY id ASC",
                (estacion_id,),
            ).fetchall()
        elif parcela_id is not None:
            filas = self._db.execute(
                "SELECT * FROM conversaciones_copiloto WHERE parcela_id = ? ORDER BY id ASC",
                (parcela_id,),
            ).fetchall()
        else:
            filas = self._db.execute("SELECT * FROM conversaciones_copiloto ORDER BY id ASC").fetchall()
        return [self._a_entidad(f) for f in filas]
