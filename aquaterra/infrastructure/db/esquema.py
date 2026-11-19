"""Esquema relacional versionado con ``PRAGMA user_version``.

Regla de oro: las migraciones son SOLO-AGREGAR. Nunca se edita una migración ya
publicada; cualquier cambio se expresa como una nueva entrada en ``MIGRACIONES``.
Así cualquier base desplegada en campo puede actualizarse de forma determinista.

Modelo (v1):

    usuarios ──< auditoria
    estaciones ──< lecturas_sensor        (series temporales, formato largo)
    estaciones ──< parcelas ──< eventos_riego >── usuarios

Integridad (resuelve DT-01):
- Llaves primarias ``AUTOINCREMENT``: un id NUNCA se reutiliza ni se renumera.
- ``eventos_riego.parcela_id`` es ``ON DELETE RESTRICT``: la base se niega a borrar
  una parcela con historial. La eliminación desde la UI es lógica (``activa = 0``).
"""

from __future__ import annotations

import sqlite3

_MIGRACION_001 = """
CREATE TABLE usuarios (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario       TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    hash_clave    TEXT    NOT NULL,
    rol           TEXT    NOT NULL CHECK (rol IN ('admin', 'operador', 'lector')),
    nombre        TEXT    NOT NULL,
    activo        INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    creado_en     TEXT    NOT NULL
);

CREATE TABLE estaciones (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo        TEXT    NOT NULL UNIQUE,
    nombre        TEXT    NOT NULL,
    tipo          TEXT    NOT NULL CHECK (tipo IN ('terrabit_inti', 'inbeersa', 'sigatoka', 'conservacion', 'otro')),
    latitud       REAL    CHECK (latitud  BETWEEN -90  AND 90),
    longitud      REAL    CHECK (longitud BETWEEN -180 AND 180),
    altitud_m     REAL,
    activa        INTEGER NOT NULL DEFAULT 1 CHECK (activa IN (0, 1)),
    creado_en     TEXT    NOT NULL
);

CREATE TABLE parcelas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT    NOT NULL,
    cultivo         TEXT    NOT NULL,
    area_m2         REAL    NOT NULL CHECK (area_m2 > 0),
    humedad_pct     REAL    NOT NULL CHECK (humedad_pct BETWEEN 0 AND 100),
    tipo_suelo      TEXT    NOT NULL CHECK (tipo_suelo IN ('Franco', 'Arenoso', 'Arcilloso')),
    riego_auto      INTEGER NOT NULL CHECK (riego_auto IN (0, 1)),
    estacion_id     INTEGER REFERENCES estaciones (id) ON DELETE SET NULL,
    activa          INTEGER NOT NULL DEFAULT 1 CHECK (activa IN (0, 1)),
    creado_en       TEXT    NOT NULL,
    actualizado_en  TEXT    NOT NULL
);
-- Dos parcelas ACTIVAS no pueden llamarse igual (las archivadas sí, para histórico).
CREATE UNIQUE INDEX ux_parcelas_nombre_activa ON parcelas (nombre COLLATE NOCASE) WHERE activa = 1;

CREATE TABLE eventos_riego (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    parcela_id           INTEGER NOT NULL REFERENCES parcelas (id) ON DELETE RESTRICT,
    ts_iso               TEXT    NOT NULL,
    ts_epoch             INTEGER NOT NULL,
    humedad_inicial_pct  REAL    CHECK (humedad_inicial_pct BETWEEN 0 AND 100),
    humedad_final_pct    REAL    CHECK (humedad_final_pct   BETWEEN 0 AND 100),
    agua_litros          REAL    NOT NULL CHECK (agua_litros > 0),
    origen               TEXT    NOT NULL DEFAULT 'manual' CHECK (origen IN ('manual', 'automatico', 'legacy_v32')),
    usuario_id           INTEGER REFERENCES usuarios (id) ON DELETE SET NULL,
    registrado_en        TEXT    NOT NULL
);
CREATE INDEX ix_riego_parcela_ts ON eventos_riego (parcela_id, ts_epoch);

CREATE TABLE lecturas_sensor (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    estacion_id  INTEGER NOT NULL REFERENCES estaciones (id) ON DELETE CASCADE,
    variable     TEXT    NOT NULL,
    valor        REAL    NOT NULL,
    unidad       TEXT,
    ts_epoch     INTEGER NOT NULL,
    ts_iso       TEXT    NOT NULL,
    fuente       TEXT    NOT NULL CHECK (fuente IN ('sd_csv', 'sd_jsonl', 'ubidots', 'mqtt_local', 'lora', 'manual')),
    calidad      INTEGER NOT NULL DEFAULT 0 CHECK (calidad IN (0, 1, 2)),
    -- Deduplicación natural: la misma muestra puede llegar por SD, Ubidots y antena.
    UNIQUE (estacion_id, variable, ts_epoch)
);
CREATE INDEX ix_lecturas_estacion_var_ts ON lecturas_sensor (estacion_id, variable, ts_epoch);

CREATE TABLE auditoria (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_iso      TEXT    NOT NULL,
    usuario_id  INTEGER REFERENCES usuarios (id) ON DELETE SET NULL,
    accion      TEXT    NOT NULL,
    entidad     TEXT    NOT NULL,
    entidad_id  INTEGER,
    detalle     TEXT
);
CREATE INDEX ix_auditoria_entidad ON auditoria (entidad, entidad_id);
"""

_MIGRACION_002 = """
CREATE TABLE eventos_estacion (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    estacion_id     INTEGER NOT NULL REFERENCES estaciones (id) ON DELETE CASCADE,
    tipo_evento     TEXT    NOT NULL,
    valor_texto     TEXT,
    archivo_ruta    TEXT,
    metadatos_json  TEXT,
    ts_epoch        INTEGER NOT NULL,
    ts_iso          TEXT    NOT NULL,
    UNIQUE (estacion_id, tipo_evento, ts_epoch)
);
CREATE INDEX ix_eventos_estacion_ts ON eventos_estacion (estacion_id, ts_epoch);

CREATE TABLE calibraciones_nodo (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    estacion_id      INTEGER REFERENCES estaciones (id) ON DELETE CASCADE,
    parcela_id       INTEGER REFERENCES parcelas (id) ON DELETE CASCADE,
    version          INTEGER NOT NULL CHECK (version >= 1),
    parametros_json  TEXT    NOT NULL,
    motivo           TEXT    NOT NULL,
    autor_id         INTEGER REFERENCES usuarios (id) ON DELETE SET NULL,
    activa           INTEGER NOT NULL DEFAULT 1 CHECK (activa IN (0, 1)),
    creado_en        TEXT    NOT NULL,
    CHECK (estacion_id IS NOT NULL OR parcela_id IS NOT NULL)
);
CREATE INDEX ix_calibraciones_destino ON calibraciones_nodo (estacion_id, parcela_id, version);

CREATE TABLE salud_actuadores_log (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    evento_riego_id       INTEGER NOT NULL UNIQUE REFERENCES eventos_riego (id) ON DELETE CASCADE,
    modo_verificacion     TEXT    NOT NULL CHECK (
        modo_verificacion IN ('sin_sensor_actuador', 'vibracion_rms', 'corriente_o_caudal', 'impacto_suelo_diferido')
    ),
    vibracion_rms_g       REAL    CHECK (vibracion_rms_g >= 0),
    vibracion_freq_hz     REAL    CHECK (vibracion_freq_hz >= 0),
    corriente_a           REAL    CHECK (corriente_a >= 0),
    caudal_lpm            REAL    CHECK (caudal_lpm >= 0),
    apertura_max_pct      REAL    NOT NULL DEFAULT 100 CHECK (apertura_max_pct BETWEEN 0 AND 100),
    diagnostico_mecanico  TEXT    NOT NULL CHECK (
        diagnostico_mecanico IN (
            'nominal', 'sin_telemetria', 'fallo_no_arranco', 'cavitacion_o_vacio', 'sobrecarga_mecanica'
        )
    ),
    registrado_en         TEXT    NOT NULL
);

CREATE TABLE incidencia_riego (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    evento_riego_id    INTEGER NOT NULL UNIQUE REFERENCES eventos_riego (id) ON DELETE CASCADE,
    humedad_a_antes    REAL    NOT NULL CHECK (humedad_a_antes BETWEEN 0 AND 100),
    humedad_a_despues  REAL    NOT NULL CHECK (humedad_a_despues BETWEEN 0 AND 100),
    humedad_b_antes    REAL    CHECK (humedad_b_antes BETWEEN 0 AND 100),
    humedad_b_despues  REAL    CHECK (humedad_b_despues BETWEEN 0 AND 100),
    delta_a_pct        REAL    NOT NULL,
    delta_b_pct        REAL,
    efectividad        TEXT    NOT NULL CHECK (
        efectividad IN ('efectivo', 'infiltracion_parcial', 'exceso_percolacion', 'sin_respuesta_en_suelo')
    ),
    observaciones      TEXT,
    evaluado_en        TEXT    NOT NULL
);

CREATE TABLE riegos_programados (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    parcela_id           INTEGER NOT NULL REFERENCES parcelas (id) ON DELETE CASCADE,
    ts_programado_epoch  INTEGER NOT NULL,
    ts_programado_iso    TEXT    NOT NULL,
    litros_propuestos    REAL    NOT NULL CHECK (litros_propuestos > 0),
    apertura_max_pct     REAL    NOT NULL DEFAULT 100 CHECK (apertura_max_pct BETWEEN 0 AND 100),
    origen               TEXT    NOT NULL DEFAULT 'ia_proactivo',
    estado               TEXT    NOT NULL DEFAULT 'pendiente' CHECK (
        estado IN ('pendiente', 'ejecutado', 'bloqueado_interlock', 'cancelado')
    ),
    motivo_bloqueo       TEXT,
    creado_en            TEXT    NOT NULL
);
CREATE INDEX ix_riegos_prog_parcela_estado ON riegos_programados (parcela_id, estado, ts_programado_epoch);

CREATE TABLE pronostico_clima_cache (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    estacion_id        INTEGER NOT NULL REFERENCES estaciones (id) ON DELETE CASCADE,
    ts_objetivo_epoch  INTEGER NOT NULL,
    ts_objetivo_iso    TEXT    NOT NULL,
    temp_c             REAL,
    hum_relativa_pct   REAL    CHECK (hum_relativa_pct BETWEEN 0 AND 100),
    lluvia_prob_pct    REAL    CHECK (lluvia_prob_pct BETWEEN 0 AND 100),
    lluvia_mm          REAL    CHECK (lluvia_mm >= 0),
    viento_ms          REAL    CHECK (viento_ms >= 0),
    et0_mm             REAL    CHECK (et0_mm >= 0),
    actualizado_en     TEXT    NOT NULL,
    UNIQUE (estacion_id, ts_objetivo_epoch)
);
CREATE INDEX ix_pronostico_estacion_ts ON pronostico_clima_cache (estacion_id, ts_objetivo_epoch);

CREATE TABLE conversaciones_copiloto (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    estacion_id              INTEGER REFERENCES estaciones (id) ON DELETE SET NULL,
    parcela_id               INTEGER REFERENCES parcelas (id) ON DELETE SET NULL,
    usuario_id               INTEGER REFERENCES usuarios (id) ON DELETE SET NULL,
    mensaje_usuario          TEXT    NOT NULL,
    diagnostico_ia           TEXT    NOT NULL,
    ajustes_propuestos_json  TEXT,
    calibracion_aplicada_id  INTEGER REFERENCES calibraciones_nodo (id) ON DELETE SET NULL,
    proveedor_ia             TEXT    NOT NULL,
    ts_iso                   TEXT    NOT NULL
);
"""

# Lista ordenada: el índice + 1 es el número de versión del esquema.
MIGRACIONES: tuple[str, ...] = (_MIGRACION_001, _MIGRACION_002)
VERSION_ESQUEMA = len(MIGRACIONES)


def version_actual(conexion: sqlite3.Connection) -> int:
    return int(conexion.execute("PRAGMA user_version;").fetchone()[0])


def aplicar_migraciones(conexion: sqlite3.Connection) -> int:
    """Lleva la base a ``VERSION_ESQUEMA``. Idempotente. Devuelve la versión final."""
    actual = version_actual(conexion)
    if actual > VERSION_ESQUEMA:
        raise RuntimeError(
            f"La base está en v{actual} pero este software solo conoce hasta v{VERSION_ESQUEMA}. "
            "Actualice SalviaBIoT antes de abrir esta base."
        )
    for numero in range(actual + 1, VERSION_ESQUEMA + 1):
        script = MIGRACIONES[numero - 1]
        # executescript hace COMMIT implícito; envolvemos en transacción explícita
        # para que una migración fallida no deje el esquema a medias.
        conexion.executescript(f"BEGIN;\n{script}\nPRAGMA user_version = {numero};\nCOMMIT;")
    return version_actual(conexion)
