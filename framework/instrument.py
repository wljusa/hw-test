"""单台仪器：SCPI 收发、识别、复位、错误队列和收尾。"""
from __future__ import annotations

from typing import Any, List, Sequence, Tuple


class InstrumentError(Exception):
    """仪器返回了非 0 的 SCPI 错误。"""


def release_commands(output_off_on_close: bool, check_errors: bool) -> List[str]:
    """收尾时要发的指令。先关输出，再查错误队列。"""
    commands: List[str] = []
    if output_off_on_close:
        commands.append("OUTP OFF")
    if check_errors:
        commands.append("SYST:ERR?")
    return commands


def is_no_error(message: str) -> bool:
    """SCPI 错误码 0 或 +0 表示队列已空。"""
    head = message.split(",", 1)[0].strip().lstrip("+")
    return head == "0"


class Instrument:
    """包装一台已打开的 VISA 资源。指令本身不带结束符。"""

    def __init__(
        self,
        resource: Any,
        alias: str,
        *,
        timeout_ms: int,
        read_termination: str,
        write_termination: str,
        reset_on_open: bool,
        output_off_on_close: bool,
        check_errors: bool,
    ) -> None:
        self.alias = alias
        self.resource = resource
        self.output_off_on_close = output_off_on_close
        self.check_errors = check_errors
        self._log: List[Tuple[str, str]] = []
        self._quiesced = False
        self._closed = False
        resource.timeout = timeout_ms
        resource.read_termination = read_termination
        resource.write_termination = write_termination
        if reset_on_open:
            self.reset()

    def write(self, command: str) -> None:
        self._log.append((">>", command))
        self.resource.write(command)

    def query(self, command: str) -> str:
        self._log.append((">>", command))
        text = _as_text(self.resource.query(command))
        self._log.append(("<<", text))
        return text

    def query_float(self, command: str) -> float:
        text = self.query(command)
        try:
            return float(text)
        except ValueError as exc:
            raise ValueError(f"{self.alias} {command} 的响应不是数值: {text}") from exc

    def expect_float(self, command: str, expected: float, abs_tol: float) -> float:
        """查询数值，超出绝对容差则断言失败。"""
        value = self.query_float(command)
        if abs(value - expected) > abs_tol:
            raise AssertionError(
                f"{self.alias} {command} 得到 {value}，期望 {expected} ± {abs_tol}"
            )
        return value

    def idn(self) -> str:
        return self.query("*IDN?")

    def reset(self) -> None:
        self.write("*RST")
        self.write("*CLS")

    def error_queue(self, limit: int = 8) -> List[str]:
        """读 SYST:ERR? 直到 0，或达到 limit。"""
        errors: List[str] = []
        for _ in range(limit):
            line = self.query("SYST:ERR?")
            errors.append(line)
            if is_no_error(line):
                break
        return errors

    def transcript(self) -> str:
        return "\n".join(f"{direction} {text}" for direction, text in self._log)

    def quiesce(self) -> None:
        """关输出并检查错误队列。重复调用只执行一次。"""
        if self._quiesced:
            return
        self._quiesced = True
        for command in release_commands(self.output_off_on_close, self.check_errors):
            if command == "SYST:ERR?":
                self._assert_no_errors()
            else:
                self.write(command)

    def close(self) -> None:
        if self._closed:
            return
        error: Exception | None = None
        try:
            self.quiesce()
        except Exception as exc:
            error = exc
        self._closed = True
        try:
            self.resource.close()
        except Exception as exc:
            if error is None:
                error = exc
        if error is not None:
            raise error

    def _assert_no_errors(self) -> None:
        errors = self.error_queue()
        bad = [line for line in errors if not is_no_error(line)]
        if bad:
            raise InstrumentError(f"{self.alias} SCPI 错误: {bad}")
        if not errors or not is_no_error(errors[-1]):
            raise InstrumentError(f"{self.alias} 错误队列未排空: {errors}")


def format_transcript(items: Sequence[Tuple[str, Instrument]]) -> str:
    parts = [f"# {alias}\n{inst.transcript()}".rstrip() for alias, inst in items]
    return "\n".join(part for part in parts if part.strip())


def _as_text(value: Any) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return str(value).strip()
