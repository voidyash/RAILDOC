"""Load / stress harness for a RUNNING RailDoc backend.

Start the backend first:

    cd backend && python -m uvicorn app.main:app --port 8000

Then run:

    python scripts/stress_load.py --duration 60 --clients 20

What it does:

  * logs in once and keeps a valid admin token
  * probes /api/health — if the database is unreachable it automatically
    falls back to a DB-free mix (auth, uploads, inference, audit) unless
    --db on/off overrides it
  * runs N concurrent virtual clients until the deadline; each client has
    its own X-Forwarded-For identity (honoured because the peer is
    loopback) so rate limits behave like they would for real users
  * mixes reads, simulations, image analysis, sample predictions, planner
    churn (approve/revert) and occasional heavy optimize/replan runs
  * prints a per-operation report (count, 2xx/4xx/429/5xx/exceptions,
    p50/p95/max latency) and sample error bodies

Exit code 0 when the 5xx rate is within --max-5xx-pct, 1 otherwise.
429 responses are counted separately: hitting a rate limit is correct
behaviour, not an error.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET = REPO_ROOT / "RAILDOC_02.yolo26"

DB_MIX = [
    ("health", 4), ("me", 4), ("dashboard", 10), ("tasks", 8),
    ("plans_current", 6), ("before_after", 4), ("weights", 3),
    ("audit_logs", 2), ("explain_task", 4),
    ("simulate", 8), ("analyze", 6), ("samples", 3),
    ("approve_rev", 4), ("optimize", 2), ("replan", 2),
]
NO_DB_MIX = [
    ("health", 6), ("me", 3), ("audit_logs", 3),
    ("analyze", 8), ("samples", 6), ("refresh", 2),
]

SIM_PRESETS = [
    {"scenario_name": "baseline", "block_duration_override": 60,
     "traffic_forecast_change": 0.0, "resource_availability_change": 0},
    {"scenario_name": "heavy freight", "block_duration_override": 60,
     "traffic_forecast_change": 0.2, "resource_availability_change": 0},
    {"scenario_name": "resource shortage", "block_duration_override": 60,
     "traffic_forecast_change": 0.0, "resource_availability_change": -30},
    {"scenario_name": "combined", "block_duration_override": 45,
     "traffic_forecast_change": 0.3, "resource_availability_change": -20},
]


def weighted_choice(rng: random.Random, mix):
    names, weights = zip(*mix)
    return rng.choices(names, weights=weights, k=1)[0]


def pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * q))]


class Stats:
    def __init__(self) -> None:
        self.ops: dict[str, dict] = defaultdict(
            lambda: {"n": 0, "ok": 0, "c4": 0, "c429": 0, "c5": 0,
                     "exc": 0, "lat": [], "errors": []}
        )
        self.started = 0.0
        self.finished = 0.0
        self.requests = 0

    def record(self, op: str, status: int | None, ms: float, body: str = "") -> None:
        s = self.ops[op]
        s["n"] += 1
        self.requests += 1
        if status is None:
            s["exc"] += 1
            if len(s["errors"]) < 3:
                s["errors"].append(f"{op}: transport error: {body[:300]}")
            return
        s["lat"].append(ms)
        if 200 <= status < 300:
            s["ok"] += 1
        elif status == 429:
            s["c429"] += 1
        elif status >= 500:
            s["c5"] += 1
            if len(s["errors"]) < 3:
                s["errors"].append(f"{op}: HTTP {status}: {body[:300]}")
        else:
            s["c4"] += 1
            if status >= 500 or (status not in (400, 401, 403, 404, 409, 413, 422)
                                 and len(s["errors"]) < 3):
                s["errors"].append(f"{op}: HTTP {status}: {body[:300]}")


class Ctx:
    def __init__(self, args, token: str, refresh: str, image: bytes | None,
                 db_on: bool, sample_src: str) -> None:
        self.args = args
        self.token = token
        self.refresh = refresh
        self.image = image
        self.sample_src = sample_src
        self.mix = DB_MIX if db_on else NO_DB_MIX
        self.db_on = db_on
        self.stats = Stats()
        self.stop = asyncio.Event()


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def op_health(c: Ctx, client: httpx.AsyncClient) -> tuple[int, bytes]:
    r = await client.get("/api/health", timeout=10)
    return r.status_code, r.content


async def _authed(c: Ctx, client: httpx.AsyncClient, method: str, url: str,
                  timeout: float = 30, **kw) -> tuple[int, bytes]:
    kw.setdefault("headers", {}).update(auth(c.token))
    r = await client.request(method, url, timeout=timeout, **kw)
    return r.status_code, r.content


async def op_me(c, client):       return await _authed(c, client, "GET", "/api/auth/me", 10)
async def op_dashboard(c, client): return await _authed(c, client, "GET", "/api/dashboard")
async def op_tasks(c, client):     return await _authed(c, client, "GET", "/api/data/tasks")
async def op_plans(c, client):     return await _authed(c, client, "GET", "/api/plans/current")
async def op_before(c, client):    return await _authed(c, client, "GET", "/api/comparison/before-after")
async def op_weights(c, client):   return await _authed(c, client, "GET", "/api/priority/weights", 10)
async def op_audit(c, client):     return await _authed(c, client, "GET", "/api/audit/logs", 15)


async def op_refresh(c, client):
    r = await client.post("/api/auth/refresh",
                          json={"refresh_token": c.refresh}, timeout=10)
    return r.status_code, r.content


async def op_explain(c, client):
    r = await _authed(c, client, "GET", "/api/data/tasks", 15)
    if r[0] != 200:
        return r
    import json as _json
    try:
        tasks = _json.loads(r[1])
        task_id = tasks[0]["task_id"]
    except Exception:
        return 200, b"{}"
    return await _authed(c, client, "GET", f"/api/explain/task/{task_id}", 15)


async def op_simulate(c, client):
    preset = random.choice(SIM_PRESETS)
    return await _authed(c, client, "POST", "/api/simulate",
                         timeout=60, json=preset)


async def op_analyze(c, client):
    if c.image is None:
        return 200, b"{}"  # no dataset bundled
    files = {"file": ("stress.jpg", c.image, "image/jpeg")}
    data = {"asset_type": "track", "draw": "false"}
    return await _authed(c, client, "POST", "/api/inspection/analyze",
                         timeout=120, files=files, data=data)


async def op_samples(c, client):
    return await _authed(c, client, "GET", "/api/inspection/samples", 120)


async def op_approve_rev(c, client):
    """Approve up to 2 unapproved blocks, then immediately revert them —
    the planner churn path (plan upsert + plan_blocks + status patches)."""
    r = await _authed(c, client, "GET", "/api/plans/current", 20)
    if r[0] != 200:
        return r
    import json as _json
    try:
        blocks = _json.loads(r[1])["blocks"]
    except Exception:
        return 200, b"{}"
    ids = [b["block_id"] for b in blocks if b.get("status") != "Approved"][:2]
    if not ids:
        return 200, b"{}"
    status, body = await _authed(c, client, "POST", "/api/plans/approve",
                                 timeout=30, json={"block_ids": ids})
    if status >= 400:
        return status, body
    status, body = await _authed(c, client, "POST", "/api/plans/revert",
                                 timeout=30,
                                 json={"plan_id": "unknown", "block_ids": ids})
    # plan_id 'unknown' with explicit block_ids reverts the blocks scoped by
    # id; the missing plan row just makes delete_plan a no-op.
    return status, body


async def op_optimize(c, client):
    return await _authed(c, client, "POST", "/api/optimize",
                         timeout=120, json=None)


async def op_replan(c, client):
    return await _authed(c, client, "POST", "/api/inspection/replan",
                         timeout=120, json={"reason": "stress_load"})


OPS = {
    "health": op_health, "me": op_me, "dashboard": op_dashboard,
    "tasks": op_tasks, "plans_current": op_plans, "before_after": op_before,
    "weights": op_weights, "audit_logs": op_audit, "refresh": op_refresh,
    "explain_task": op_explain, "simulate": op_simulate, "analyze": op_analyze,
    "samples": op_samples, "approve_rev": op_approve_rev,
    "optimize": op_optimize, "replan": op_replan,
}


async def worker(idx: int, c: Ctx) -> None:
    rng = random.Random(idx)
    # Distinct virtual identity per client (loopback peer ⇒ XFF is honoured).
    xff = {"X-Forwarded-For": f"10.0.{idx // 250}.{idx % 250 + 1}"}
    timeout = httpx.Timeout(30.0, read=120.0)
    async with httpx.AsyncClient(base_url=c.args.base_url,
                                 headers=xff, timeout=timeout) as client:
        while not c.stop.is_set():
            op = weighted_choice(rng, c.mix)
            started = time.perf_counter()
            try:
                status, body = await OPS[op](c, client)
                ms = (time.perf_counter() - started) * 1000
                c.stats.record(op, status, ms, body.decode("utf-8", "replace"))
            except Exception as exc:  # noqa: BLE001
                ms = (time.perf_counter() - started) * 1000
                c.stats.record(op, None, ms, repr(exc))
            if c.args.think > 0:
                await asyncio.sleep(rng.uniform(0, c.args.think))


async def run(args) -> int:
    async with httpx.AsyncClient(base_url=args.base_url, timeout=30) as client:
        # Preflight: login.
        try:
            r = await client.post("/api/auth/login",
                                  json={"username": args.username,
                                        "password": args.password})
        except Exception as exc:  # noqa: BLE001
            print(f"FATAL: cannot reach {args.base_url}: {exc!r}")
            return 2
        if r.status_code != 200:
            print(f"FATAL: login failed ({r.status_code}): {r.text[:300]}")
            return 2
        tokens = r.json()
        token, refresh = tokens["access_token"], tokens["refresh_token"]

        # Preflight: database health → pick the traffic mix.
        h = await client.get("/api/health")
        db_ok = h.status_code == 200 and h.json().get("status") == "ok"
        if args.db == "on":
            db_on = True
        elif args.db == "off":
            db_on = False
        else:
            db_on = db_ok
        if args.db == "auto" and not db_ok:
            print("NOTE: database unreachable — falling back to the DB-free "
                  "mix (auth, uploads, inference, audit).")
        elif args.db == "on" and not db_ok:
            print("WARNING: --db on but /api/health reports degraded; "
                  "expect 5xx from data endpoints.")

        # Sample image for the analyze op.
        image = None
        sample_src = ""
        pattern = sorted((DATASET / "test" / "images").glob("*.jpg")) \
            if (DATASET / "test" / "images").is_dir() else []
        if pattern:
            image = pattern[0].read_bytes()
            sample_src = pattern[0].name
        else:
            print("NOTE: dataset not found — the analyze op will be skipped.")

    ctx = Ctx(args, token, refresh, image, db_on, sample_src)
    if image is None:
        ctx.mix = [(n, w) for n, w in ctx.mix if n != "analyze"]
    mix = ", ".join(f"{n}:{w}" for n, w in ctx.mix)
    print(f"Target        : {args.base_url}")
    print(f"Mode          : {'db-on' if db_on else 'db-off'} mix ({mix})")
    print(f"Clients       : {args.clients}   duration: {args.duration}s   "
          f"think: {args.think}s")
    print(f"Sample image  : {sample_src or '(none)'}")
    print("-" * 72)

    ctx.stats.started = time.time()
    tasks = [asyncio.create_task(worker(i, ctx)) for i in range(args.clients)]
    await asyncio.sleep(args.duration)
    ctx.stop.set()
    await asyncio.gather(*tasks, return_exceptions=True)
    ctx.stats.finished = time.time()

    # ── report ──────────────────────────────────────────────────
    stats = ctx.stats
    elapsed = max(stats.finished - stats.started, 1e-6)
    header = (f"{'op':<15}{'req':>6}{'2xx':>6}{'4xx':>6}{'429':>6}{'5xx':>6}"
              f"{'exc':>5}{'p50ms':>9}{'p95ms':>9}{'maxms':>9}")
    print("\n=== RailDoc stress report ===")
    print(f"duration {elapsed:.1f}s   requests {stats.requests}   "
          f"rps {stats.requests / elapsed:.1f}")
    print(header)
    print("-" * len(header))

    tot = {"n": 0, "ok": 0, "c4": 0, "c429": 0, "c5": 0, "exc": 0}
    all_lat: list[float] = []
    for op in sorted(stats.ops):
        s = stats.ops[op]
        for k in tot:
            tot[k] += s[k]
        all_lat += s["lat"]
        print(f"{op:<15}{s['n']:>6}{s['ok']:>6}{s['c4']:>6}{s['c429']:>6}"
              f"{s['c5']:>6}{s['exc']:>5}{pct(s['lat'], 0.50):>9.0f}"
              f"{pct(s['lat'], 0.95):>9.0f}"
              f"{(max(s['lat']) if s['lat'] else 0):>9.0f}")
    print("-" * len(header))
    print(f"{'TOTAL':<15}{tot['n']:>6}{tot['ok']:>6}{tot['c4']:>6}"
          f"{tot['c429']:>6}{tot['c5']:>6}{tot['exc']:>5}"
          f"{pct(all_lat, 0.50):>9.0f}{pct(all_lat, 0.95):>9.0f}"
          f"{(max(all_lat) if all_lat else 0):>9.0f}")

    failures = [(op, e) for op in sorted(stats.ops)
                for e in stats.ops[op]["errors"]]
    if failures:
        print("\nSample errors:")
        for op, err in failures[:8]:
            print(f"  {err}")

    denom = max(tot["n"] - tot["c429"], 1)
    five_xx_rate = 100.0 * (tot["c5"] + tot["exc"]) / denom
    print(f"\n5xx+transport rate: {five_xx_rate:.2f}% of non-429 requests "
          f"(threshold {args.max_5xx_pct}%)")
    if five_xx_rate > args.max_5xx_pct:
        print("RESULT: FAIL")
        return 1
    print("RESULT: PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--duration", type=float, default=60.0,
                        help="seconds to run (default 60)")
    parser.add_argument("--clients", type=int, default=20,
                        help="concurrent virtual clients (default 20)")
    parser.add_argument("--think", type=float, default=0.05,
                        help="max think-time seconds between requests")
    parser.add_argument("--db", choices=["auto", "on", "off"], default="auto")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="admin123")
    parser.add_argument("--max-5xx-pct", type=float, default=1.0,
                        help="fail when 5xx+errors exceed this %% of traffic")
    args = parser.parse_args()
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\ninterrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())
