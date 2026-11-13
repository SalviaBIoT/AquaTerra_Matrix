"""DT-03: crear y actualizar comparten validación."""

import pytest

from aquaterra.application.servicios import ServicioParcelas
from aquaterra.core.domain import ErrorValidacion, TipoSuelo
from aquaterra.core.domain.validadores import validar_datos_parcela
from tests.conftest import campos_parcela


def test_normaliza_datos_validos():
    datos = validar_datos_parcela(**campos_parcela(nombre="  Lote   Norte ", area="12,5"))
    assert datos.nombre == "Lote Norte"
    assert datos.area_m2 == 12.5
    assert datos.tipo_suelo is TipoSuelo.FRANCO


def test_acumula_todos_los_errores():
    with pytest.raises(ErrorValidacion) as info:
        validar_datos_parcela(**campos_parcela(nombre="", area="abc", humedad=150, suelo="Lunar"))
    assert len(info.value.problemas) == 4


def test_regresion_dt03_actualizar_con_area_no_numerica(db, admin):
    servicio = ServicioParcelas(db)
    parcela = servicio.crear(admin, **campos_parcela())
    with pytest.raises(ErrorValidacion, match="numérica"):
        servicio.actualizar(admin, parcela.id, **campos_parcela(area="doce"))
    assert servicio.obtener(parcela.id).area_m2 == 120  # nada se corrompió
