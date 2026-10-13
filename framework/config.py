"""按 HW_ENV / --env 读取仪器配置。资源地址只来自 yaml。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENTS = ("sim", "bench")
BACKENDS = ("sim", "py")


def resolve_env_name(explicit: Optional[str] = None) -> str:
    """优先显式参数，其次 HW_ENV，默认 sim。"""
    name = (explicit or os.environ.get("HW_ENV") or "sim").strip().lower()
    if name not in ENVIRONMENTS:
        raise ValueError("HW_ENV/--env 仅支持 sim 或 bench")
    return name


def instruments_path() -> Path:
    """本地 instruments.yaml 优先；没有则用仓库里的示例。"""
    local = ROOT / "config" / "instruments.yaml"
    if local.is_file():
        return local
    return ROOT / "config" / "instruments.example.yaml"


def load_bench(env: Optional[str] = None, path: Optional[Path] = None) -> Dict[str, Any]:
    """返回当前环境的台架配置。sim_file 解析为绝对路径。"""
    env_name = resolve_env_name(env)
    source = Path(path) if path is not None else instruments_path()
    raw = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict) or env_name not in raw:
        raise ValueError(f"{source} 缺少环境 {env_name}")
    block = raw[env_name]
    if not isinstance(block, dict):
        raise ValueError(f"环境 {env_name} 必须是映射")

    backend = str(block.get("backend") or "").strip().lower()
    if backend not in BACKENDS:
        raise ValueError("backend 仅支持 sim 或 py")

    timeout_ms = _timeout(block.get("timeout_ms"), 5000)
    instruments = _instruments(block.get("instruments"), timeout_ms)
    sim_file = _sim_file(backend, block.get("sim_file"))
    return {
        "env": env_name,
        "backend": backend,
        "sim_file": sim_file,
        "timeout_ms": timeout_ms,
        "instruments": instruments,
    }


def _instruments(raw: Any, default_timeout: int) -> Dict[str, Dict[str, Any]]:
    if not isinstance(raw, dict) or not raw:
        raise ValueError("instruments 不能为空")
    normalized: Dict[str, Dict[str, Any]] = {}
    for alias, spec in raw.items():
        if not isinstance(spec, dict):
            raise ValueError(f"{alias} 的配置必须是映射")
        resource = str(spec.get("resource") or "").strip()
        if not resource:
            raise ValueError(f"{alias} 缺少 resource")
        normalized[str(alias)] = {
            "resource": resource,
            "read_termination": _termination(spec.get("read_termination", "\n")),
            "write_termination": _termination(spec.get("write_termination", "\n")),
            "timeout_ms": _timeout(spec.get("timeout_ms"), default_timeout),
            "reset_on_open": _as_bool(spec.get("reset_on_open"), False),
            "output_off_on_close": _as_bool(spec.get("output_off_on_close"), False),
            "check_errors": _as_bool(spec.get("check_errors"), False),
        }
    return normalized


def _sim_file(backend: str, raw: Any) -> Optional[str]:
    if backend != "sim":
        return None
    if not raw:
        raise ValueError("sim 后端需要 sim_file")
    path = Path(str(raw))
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve()
    if not path.is_file():
        raise ValueError(f"找不到模拟台架 {path}")
    return str(path)


def _timeout(value: Any, default: int) -> int:
    if value is None:
        return default
    try:
        timeout = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"timeout_ms 必须是整数: {value}") from exc
    if timeout <= 0:
        raise ValueError("timeout_ms 必须大于 0")
    return timeout


def _termination(value: Any) -> str:
    text = "\n" if value is None else str(value)
    return text.replace("\\r", "\r").replace("\\n", "\n")


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
    raise ValueError(f"无法解析布尔值: {value}")
