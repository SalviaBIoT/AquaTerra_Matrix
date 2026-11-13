"""Migración real de la semilla v3.2 congelada en legacy/aquautp_v3.2/data."""

import pytest

from aquaterra.application.servicios import ServicioAutenticacion, ServicioMonitor
from aquaterra.core.domain import Rol
from aquaterra.infrastructure.db.repositorios import RepositorioParcelas, RepositorioRiegos
from aquaterra.infrastructure.legacy.migrador_v32 import migrar_semilla_v32
from tests.conftest import ITERACIONES_TEST, SEMILLA_V32


def test_migra_semilla_completa(db):
    resumen = migrar_semilla_v32(db, SEMILLA_V32, iteraciones_hash=ITERACIONES_TEST)
    assert (resumen.usuarios, resumen.parcelas, resumen.riegos) == (2, 4, 6)
    assert resumen.riegos_huerfanos == []

    ids = [p.id for p in RepositorioParcelas(db).listar()]
    assert ids == [1, 2, 3, 4]  # ids originales conservados

    riegos = RepositorioRiegos(db).listar_por_parcela(3)
    assert riegos[0].ts_iso.endswith("-05:00")
    assert all(r.origen.value == "legacy_v32" for r in riegos)

    consumo = dict(ServicioMonitor(db).consumo_por_parcela())
    assert consumo == {"Invernadero B": 75.0, "Parcela Oeste": 190.0, "Puerta 3": 50.0}


def test_credenciales_legacy_siguen_funcionando_pero_hasheadas(db):
    migrar_semilla_v32(db, SEMILLA_V32, iteraciones_hash=ITERACIONES_TEST)
    hashes = [f[0] for f in db.execute("SELECT hash_clave FROM usuarios")]
    assert all(h.startswith("pbkdf2_sha256$") for h in hashes)
    admin = ServicioAutenticacion(db).iniciar_sesion("admin", "1234")
    assert admin.rol is Rol.ADMIN
    assert ServicioAutenticacion(db).iniciar_sesion("daniel", "1234").rol is Rol.OPERADOR


def test_migracion_no_se_ejecuta_dos_veces(db):
    migrar_semilla_v32(db, SEMILLA_V32, iteraciones_hash=ITERACIONES_TEST)
    with pytest.raises(RuntimeError):
        migrar_semilla_v32(db, SEMILLA_V32, iteraciones_hash=ITERACIONES_TEST)
