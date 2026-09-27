"""Tests for the audit log API (app/api/audit.py).

Covers the rewritten loader: per-file mtime/size entry cache, cache
invalidation on append, filters (event type / username / status), and
symmetric status matching across the two notations the system writes —
numeric HTTP codes (AuditLogMiddleware) and success/failure (AuditLogger).
"""

import importlib
import json
import os
import tempfile
import threading
import time
from pathlib import Path

import pytest

from app.core.security import TokenData


@pytest.fixture(scope="module")
def audit_env():
    """Redirect the audit API at a temp log dir for the whole module.

    The module binds LOG_DIR at import time, so it is reloaded once the
    env var is set; original state is restored afterwards.
    """
    log_dir = Path(tempfile.mkdtemp(prefix="raildoc_audit_test_"))
    os.environ["AUDIT_LOG_DIR"] = str(log_dir)

    from app.api import audit as audit_mod

    saved_dir = audit_mod.LOG_DIR
    saved_cache = dict(audit_mod._entry_cache)
    audit_mod._entry_cache.clear()
    importlib.reload(audit_mod)
    yield log_dir
    audit_mod.LOG_DIR = saved_dir
    audit_mod._entry_cache.clear()
    audit_mod._entry_cache.update(saved_cache)
    os.environ.pop("AUDIT_LOG_DIR", None)


@pytest.fixture()
def admin():
    return TokenData(username="tester", roles=["admin"])


@pytest.fixture(autouse=True)
def _clean_log_dir(audit_env):
    """The log dir is module-scoped for speed — wipe it between tests so
    files written by one test cannot leak into another's plain loads."""
    from app.api import audit as audit_mod

    for f in audit_env.glob("*.log"):
        f.unlink(missing_ok=True)
    audit_mod._entry_cache.clear()
    yield


def _logs(audit_mod, admin, **kw):
    params = dict(event_type=None, username=None, status=None, date=None, limit=200)
    params.update(kw)
    return audit_mod.get_audit_logs(current_user=admin, **params)


def _write_entries(log_dir: Path, entries: list[dict], name: str = "audit_20260924.log") -> Path:
    log_file = log_dir / name
    log_file.write_text(
        "\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8"
    )
    return log_file


SAMPLE = [
    {"timestamp": "2026-09-24T10:00:00Z", "event_type": "user_login", "username": "admin", "status": "success"},
    {"timestamp": "2026-09-24T10:05:00Z", "event_type": "simulation_run", "username": "planner", "status": 200},
    {"timestamp": "2026-09-24T10:10:00Z", "event_type": "plan_approved", "username": "admin", "status": "success"},
    {"timestamp": "2026-09-24T10:15:00Z", "event_type": "unauthorized_access", "username": "ghost", "status": 401},
    {"timestamp": "2026-09-24T10:20:00Z", "event_type": "plan_rejected", "username": "ops", "status": "failure"},
    {"timestamp": "2026-09-24T10:25:00Z", "event_type": "api_request", "username": "ghost", "status": 500},
]


class TestAuditLogs:

    def test_plain_load_and_ordering(self, audit_env, admin):
        from app.api import audit as audit_mod

        _write_entries(audit_env, SAMPLE)
        r = _logs(audit_mod, admin)
        assert r["total"] == 6
        # newest-first
        assert r["entries"][0]["event_type"] == "api_request"
        assert r["entries"][-1]["event_type"] == "user_login"

    def test_username_filter(self, audit_env, admin):
        from app.api import audit as audit_mod

        _write_entries(audit_env, SAMPLE)
        r = _logs(audit_mod, admin, username="admin")
        assert r["total"] == 2
        assert all(e["username"] == "admin" for e in r["entries"])

    def test_numeric_status_matches_textual_entries(self, audit_env, admin):
        """status=200 must match both the numeric 200 row and the textual
        success rows — the middleware and AuditLogger use different
        notations for the same outcome."""
        from app.api import audit as audit_mod

        _write_entries(audit_env, SAMPLE)
        r = _logs(audit_mod, admin, status="200")
        assert r["total"] == 3
        assert all(str(e["status"]) in ("200", "success") for e in r["entries"])

    def test_textual_status_matches_numeric_entries(self, audit_env, admin):
        from app.api import audit as audit_mod

        _write_entries(audit_env, SAMPLE)
        failure = _logs(audit_mod, admin, status="failure")
        success = _logs(audit_mod, admin, status="success")
        assert failure["total"] == 3  # 401, "failure", 500
        assert success["total"] == 3  # 200, "success" x2

    def test_event_type_filter(self, audit_env, admin):
        from app.api import audit as audit_mod

        _write_entries(audit_env, SAMPLE)
        r = _logs(audit_mod, admin, event_type="user_login")
        assert r["total"] == 1
        assert r["entries"][0]["event_type"] == "user_login"

    def test_limit_is_respected_but_total_is_whole(self, audit_env, admin):
        from app.api import audit as audit_mod

        _write_entries(audit_env, SAMPLE)
        r = _logs(audit_mod, admin, limit=2)
        assert len(r["entries"]) == 2 and r["total"] == 6

    def test_date_filter_selects_single_file(self, audit_env, admin):
        from app.api import audit as audit_mod

        _write_entries(audit_env, SAMPLE)
        _write_entries(
            audit_env,
            [{"timestamp": "2026-01-01T00:00:00Z", "event_type": "user_login",
              "username": "old", "status": "success"}],
            name="audit_20260101.log",
        )
        r = _logs(audit_mod, admin, date="20260101")
        assert r["total"] == 1 and r["entries"][0]["username"] == "old"

    def test_missing_dir_returns_empty(self, audit_env, admin, monkeypatch):
        from app.api import audit as audit_mod

        monkeypatch.setattr(audit_mod, "LOG_DIR", Path("Z:/definitely/not/here"))
        r = _logs(audit_mod, admin)
        assert r == {"entries": [], "total": 0}

    def test_corrupt_lines_are_skipped(self, audit_env, admin):
        from app.api import audit as audit_mod

        log_file = audit_env / "audit_corrupt.log"
        log_file.write_text(
            json.dumps(SAMPLE[0]) + "\n"
            + "{not valid json\n"
            + json.dumps(SAMPLE[1]) + "\n",
            encoding="utf-8",
        )
        r = _logs(audit_mod, admin)
        assert r["total"] == 2


class TestAuditCache:

    def test_cache_hit_and_invalidation(self, audit_env, admin):
        from app.api import audit as audit_mod

        log_file = _write_entries(audit_env, SAMPLE)
        first = _logs(audit_mod, admin)
        assert str(log_file) in audit_mod._entry_cache
        cached_list = audit_mod._entry_cache[str(log_file)][2]

        second = _logs(audit_mod, admin)
        # identical result served from the same parsed list object
        assert second["total"] == first["total"]
        assert audit_mod._entry_cache[str(log_file)][2] is cached_list

        # an append changes mtime+size → reparse picks up the new entry
        time.sleep(0.02)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": "2026-09-24T10:30:00Z",
                "event_type": "weights_updated",
                "username": "admin",
                "status": "success",
            }) + "\n")
        r = _logs(audit_mod, admin)
        assert r["total"] == 7
        assert audit_mod._entry_cache[str(log_file)][2] is not cached_list

    def test_cache_is_thread_safe(self, audit_env, admin):
        """Concurrent readers must not corrupt the shared cache."""
        from app.api import audit as audit_mod

        _write_entries(audit_env, SAMPLE)
        errors: list[Exception] = []

        def reader():
            try:
                for _ in range(20):
                    r = _logs(audit_mod, admin)
                    assert r["total"] == 6
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=reader) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors


class TestAuditStats:

    def test_stats_totals(self, audit_env, admin):
        from app.api import audit as audit_mod

        _write_entries(audit_env, SAMPLE)
        s = audit_mod.get_audit_stats(current_user=admin, date=None)
        assert s["total"] == 6
        assert s["status_counts"].get("success") == 2
        assert s["user_counts"].get("ghost") == 2
        assert s["event_counts"].get("user_login") == 1

    def test_stats_missing_dir(self, audit_env, admin, monkeypatch):
        from app.api import audit as audit_mod

        monkeypatch.setattr(audit_mod, "LOG_DIR", Path("Z:/definitely/not/here"))
        s = audit_mod.get_audit_stats(current_user=admin, date=None)
        assert s == {"total": 0, "event_counts": {}, "user_counts": {}, "status_counts": {}}


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
