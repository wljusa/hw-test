"""Pytest 入口：选择 sim 或 bench，提供 bench 夹具，失败时附上 SCPI 记录。"""
from __future__ import annotations

import os

import allure
import pytest

from framework.session import Bench


def pytest_addoption(parser):
    parser.addoption(
        "--env",
        action="store",
        default=None,
        choices=["sim", "bench"],
        help="选择运行环境: sim 或 bench",
    )


def pytest_configure(config):
    env_from_cli = config.getoption("--env")
    env_name = (os.environ.get("HW_ENV") or env_from_cli or "sim").strip().lower()
    if env_name not in ("sim", "bench"):
        raise pytest.UsageError("HW_ENV/--env 仅支持 sim 或 bench")
    os.environ["HW_ENV"] = env_name


@pytest.fixture
def bench():
    session = Bench.open_from_config()
    try:
        yield session
    finally:
        session.close()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when not in {"call", "teardown"} or not report.failed:
        return
    session = item.funcargs.get("bench")
    if session is None:
        return
    text = session.transcript()
    if not text.strip():
        return
    allure.attach(text, name="SCPI", attachment_type=allure.attachment_type.TEXT)
