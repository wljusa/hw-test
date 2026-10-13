"""模拟万用表：识别和直流电压读数。"""
from __future__ import annotations


def test_dmm_idn(bench):
    idn = bench["dmm"].idn()
    assert "HWTEST" in idn
    assert "DMM34401" in idn


def test_dmm_measure_dc(bench):
    reading = bench["dmm"].query_float("MEAS:VOLT:DC?")
    assert abs(reading - 1.234) < 0.001
