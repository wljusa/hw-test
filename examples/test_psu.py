"""模拟直流电源：设电压，结束时关闭输出。"""
from __future__ import annotations


def test_psu_idn(bench):
    assert "PSU" in bench["psu"].idn()


def test_psu_set_voltage(bench):
    psu = bench["psu"]
    psu.write("VOLT 5")
    psu.expect_float("VOLT?", 5, abs_tol=0.001)


def test_psu_output_off_on_close(bench):
    psu = bench["psu"]
    psu.write("OUTP ON")
    assert psu.query("OUTP?") == "ON"
    psu.quiesce()
    assert psu.query("OUTP?") == "OFF"
