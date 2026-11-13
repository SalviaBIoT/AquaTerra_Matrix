"""DT-01 (integridad de ids), atomicidad del riego, permisos y auditoría."""

import sqlite3
from datetime import date

import pytest

from aquaterra.application.servicios import ServicioMonitor, ServicioParcelas, ServicioRiego
from aquaterra.core.domain import EntidadNoEncontrada, ErrorPermiso, ErrorValidacion
from aquaterra.infrastructure.db.esquema import VERSION_ESQUEMA, aplicar_migraciones, version_actual
from aquaterra.infrastructure.db.repositorios import RepositorioAuditoria, RepositorioRiegos
from tests.conftest import campos_parcela


def _regar(db, actor, pid, litros=50):
    return ServicioRiego(db).aplicar_riego(actor, parcela_id=pid, umbral_pct=45, litros=litros,
                                           fecha=date(2026, 11, 13), hora="06:00")


def test_migraciones_idempotentes(db):
    assert version_actual(db) == VERSION_ESQUEMA
    assert aplicar_migraciones(db) == VERSION_ESQUEMA


def test_regresion_dt01_archivar_no_renumera_ni_rompe_riegos(db, admin):
    servicio = ServicioParcelas(db)
    p1 = servicio.crear(admin, **campos_parcela(nombre="P1"))
    p2 = servicio.crear(admin, **campos_parcela(nombre="P2"))
    p3 = servicio.crear(admin, **campos_parcela(nombre="P3"))
    _regar(db, admin, p3.id)

    servicio.archivar(admin, p2.id)

    activas = [p.id for p in servicio.listar()]
    assert activas == [p1.id, p3.id]                       # p3 conserva su id
    riegos_p3 = RepositorioRiegos(db).listar_por_parcela(p3.id)
    assert len(riegos_p3) == 1                             # su historial sigue vinculado
    p4 = servicio.crear(admin, **campos_parcela(nombre="P4"))
    assert p4.id == p3.id + 1                              # AUTOINCREMENT: ids nunca se reutilizan


def test_la_base_impide_borrado_fisico_con_historial(db, admin):
    p = ServicioParcelas(db).crear(admin, **campos_parcela())
    _regar(db, admin, p.id)
    with pytest.raises(sqlite3.IntegrityError), db:
        db.execute("DELETE FROM parcelas WHERE id = ?", (p.id,))


def test_nombre_duplicado_entre_activas(db, admin):
    servicio = ServicioParcelas(db)
    servicio.crear(admin, **campos_parcela(nombre="Lote A"))
    with pytest.raises(ErrorValidacion):
        servicio.crear(admin, **campos_parcela(nombre="lote a"))


def test_operador_no_puede_mutar(db, admin, operador):
    servicio = ServicioParcelas(db)
    p = servicio.crear(admin, **campos_parcela())
    with pytest.raises(ErrorPermiso):
        servicio.crear(operador, **campos_parcela(nombre="Otra"))
    with pytest.raises(ErrorPermiso):
        servicio.archivar(operador, p.id)
    with pytest.raises(ErrorPermiso):
        _regar(db, operador, p.id)


def test_riego_actualiza_humedad_y_registra_evento(db, admin):
    p = ServicioParcelas(db).crear(admin, **campos_parcela(humedad=30))
    resultado = _regar(db, admin, p.id, litros=75)
    assert resultado.aplicado
    assert resultado.parcela.humedad_pct == 95
    assert resultado.evento.ts_iso == "2026-11-13T06:00:00-05:00"
    assert resultado.evento.humedad_inicial_pct == 30


def test_riego_no_requerido_no_escribe(db, admin):
    p = ServicioParcelas(db).crear(admin, **campos_parcela(humedad=80))
    assert not _regar(db, admin, p.id).aplicado
    assert RepositorioRiegos(db).contar() == 0


def test_riego_es_atomico_si_falla_el_evento(db, admin, monkeypatch):
    p = ServicioParcelas(db).crear(admin, **campos_parcela(humedad=30))

    def falla(*_a, **_k):
        raise sqlite3.OperationalError("disco lleno simulado")

    monkeypatch.setattr(RepositorioRiegos, "registrar", falla)
    with pytest.raises(sqlite3.OperationalError):
        _regar(db, admin, p.id)
    assert ServicioParcelas(db).obtener(p.id).humedad_pct == 30  # rollback de la humedad


def test_riego_sobre_parcela_archivada(db, admin):
    servicio = ServicioParcelas(db)
    p = servicio.crear(admin, **campos_parcela())
    servicio.archivar(admin, p.id)
    with pytest.raises(EntidadNoEncontrada):
        _regar(db, admin, p.id)


def test_consumo_agrupa_por_id_aunque_se_renombre(db, admin):
    servicio = ServicioParcelas(db)
    p = servicio.crear(admin, **campos_parcela(nombre="Viejo", humedad=10))
    _regar(db, admin, p.id, litros=40)
    servicio.actualizar(admin, p.id, **campos_parcela(nombre="Nuevo", humedad=10))
    _regar(db, admin, p.id, litros=60)
    assert ServicioMonitor(db).consumo_por_parcela() == [("Nuevo", 100.0)]


def test_auditoria_registra_mutaciones(db, admin):
    servicio = ServicioParcelas(db)
    p = servicio.crear(admin, **campos_parcela())
    servicio.actualizar(admin, p.id, **campos_parcela(area="200"))
    servicio.archivar(admin, p.id)
    acciones = [f["accion"] for f in RepositorioAuditoria(db).listar("parcela")]
    assert acciones == ["crear", "actualizar", "archivar"]
