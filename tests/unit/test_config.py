"""配置解析。这些测试不打开 VISA。"""
from __future__ import annotations

from pathlib import Path

import pytest

from framework.config import instruments_path, load_bench, resolve_env_name
import framework.config as config


def test_default_env_is_sim(monkeypatch):
    monkeypatch.delenv("HW_ENV", raising=False)
    assert resolve_env_name() == "sim"


def test_hw_env_selects_bench(monkeypatch):
    monkeypatch.setenv("HW_ENV", "bench")
    assert resolve_env_name() == "bench"


def test_unknown_env_rejected():
    with pytest.raises(ValueError, match="sim 或 bench"):
        resolve_env_name("lab")


def test_example_file_used_when_local_is_missing():
    path = instruments_path()
    assert path.name == "instruments.example.yaml"
    loaded = load_bench("sim")
    assert loaded["backend"] == "sim"
    assert loaded["instruments"]["dmm"]["resource"] == "ASRL1::INSTR"
    assert loaded["instruments"]["dmm"]["output_off_on_close"] is False
    assert loaded["instruments"]["psu"]["output_off_on_close"] is True
    assert loaded["instruments"]["psu"]["check_errors"] is True
    assert loaded["instruments"]["psu"]["reset_on_open"] is True
    assert loaded["instruments"]["dmm"]["read_termination"] == "\n"
    assert Path(loaded["sim_file"]).is_file()


def test_bench_backend_is_py():
    loaded = load_bench("bench")
    assert loaded["backend"] == "py"
    assert loaded["sim_file"] is None
    assert loaded["instruments"]["psu"]["output_off_on_close"] is True


def test_local_file_wins(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "instruments.example.yaml").write_text("sim: {}\n", encoding="utf-8")
    local = config_dir / "instruments.yaml"
    local.write_text("sim: {}\n", encoding="utf-8")
    assert instruments_path() == local


def test_missing_resource(tmp_path):
    path = tmp_path / "instruments.yaml"
    path.write_text(
        "sim:\n  backend: sim\n  sim_file: sim/bench.yaml\n  instruments:\n    dmm: {}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="resource"):
        load_bench("sim", path)


def test_missing_sim_file(tmp_path):
    path = tmp_path / "instruments.yaml"
    path.write_text(
        "sim:\n"
        "  backend: sim\n"
        "  sim_file: missing.yaml\n"
        "  instruments:\n"
        "    dmm:\n"
        "      resource: ASRL1::INSTR\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="找不到模拟台架"):
        load_bench("sim", path)
