from datetime import date, time

import pytest

from aquaterra.core import tiempo


def test_iso_lleva_desfase_colombia():
    momento = tiempo.combinar(date(2026, 11, 13), time(6, 0))
    assert tiempo.a_iso(momento) == "2026-11-13T06:00:00-05:00"


def test_epoch_ida_y_vuelta():
    momento = tiempo.combinar(date(2026, 1, 1), time(0, 0))
    assert tiempo.a_epoch(momento) == 1767243600  # 2026-01-01T05:00:00Z
    assert tiempo.desde_epoch(tiempo.a_epoch(momento)) == momento


def test_fecha_legacy_mdy_y_hora_sin_cero():
    momento = tiempo.parsear_fecha_legacy_v32("11/27/25", "8:00")
    assert tiempo.a_iso(momento) == "2025-11-27T08:00:00-05:00"


@pytest.mark.parametrize("hora", ["24:00", "7", "07:60", "abc", ""])
def test_hora_invalida(hora):
    with pytest.raises(ValueError):
        tiempo.parsear_hora(hora)
