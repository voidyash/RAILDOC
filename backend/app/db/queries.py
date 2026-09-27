"""Supabase REST API query layer — all reads/writes via PostgREST."""

import functools
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from urllib.parse import quote

import httpx
from dotenv import load_dotenv

load_dotenv()

SB_URL = os.getenv("SUPABASE_URL")
SB_KEY = os.getenv("SUPABASE_KEY")           # anon key for reads
SB_SVC = os.getenv("SUPABASE_SERVICE_KEY")   # service key for writes

TIMEOUT = 30

# One pooled client: the old code opened (and abandoned) a fresh TCP+TLS
# connection for every PostgREST call, which collapses latency under load.
_client = httpx.Client(timeout=TIMEOUT)

# Serialises destructive plan writes (save_blocks clears + re-inserts three
# tables). Without it, concurrent /optimize runs interleave their
# delete/insert windows and can lose a plan or 500 on duplicate PKs.
# Single-process only: a multi-worker deployment needs an external lock.
PLAN_WRITE_LOCK = threading.Lock()


def _q(value) -> str:
    """URL-encode a value interpolated into a PostgREST filter — task/plan
    ids arrive via path params and request bodies (they can contain '&',
    '=' and spaces, which would otherwise rewrite the query string)."""
    return quote(str(value), safe="")


def _plan_write(fn):
    """Run a plan-mutating function under PLAN_WRITE_LOCK. Never nested:
    no decorated function calls another decorated one."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with PLAN_WRITE_LOCK:
            return fn(*args, **kwargs)
    return wrapper


def _headers(key: str = None, prefer: str = "return=representation"):
    return {
        "apikey": key or SB_KEY,
        "Authorization": f"Bearer {key or SB_KEY}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


def _get(table: str, params: str = "", key: str = None) -> list[dict]:
    resp = _client.get(
        f"{SB_URL}/rest/v1/{table}?{params}",
        headers=_headers(key),
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def _post(table: str, data: list[dict], key: str = None) -> list[dict]:
    resp = _client.post(
        f"{SB_URL}/rest/v1/{table}",
        headers=_headers(key or SB_SVC),
        json=data,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json() if resp.status_code != 204 else []


def _upsert(table: str, data: list[dict], key: str = None) -> list[dict]:
    headers = _headers(key or SB_SVC)
    headers["Prefer"] = "return=representation,resolution=merge-duplicates"
    resp = _client.post(
        f"{SB_URL}/rest/v1/{table}",
        headers=headers,
        json=data,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json() if resp.status_code != 204 else []


def _is_fk_error(exc: Exception) -> bool:
    """True when a PostgREST failure is a foreign-key violation (SQLSTATE
    23503, surfaced by PostgREST as HTTP 409 with a JSON body)."""
    resp = getattr(exc, "response", None)
    if resp is None:
        return False
    try:
        return json.loads(resp.text).get("code") == "23503"
    except Exception:
        return "23503" in resp.text


def _delete(table: str, params: str = "", key: str = None):
    """Delete rows. PostgREST requires a WHERE filter — use 'id=not.is.null' to delete all."""
    if not params:
        params = "id=not.is.null"  # fallback: won't work for tables without 'id'
    resp = _client.delete(
        f"{SB_URL}/rest/v1/{table}?{params}",
        headers=_headers(key or SB_SVC, prefer="return=minimal"),
        timeout=TIMEOUT,
    )
    
    # Ignore 404 (no rows matched) — that's fine
    if resp.status_code not in (200, 204, 404):
        resp.raise_for_status()


def _patch(table: str, data: dict, params: str = "", key: str = None) -> list[dict]:
    resp = _client.patch(
        f"{SB_URL}/rest/v1/{table}?{params}",
        headers=_headers(key or SB_SVC),
        json=data,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json() if resp.status_code != 204 else []


# ─── Corridors ────────────────────────────────────────────────────

def get_corridors() -> list[dict]:
    return _get("corridors", "order=corridor_id")


# ─── Assets ───────────────────────────────────────────────────────

def get_assets() -> list[dict]:
    return _get("assets", "order=asset_id")


# ─── Tasks ────────────────────────────────────────────────────────

def get_tasks() -> list[dict]:
    return _get("maintenance_tasks", "order=priority_score.desc")


def get_task(task_id: str) -> Optional[dict]:
    rows = _get("maintenance_tasks", f"task_id=eq.{_q(task_id)}&limit=1")
    return rows[0] if rows else None


def update_task(task_id: str, updates: dict):
    _patch("maintenance_tasks", updates, f"task_id=eq.{_q(task_id)}")


def _stringify_dates(row: dict) -> dict:
    """Convert date/datetime/enum objects to JSON-safe values."""
    out = {}
    for k, v in row.items():
        if hasattr(v, 'isoformat'):
            out[k] = v.isoformat()
        elif hasattr(v, 'value'):  # enum
            out[k] = v.value
        elif isinstance(v, dict):
            out[k] = _stringify_dates(v)
        elif isinstance(v, list):
            out[k] = [_stringify_dates(i) if isinstance(i, dict) else (i.value if hasattr(i, 'value') else i) for i in v]
        else:
            out[k] = v
    return out


def update_all_tasks(tasks: list[dict]):
    """Batch update tasks — upsert in chunks of 50.

    PostgREST applies each batch atomically, so a single task referencing an
    asset that no longer exists (stale optimizer output after an asset was
    deleted) previously failed the WHOLE chunk — and with it the entire
    /optimize persist step. FK violations are now retried once without the
    offending rows; anything else still raises.
    """
    for i in range(0, len(tasks), 50):
        chunk = [_stringify_dates(t) for t in tasks[i : i + 50]]
        try:
            _upsert("maintenance_tasks", chunk)
        except httpx.HTTPStatusError as exc:
            if not _is_fk_error(exc):
                raise
            # PostgREST batches are transactional — the failed chunk rolled
            # back entirely, so filtering and retrying cannot double-write.
            try:
                existing = {a["asset_id"] for a in _get("assets", "select=asset_id")}
            except Exception:
                existing = None
            if existing is None:
                raise
            kept = [t for t in chunk if t.get("asset_id") in existing]
            dropped = len(chunk) - len(kept)
            if not kept:
                print(f"[db] update_all_tasks: dropped all {dropped} rows with missing asset refs")
                continue
            if dropped:
                print(f"[db] update_all_tasks: dropped {dropped} row(s) with missing asset refs")
            _upsert("maintenance_tasks", kept)


# ─── Trains ───────────────────────────────────────────────────────

def get_trains() -> list[dict]:
    return _get("trains", "order=corridor_id,scheduled_time")


# ─── Block Windows ────────────────────────────────────────────────

def get_block_windows() -> list[dict]:
    return _get("block_windows", "order=corridor_id,start_time")


# ─── Maintenance Blocks ───────────────────────────────────────────

def get_blocks() -> list[dict]:
    """Fetch all blocks with their task assignments and departments.

    Three independent reads — they used to run sequentially, which made
    every dashboard/plans read pay 3x the DB round-trip latency; the
    PostgREST client is thread-safe, so they now run concurrently.
    """
    with ThreadPoolExecutor(max_workers=3) as pool:
        blocks_future = pool.submit(
            _get, "maintenance_blocks", "order=corridor_id,start_time"
        )
        assign_future = pool.submit(
            _get, "block_task_assignments", "select=block_id,task_id"
        )
        dept_future = pool.submit(
            _get, "block_departments", "select=block_id,department"
        )
        blocks = blocks_future.result()
        if not blocks:
            return blocks
        all_assignments = assign_future.result()
        all_departments = dept_future.result()

    # Build lookup dicts
    assign_map: dict[str, list[str]] = {}
    for a in all_assignments:
        assign_map.setdefault(a["block_id"], []).append(a["task_id"])

    dept_map: dict[str, list[str]] = {}
    for d in all_departments:
        dept_map.setdefault(d["block_id"], []).append(d["department"])

    for b in blocks:
        bid = b["block_id"]
        b["assigned_tasks"] = assign_map.get(bid, [])
        b["departments"] = dept_map.get(bid, [])

    return blocks


@_plan_write
def save_blocks(blocks: list[dict]):
    """Clear and re-insert all blocks."""
    # Delete in dependency order using the table's PK column
    _delete("block_task_assignments", "task_id=not.is.null")
    _delete("block_departments", "block_id=not.is.null")
    _delete("maintenance_blocks", "block_id=not.is.null")

    if not blocks:
        return

    # Insert blocks
    _post("maintenance_blocks", [
        _stringify_dates({
            "block_id": b["block_id"],
            "corridor_id": b["corridor_id"],
            "start_time": b["start_time"],
            "end_time": b["end_time"],
            "duration_minutes": b["duration_minutes"],
            "block_type": b["block_type"],
            "utilization": b["utilization"],
            "train_impact": b["train_impact"],
            "status": b.get("status", "Proposed"),
            "explanation": b.get("explanation", ""),
        })
        for b in blocks
    ])

    # Insert task assignments
    assignments = []
    for b in blocks:
        for tid in b.get("assigned_tasks", []):
            assignments.append({"block_id": b["block_id"], "task_id": tid})
    if assignments:
        _post("block_task_assignments", assignments)

    # Insert department assignments
    dept_links = []
    for b in blocks:
        for dept in b.get("departments", []):
            dept_links.append({"block_id": b["block_id"], "department": dept})
    if dept_links:
        _post("block_departments", dept_links)


@_plan_write
def add_block(block: dict):
    """Insert a single block with task/department links (used by the
    inspection workflow commit; unlike save_blocks it does not clear
    existing blocks)."""
    _post("maintenance_blocks", [
        _stringify_dates({
            "block_id": block["block_id"],
            "corridor_id": block["corridor_id"],
            "start_time": block["start_time"],
            "end_time": block["end_time"],
            "duration_minutes": block["duration_minutes"],
            "block_type": block["block_type"],
            "utilization": block["utilization"],
            "train_impact": block["train_impact"],
            "status": block.get("status", "Approved"),
            "explanation": block.get("explanation", ""),
        })
    ])
    assignments = [
        {"block_id": block["block_id"], "task_id": tid}
        for tid in block.get("assigned_tasks", [])
    ]
    if assignments:
        _post("block_task_assignments", assignments)
    dept_links = [
        {"block_id": block["block_id"], "department": dept}
        for dept in block.get("departments", [])
    ]
    if dept_links:
        _post("block_departments", dept_links)


# ─── Priority Weights ─────────────────────────────────────────────

def get_weights() -> dict:
    rows = _get("priority_weights", "id=eq.1&limit=1")
    if rows:
        r = rows[0]
        return {
            "asset_criticality": r["asset_criticality"],
            "failure_risk": r["failure_risk"],
            "overdue_factor": r["overdue_factor"],
            "train_impact": r["train_impact"],
            "safety_criticality": r["safety_criticality"],
        }
    return {
        "asset_criticality": 0.30,
        "failure_risk": 0.25,
        "overdue_factor": 0.20,
        "train_impact": 0.15,
        "safety_criticality": 0.10,
    }


def update_weights(weights: dict):
    _patch("priority_weights", weights, "id=eq.1")


# ─── Plans ────────────────────────────────────────────────────────

def get_plans() -> list[dict]:
    return _get("plans", "order=created_at.desc")


@_plan_write
def save_plan(plan: dict):
    _upsert("plans", [{
        "plan_id": plan["plan_id"],
        "plan_type": plan["plan_type"],
        "week_number": plan["week_number"],
        "corridor_id": plan["corridor_id"],
        "status": plan.get("status", "Draft"),
        "approved_by": plan.get("approved_by"),
        "metrics": plan.get("metrics", {}),
    }])
    # Persist which blocks this plan approves (plan_blocks table). The link
    # used to be silently dropped, so approvals could never be reverted by
    # scope — reverting reset every block in the system.
    block_ids = [b for b in plan.get("block_ids", []) if isinstance(b, str)]
    if not block_ids:
        return
    existing = {b["block_id"] for b in get_blocks()}  # FK safety; get_blocks does not take the lock
    pairs = [{"plan_id": plan["plan_id"], "block_id": bid}
             for bid in dict.fromkeys(block_ids) if bid in existing]
    if pairs:
        _post("plan_blocks", pairs)


def get_plan_blocks(plan_id: str) -> list[str]:
    """Block ids linked to a plan (read before the plan row is deleted)."""
    rows = _get("plan_blocks", f"plan_id=eq.{_q(plan_id)}&select=block_id")
    return [r["block_id"] for r in rows if r.get("block_id")]


def approve_plan(plan_id: str, approved_by: str):
    _patch("plans", {"status": "Approved", "approved_by": approved_by},
           f"plan_id=eq.{plan_id}")


@_plan_write
def mark_blocks_status(status: str):
    """Update status of all maintenance_blocks."""
    _patch("maintenance_blocks", {"status": status}, "block_id=not.is.null")


@_plan_write
def mark_blocks_status_by_ids(block_ids: list[str], status: str):
    """Update status of specific blocks by their IDs — one PostgREST filter
    instead of the old per-id loop (each round-trip opened a fresh connection)."""
    if not block_ids:
        return
    ids = ",".join(_q(bid) for bid in block_ids)
    _patch("maintenance_blocks", {"status": status}, f"block_id=in.({ids})")


@_plan_write
def delete_plan(plan_id: str):
    pid = _q(plan_id)
    # Drop plan->block links first: plan_blocks references plans (setup.sql
    # cascades, schema.sql does not — be explicit either way).
    _delete("plan_blocks", f"plan_id=eq.{pid}")
    _delete("plans", f"plan_id=eq.{pid}")
