"""Fixtures compartidas: base SQLite en memoria con esquema y actores de prueba."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from aquaterra.core.domain import Rol, Usuario
from aquaterra.infrastructure.db import abrir_conexion, aplicar_migraciones
from aquaterra.infrastructure.db.repositorios import RepositorioUsuarios
from aquaterra.infrastructure.seguridad import generar_hash

RAIZ = Path(__file__).resolve().parent.parent
SEMILLA_V32 = RAIZ / "legacy" / "aquautp_v3.2" / "data"
ITERACIONES_TEST = 1_000  # Hash rápido en pruebas; producción usa 600 000.


@pytest.fixture
def db() -> sqlite3.Connection:
    conexion = abrir_conexion(":memory:")
    aplicar_migraciones(conexion)
    yield conexion
    conexion.close()


@pytest.fixture
def admin(db) -> Usuario:
    with db:
        return RepositorioUsuarios(db).crear("admin_t", generar_hash("clave", iteraciones=ITERACIONES_TEST),
                                             Rol.ADMIN, "Admin Prueba")


@pytest.fixture
def operador(db) -> Usuario:
    with db:
        return RepositorioUsuarios(db).crear("oper_t", generar_hash("clave", iteraciones=ITERACIONES_TEST),
                                             Rol.OPERADOR, "Operador Prueba")


def campos_parcela(**cambios):
    base = {"nombre": "Lote Norte", "cultivo": "Tomate", "area": "120", "humedad": 30,
            "suelo": "Franco", "riego_auto": True}
    base.update(cambios)
    return base
