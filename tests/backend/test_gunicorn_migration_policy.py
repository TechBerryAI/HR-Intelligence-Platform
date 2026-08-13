"""Gunicorn master must verify schema, never upgrade."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parents[2] / "apps" / "backend"


def _load_gunicorn_conf():
    spec = importlib.util.spec_from_file_location(
        "hcip_gunicorn_conf",
        BACKEND / "gunicorn.conf.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_gunicorn_on_starting_verifies_and_sets_skip_flag(monkeypatch):
    monkeypatch.delenv("HCIP_MIGRATIONS_DONE", raising=False)
    monkeypatch.setenv("MIGRATIONS_ALREADY_APPLIED", "true")
    calls = {"prepare": 0, "upgrade": 0}

    def fake_prepare():
        calls["prepare"] += 1
        return "20260812_ext_outbox"

    monkeypatch.setattr(
        "app.config.env_validator.EnvValidator.print_report",
        classmethod(lambda cls: True),
    )
    monkeypatch.setattr(
        "app.database.alembic_runner.prepare_schema_for_web_process",
        fake_prepare,
    )
    monkeypatch.setattr(
        "app.database.alembic_runner.upgrade_head",
        lambda: calls.__setitem__("upgrade", calls["upgrade"] + 1),
    )
    mod = _load_gunicorn_conf()
    assert "upgrade_head()" not in Path(mod.__file__).read_text(encoding="utf-8")
    mod.on_starting(SimpleNamespace())
    assert calls["prepare"] == 1
    assert calls["upgrade"] == 0
    assert __import__("os").environ.get("HCIP_MIGRATIONS_DONE") == "1"
    assert __import__("os").environ.get("MIGRATIONS_ALREADY_APPLIED", "").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
