"""DT-05b: contraseñas con hash; login con rehash transparente."""

import pytest

from aquaterra.application.servicios import ServicioAutenticacion
from aquaterra.core.domain import ErrorAutenticacion
from aquaterra.infrastructure.db.repositorios import RepositorioAuditoria, RepositorioUsuarios
from aquaterra.infrastructure.seguridad import generar_hash, requiere_rehash, verificar_clave
from tests.conftest import ITERACIONES_TEST


def test_hash_no_contiene_la_clave_y_usa_salt():
    h1 = generar_hash("1234", iteraciones=ITERACIONES_TEST)
    h2 = generar_hash("1234", iteraciones=ITERACIONES_TEST)
    assert "1234" not in h1.split("$", 2)[2]
    assert h1 != h2                      # salt distinto por usuario
    assert verificar_clave("1234", h1) and verificar_clave("1234", h2)
    assert not verificar_clave("12345", h1)


@pytest.mark.parametrize("basura", ["", "1234", "md5$x$y$z", "pbkdf2_sha256$no$es$b64"])
def test_hash_malformado_nunca_autentica(basura):
    assert verificar_clave("1234", basura) is False


def test_login_exitoso_rehashea_hash_debil(db, admin):
    _, hash_inicial = RepositorioUsuarios(db).credenciales("admin_t")
    assert requiere_rehash(hash_inicial)  # 1 000 iteraciones < 600 000
    usuario = ServicioAutenticacion(db).iniciar_sesion("ADMIN_T", "clave")  # usuario sin distinguir mayúsculas
    assert usuario.id == admin.id
    _, hash_nuevo = RepositorioUsuarios(db).credenciales("admin_t")
    assert not requiere_rehash(hash_nuevo)


def test_login_fallido_es_generico_y_auditado(db, admin):
    with pytest.raises(ErrorAutenticacion, match="Usuario o contraseña incorrectos"):
        ServicioAutenticacion(db).iniciar_sesion("admin_t", "mala")
    with pytest.raises(ErrorAutenticacion):
        ServicioAutenticacion(db).iniciar_sesion("no_existe", "x")
    assert len([f for f in RepositorioAuditoria(db).listar("usuario") if f["accion"] == "login_fallido"]) == 2
