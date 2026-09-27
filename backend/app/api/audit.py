import json
import os
import threading
from collections import Counter
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.audit import AuditEventType
from app.core.security import get_admin_user, TokenData

router = APIRouter(prefix="/api/audit", tags=["audit"])

# AUDIT_LOG_DIR so deployments that run the backend from a different cwd
# can point at the real log directory instead of a silently empty relative
# path (previously the API returned [] forever in that case).
LOG_DIR = Path(os.getenv("AUDIT_LOG_DIR", "logs/audit"))

# Re-parsing up to 7 log files on EVERY request was the audit screen's
# latency tail (multi-second p95 whenever audit_*.log grew large). Entries
# are immutable once written, so the parsed result is cached per file and
# invalidated by mtime — a request only pays for files changed since.
_entry_cache: dict[str, tuple[float, int, list[dict]]] = {}
_cache_lock = threading.Lock()


def _iter_file_entries(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                if isinstance(entry, dict):
                    yield entry
    except OSError:
        return


def _load_entries(files: list[Path]) -> list[dict]:
    merged: list[dict] = []
    with _cache_lock:
        for path in files:
            key = str(path)
            try:
                stat = path.stat()
            except OSError:
                continue
            cached = _entry_cache.get(key)
            # Entries are immutable once written: (mtime, size) unchanged
            # means the cached parse is still exact, however old the file is.
            if cached is not None and cached[0] == stat.st_mtime and cached[1] == stat.st_size:
                merged.extend(cached[2])
                continue
            entries = list(_iter_file_entries(path))
            _entry_cache[key] = (stat.st_mtime, stat.st_size, entries)
            if len(_entry_cache) > 32:  # bound the cache (rotation names accumulate)
                for stale in list(_entry_cache)[: len(_entry_cache) - 16]:
                    _entry_cache.pop(stale, None)
            merged.extend(entries)
    return merged


@router.get("/logs")
def get_audit_logs(
    current_user: TokenData = Depends(get_admin_user),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    username: Optional[str] = Query(None, description="Filter by username"),
    status: Optional[str] = Query(None, description="Filter by status (success/failure)"),
    date: Optional[str] = Query(None, description="Filter by date (YYYY-MM-DD)"),
    limit: int = Query(200, ge=1, le=1000, description="Max entries to return"),
):
    if not LOG_DIR.exists():
        return {"entries": [], "total": 0}

    if date:
        log_file = LOG_DIR / f"audit_{date}.log"
        files = [log_file] if log_file.exists() else []
    else:
        files = sorted(LOG_DIR.glob("audit_*.log"), reverse=True)[:7]

    # File entries are chronological per file; merge newest file first and
    # keep a global sort stable afterwards.
    entries = _load_entries(files)

    # The middleware writes numeric HTTP status codes while the
    # AuditLogger convention is success/failure — filters must match
    # across both notations, in either direction.
    def _matches(entry: dict) -> bool:
        if event_type and entry.get("event_type") != event_type:
            return False
        if username and entry.get("username") != username:
            return False
        if status and not _status_match(entry.get("status"), status):
            return False
        return True

    filtered = [e for e in entries if _matches(e)]
    filtered.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    return {"entries": filtered[:limit], "total": len(filtered)}


def _status_match(entry_status, wanted: str) -> bool:
    es = str(entry_status)
    if es == wanted:
        return True
    is_code = es.isdigit()
    if wanted.isdigit():
        code = int(wanted)
        if 200 <= code < 300:
            return es == "success" or es == "2xx"
        return es == "failure" or es in ("4xx", "5xx")
    if wanted == "success":
        return is_code and 200 <= int(es) < 300
    if wanted == "failure":
        return is_code and int(es) >= 400
    if wanted == "2xx":
        return es == "success" or (is_code and 200 <= int(es) < 300)
    if wanted == "4xx":
        return es == "failure" or (is_code and 400 <= int(es) < 500)
    if wanted == "5xx":
        return es == "failure" or (is_code and int(es) >= 500)
    return False


@router.get("/event-types")
async def get_event_types(
    current_user: TokenData = Depends(get_admin_user),
):
    return {"event_types": [e.value for e in AuditEventType]}


@router.get("/stats")
def get_audit_stats(
    current_user: TokenData = Depends(get_admin_user),
    date: Optional[str] = Query(None, description="Filter by date (YYYY-MM-DD)"),
):
    if not LOG_DIR.exists():
        return {"total": 0, "event_counts": {}, "user_counts": {}, "status_counts": {}}

    if date:
        files = [LOG_DIR / f"audit_{date}.log"]
        files = [f for f in files if f.exists()]
    else:
        files = sorted(LOG_DIR.glob("audit_*.log"), reverse=True)[:7]

    event_counts: Counter = Counter()
    user_counts: Counter = Counter()
    status_counts: Counter = Counter()

    for entry in _load_entries(files):
        event_counts[entry.get("event_type", "unknown")] += 1
        user_counts[entry.get("username", "unknown")] += 1
        status_counts[entry.get("status", "unknown")] += 1

    return {
        "total": sum(event_counts.values()),
        "event_counts": dict(event_counts.most_common()),
        "user_counts": dict(user_counts.most_common()),
        "status_counts": dict(status_counts),
    }
