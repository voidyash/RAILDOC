"""Sanity-check backend/.env JSON-valued entries (used by start.cmd).

An invalid JSON line (a connection spec, credential blob, etc.) crashes the
backend at boot with a raw parse error. This script reports the offending
line(s) here instead, so start.cmd can stop early with a readable message.

Runs with NO third-party imports (stdlib only) so it works before pip install.
Prints machine-readable progress markers so cmd.exe callers can distinguish
"checked, no problems" from "checked, found problems".

Exit code 0 = .env is fine (or absent — nothing to check), 1 = invalid entries.

Usage:
    python scripts/check_env.py [path-to-env]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV = REPO_ROOT / "backend" / ".env"


def check_env(path: Path) -> int:
    problems = 0
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        print("[start] note: no .env file to check")
        return 0
    except UnicodeDecodeError as e:
        print(f"[start] INVALID: .env is not valid UTF-8 text ({e})")
        return 1

    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("[") or "=" not in line:
            continue  # blank / comment / section header
        key, _, value = line.partition("=")
        value = value.strip().strip("'\"")
        # Only quoted-JSON-looking values are checked; note value[:1] in "[{"
        # would be True for an empty value ('' is a substring of anything).
        if not value or not value.startswith(("[", "{")):
            continue
        # .env convention: inner quotes are backslash-escaped inside the
        # double-quoted value — unescape them before parsing.
        normalized = value.replace('\\"', '"')
        try:
            json.loads(normalized)
        except json.JSONDecodeError as e:
            print(f"  INVALID JSON at line {lineno}: {key} -> {e.msg}")
            problems += 1

    return 1 if problems else 0


def main() -> int:
    env_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ENV
    print("[start] checking .env JSON entries...")
    result = check_env(env_path)
    print("[start] env-check-result: 0" if result == 0 else "[start] env-check-result: 1")
    return result


if __name__ == "__main__":
    sys.exit(main())
