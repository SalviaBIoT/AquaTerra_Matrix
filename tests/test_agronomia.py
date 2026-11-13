import math

import pytest

from aquaterra.core.agronomia.hidrico import decidir_riego
from aquaterra.core.agronomia.psicrometria import ZonaVPD, clasificar_vpd, presion_saturacion_kpa, vpd_kpa


def test_tetens_valores_de_referencia_fao56():
    # FAO-56, Anexo 2 (tabla 2.3): e_s(20 °C)=2.338 kPa, e_s(30 °C)=4.243 kPa
    assert math.isclose(presion_saturacion_kpa(20.0), 2.338, abs_tol=0.002)
    assert math.isclose(presion_saturacion_kpa(30.0), 4.243, abs_tol=0.002)


def test_vpd_aire_saturado_es_cero_y_aire_seco_es_es():
    assert vpd_kpa(25.0, 100.0) == 0.0
    assert math.isclose(vpd_kpa(25.0, 0.0), presion_saturacion_kpa(25.0), abs_tol=1e-3)


def test_vpd_caso_tipico_cafetero():
    # 24 °C y 68 % HR -> ~0.95 kPa (zona óptima)
    vpd = vpd_kpa(24.0, 68.0)
    assert 0.9 < vpd < 1.0
    assert clasificar_vpd(vpd) is ZonaVPD.OPTIMA


@pytest.mark.parametrize("vpd,zona", [
    (0.2, ZonaVPD.RIESGO_FUNGICO), (0.6, ZonaVPD.PROPAGACION), (1.0, ZonaVPD.OPTIMA),
    (1.4, ZonaVPD.FLORACION), (2.1, ZonaVPD.ESTRES_HIDRICO),
])
def test_clasificacion_vpd(vpd, zona):
    assert clasificar_vpd(vpd) is zona


def test_vpd_rechaza_entradas_fisicamente_imposibles():
    with pytest.raises(ValueError):
        vpd_kpa(25.0, 120.0)
    with pytest.raises(ValueError):
        presion_saturacion_kpa(-200.0)  # Lectura fallida típica del DHT22


def test_decision_riego_por_umbral():
    assert decidir_riego(30, 45).regar is True
    assert decidir_riego(45, 45).regar is False
