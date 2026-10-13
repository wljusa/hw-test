"""按配置打开一台台架，结束时收尾并关闭 VISA。"""
from __future__ import annotations

from typing import Any, Dict, Iterator, Optional

from framework.config import load_bench
from framework.instrument import Instrument, format_transcript


class Bench:
    """别名到仪器的映射。测试通过 bench['dmm'] 取仪器。"""

    def __init__(self, settings: Dict[str, Any]) -> None:
        self.settings = settings
        self._rm: Any = None
        self._opened: Dict[str, Instrument] = {}

    @classmethod
    def open_from_config(cls, env: Optional[str] = None) -> "Bench":
        bench = cls(load_bench(env))
        bench.open()
        return bench

    def open(self) -> "Bench":
        self._rm = _resource_manager(self.settings)
        try:
            timeout = int(self.settings["timeout_ms"])
            for alias, spec in self.settings["instruments"].items():
                self._opened[alias] = self._open_one(alias, spec, timeout)
        except Exception:
            self.close()
            raise
        return self

    def __getitem__(self, alias: str) -> Instrument:
        try:
            return self._opened[alias]
        except KeyError:
            known = ", ".join(sorted(self._opened)) or "无"
            raise KeyError(f"未配置仪器 {alias}，当前有: {known}") from None

    def __iter__(self) -> Iterator[str]:
        return iter(self._opened)

    def transcript(self) -> str:
        return format_transcript(list(self._opened.items()))

    def close(self) -> None:
        errors: list[BaseException] = []
        for inst in self._opened.values():
            try:
                inst.close()
            except Exception as exc:
                errors.append(exc)
        if self._rm is not None:
            try:
                self._rm.close()
            except Exception as exc:
                errors.append(exc)
            finally:
                self._rm = None
        if errors:
            raise errors[0]

    def _open_one(self, alias: str, spec: Dict[str, Any], timeout: int) -> Instrument:
        try:
            resource = self._rm.open_resource(spec["resource"])
        except Exception as exc:
            raise RuntimeError(f"打开仪器 {alias}（{spec['resource']}）失败") from exc
        return Instrument(
            resource,
            alias,
            timeout_ms=int(spec.get("timeout_ms") or timeout),
            read_termination=spec["read_termination"],
            write_termination=spec["write_termination"],
            reset_on_open=bool(spec["reset_on_open"]),
            output_off_on_close=bool(spec["output_off_on_close"]),
            check_errors=bool(spec["check_errors"]),
        )


def _resource_manager(settings: Dict[str, Any]) -> Any:
    import pyvisa
    import pyvisa_sim  # noqa: F401  注册 @sim 后端

    backend = settings["backend"]
    if backend == "sim":
        return pyvisa.ResourceManager(f"{settings['sim_file']}@sim")
    if backend == "py":
        return pyvisa.ResourceManager("@py")
    raise ValueError(f"不支持的 VISA 后端: {backend}")
