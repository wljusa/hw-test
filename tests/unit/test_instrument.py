"""收尾策略。用假资源，不打开 VISA。"""
from __future__ import annotations

import pytest

from framework.instrument import Instrument, InstrumentError, is_no_error, release_commands


class FakeResource:
    def __init__(self, errors=None):
        self.commands = []
        self.errors = list(errors or ['0,"No error"'])
        self.timeout = 0
        self.read_termination = ""
        self.write_termination = ""
        self.closed = False

    def write(self, command: str) -> None:
        self.commands.append(("write", command))

    def query(self, command: str) -> str:
        self.commands.append(("query", command))
        if command == "SYST:ERR?":
            if self.errors:
                return self.errors.pop(0)
            return '0,"No error"'
        if command == "OUTP?":
            return "OFF"
        return "0"

    def close(self) -> None:
        self.closed = True


def _instrument(raw, **overrides) -> Instrument:
    options = dict(
        timeout_ms=1000,
        read_termination="\n",
        write_termination="\n",
        reset_on_open=False,
        output_off_on_close=False,
        check_errors=False,
    )
    options.update(overrides)
    return Instrument(raw, "psu", **options)


def test_release_commands():
    assert release_commands(True, True) == ["OUTP OFF", "SYST:ERR?"]
    assert release_commands(False, False) == []


def test_is_no_error():
    assert is_no_error('0,"No error"')
    assert is_no_error("+0, No error")
    assert not is_no_error('1,"Command error"')


def test_quiesce_turns_output_off_then_checks_errors():
    raw = FakeResource()
    inst = _instrument(raw, output_off_on_close=True, check_errors=True)
    inst.quiesce()
    assert raw.commands == [("write", "OUTP OFF"), ("query", "SYST:ERR?")]
    inst.quiesce()
    assert raw.commands == [("write", "OUTP OFF"), ("query", "SYST:ERR?")]


def test_close_still_closes_when_error_queue_is_dirty():
    raw = FakeResource(['1,"Command error"', '0,"No error"'])
    inst = _instrument(raw, check_errors=True)
    with pytest.raises(InstrumentError, match="SCPI 错误"):
        inst.close()
    assert raw.closed


def test_reset_on_open():
    raw = FakeResource()
    _instrument(raw, reset_on_open=True)
    assert raw.commands == [("write", "*RST"), ("write", "*CLS")]


def test_expect_float_rejects_out_of_tolerance():
    raw = FakeResource()

    def query(command: str) -> str:
        raw.commands.append(("query", command))
        return "1.200"

    raw.query = query
    inst = _instrument(raw)
    with pytest.raises(AssertionError, match="期望 1.234"):
        inst.expect_float("MEAS:VOLT:DC?", 1.234, abs_tol=0.001)
