"""Tests for scripts/check_env.py — the .env JSON sanity checker used by
start.cmd / start.sh.

The checker must:
  * pass a well-formed .env (exit 0)
  * pass empty values (SSL_KEYFILE="" etc.) — regression: value[:1] in "[{"
    was True for "" and json.loads("") raised a false positive
  * pass escaped-JSON values of both .env quoting conventions
  * fail a .env whose JSON-looking value does not parse (exit 1)
  * ignore comments, blank lines, section headers, non-JSON values
  * tolerate a missing file (start.cmd runs it before any install step)
  * exit 1 — not crash — on a non-UTF-8 .env
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
CHECK_ENV = SCRIPTS_DIR / "check_env.py"


def run_checker(tmp_path: Path, content: str | bytes, name: str = ".env") -> subprocess.CompletedProcess:
    env_file = tmp_path / name
    if isinstance(content, bytes):
        env_file.write_bytes(content)
    else:
        env_file.write_text(content, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(CHECK_ENV), str(env_file)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class TestValidEnvFiles:
    def test_well_formed_env_passes(self, tmp_path):
        r = run_checker(tmp_path, 'SUPABASE_URL="https://x.supabase.co"\nPORT=8000\n')
        assert r.returncode == 0

    def test_empty_values_do_not_crash(self, tmp_path):
        """Regression: value[:1] in "[{" was True for the empty string."""
        r = run_checker(
            tmp_path,
            'SSL_KEYFILE=""\nSSL_CERTFILE=""\nTMS_API_URL=""\n'
            "EMPTY_BARE=\nQUOTED_EMPTY=''\n",
        )
        assert r.returncode == 0

    def test_valid_json_object_passes(self, tmp_path):
        r = run_checker(tmp_path, 'CONN="{\\"a\\": 1}"\n')
        assert r.returncode == 0

    def test_valid_json_object_single_quote_wrapped(self, tmp_path):
        r = run_checker(tmp_path, "CONN='{\"a\": 1}'\n")
        assert r.returncode == 0

    def test_valid_json_array_backslash_escaped(self, tmp_path):
        r = run_checker(tmp_path, 'LIST="{\\"x\\": [1, 2]}"\n')
        assert r.returncode == 0

    def test_comments_blanks_and_sections_ignored(self, tmp_path):
        r = run_checker(
            tmp_path,
            "# comment\n\n[SECTION]\nPLAIN=value\nNUMBER=42\n",
        )
        assert r.returncode == 0


class TestInvalidEnvFiles:
    def test_corrupt_json_object_fails(self, tmp_path):
        r = run_checker(tmp_path, 'BAD="{not valid"\n')
        assert r.returncode == 1
        assert "BAD" in r.stdout

    def test_corrupt_json_array_fails(self, tmp_path):
        r = run_checker(tmp_path, "BAD='[1,'\n")
        assert r.returncode == 1

    def test_reports_every_offending_line(self, tmp_path):
        r = run_checker(tmp_path, 'BAD1="{nope"\nGOOD="x"\nBAD2="[1,"\n')
        assert r.returncode == 1
        assert "BAD1" in r.stdout and "BAD2" in r.stdout

    def test_non_utf8_file_fails_cleanly(self, tmp_path):
        r = run_checker(tmp_path, b"\xff\xfe key = \x00\x01\n")
        assert r.returncode == 1
        assert "UTF-8" in r.stdout

    def test_missing_file_is_tolerated(self, tmp_path):
        r = subprocess.run(
            [sys.executable, str(CHECK_ENV), str(tmp_path / "nope.env")],
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0


class TestScriptIntegrity:
    def test_checker_is_stdlib_only(self):
        """start.cmd runs this before pip install — no third-party imports."""
        source = CHECK_ENV.read_text(encoding="utf-8")
        assert "import requests" not in source
        assert "import yaml" not in source

    def test_real_repo_env_passes_when_present(self):
        """The developer's actual backend/.env must not trip the checker
        (regression: six placeholder-empty values aborted the boot)."""
        real_env = Path(__file__).resolve().parents[1] / ".env"
        if not real_env.exists():
            pytest.skip("no backend/.env on this machine")
        r = subprocess.run(
            [sys.executable, str(CHECK_ENV), str(real_env)],
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0, r.stdout
