import json
import os
import time
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.core.security import get_current_user, get_planner_user, get_operations_user, get_engineer_user, get_authenticated_user, require_roles, UserRole, TokenData
from app.core.middleware import (
    AuditLogMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.core.exceptions import (
    generic_exception_handler,
    request_validation_exception_handler,
)
from app.core.pools import run_heavy, run_io
from fastapi.exceptions import RequestValidationError

from app.models.domain import (
    MaintenanceTask, MaintenanceBlock, BlockWindow, Train,
    PlanMetrics, PriorityWeights, WhatIfScenario, TaskStatus
)
from app.ai.priority_engine import (
    calculate_all_priorities, generate_explanation, get_priority_distribution
)
from app.optimizer.block_optimizer import BlockOptimizer
from app.db import queries as db
from app.api.auth import router as auth_router
from app.api.audit import router as audit_router
from app.api.inspection import router as inspection_router


app = FastAPI(
    title="RailDoc",
    description="Railway maintenance block planning and scheduling — coordinates Engineering, S&T, and Traction work into shared maintenance blocks",
    version="1.0.0"
)

# add_middleware inserts at the front, so the LAST added runs FIRST:
# security headers must wrap the rate limiter so even limiter-generated 429s
# carry them; CORS stays innermost (the app is served same-origin via the
# Vite proxy / nginx). Credentials are not used (tokens travel in the
# Authorization header), so wildcard origins without credentials are correct.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Was dead code (never registered): structured JSON audit lines for
# sensitive endpoints and every 4xx/5xx. Runs inside the rate limiter
# (429s are logged by the limiter itself) and around CORS/the app, so it
# sees every response the app actually serves.
app.add_middleware(AuditLogMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# Unhandled exceptions used to fall through to a bare text 500; this returns
# structured JSON (only the generic handler — FastAPI's default HTTPException
# and 422 shapes already carry `detail`, which the frontend reads).
app.add_exception_handler(Exception, generic_exception_handler)
# Body-validation 422s: the default handler crashes when the rejected input
# contains NaN/Infinity (it embeds the raw value in the error body, and
# Starlette's strict JSON dump refuses non-finite floats). The override
# sanitizes the payload so hostile values get a real 422, not a 500.
app.add_exception_handler(RequestValidationError, request_validation_exception_handler)

app.include_router(auth_router)
app.include_router(audit_router)
app.include_router(inspection_router)


# /api/health does a real Supabase round trip, which made it cost ~1.5 s per
# call — and it is probed by the load harness, uptime checks and every UI
# poll. Cache the verdict briefly so bursts of probes do not each pay the
# full DB latency (HEALTH_CACHE_TTL=0 disables caching).
_health_cache: dict = {"ts": 0.0, "payload": None}
_HEALTH_TTL = float(os.getenv("HEALTH_CACHE_TTL", "15"))


@app.get("/api/health")
def health_check():
    if _HEALTH_TTL > 0:
        now = time.monotonic()
        cached = _health_cache["payload"]
        if cached is not None and now - _health_cache["ts"] < _HEALTH_TTL:
            return cached
    try:
        import httpx as _hx
        resp = _hx.get(f"{db.SB_URL}/rest/v1/corridors?select=count",
                        headers=db._headers(), params={"Prefer": "count=exact"},
                        timeout=10)
        payload = {"status": "ok", "database": "connected", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        payload = {"status": "degraded", "database": "disconnected", "error": str(e)}
    if _HEALTH_TTL > 0:
        _health_cache["payload"] = payload
        _health_cache["ts"] = time.monotonic()
    return payload


@app.get("/api/data/assets")
def get_assets(current_user: TokenData = Depends(get_authenticated_user)):
    return db.get_assets()


@app.get("/api/data/tasks")
def get_tasks(current_user: TokenData = Depends(get_authenticated_user)):
    return db.get_tasks()


@app.get("/api/data/trains")
def get_trains(current_user: TokenData = Depends(get_authenticated_user)):
    return db.get_trains()


@app.get("/api/data/corridors")
def get_corridors(current_user: TokenData = Depends(get_authenticated_user)):
    return db.get_corridors()


@app.get("/api/data/block-windows")
def get_block_windows(current_user: TokenData = Depends(get_authenticated_user)):
    return db.get_block_windows()


@app.post("/api/data/regenerate")
def regenerate_data(current_user: TokenData = Depends(get_planner_user)):
    from app.db.seed import main as seed_main
    seed_main()
    return {"message": "Database re-seeded"}


class WeightsUpdate(BaseModel):
    # Bounded and finite: NaN/inf/negative/out-of-range weights poisoned
    # every recomputed priority score, and NaN crashed the optimizer
    # objective (int(round(nan))).
    asset_criticality: Optional[float] = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    failure_risk: Optional[float] = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    overdue_factor: Optional[float] = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    train_impact: Optional[float] = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    safety_criticality: Optional[float] = Field(default=None, ge=0, le=1, allow_inf_nan=False)


@app.get("/api/priority/weights")
def get_priority_weights(current_user: TokenData = Depends(get_authenticated_user)):
    return db.get_weights()


@app.put("/api/priority/weights")
def update_priority_weights(update: WeightsUpdate, current_user: TokenData = Depends(get_planner_user)):
    w = db.get_weights()
    if update.asset_criticality is not None:
        w["asset_criticality"] = update.asset_criticality
    if update.failure_risk is not None:
        w["failure_risk"] = update.failure_risk
    if update.overdue_factor is not None:
        w["overdue_factor"] = update.overdue_factor
    if update.train_impact is not None:
        w["train_impact"] = update.train_impact
    if update.safety_criticality is not None:
        w["safety_criticality"] = update.safety_criticality

    db.update_weights(w)

    weights = PriorityWeights(**w)
    tasks_raw = db.get_tasks()
    tasks = [MaintenanceTask(**t) for t in tasks_raw]
    tasks = calculate_all_priorities(tasks, weights)
    for t in tasks:
        t.explanation = generate_explanation(t)
    db.update_all_tasks([t.model_dump() for t in tasks])

    return {"weights": w, "tasks_recalculated": len(tasks)}


@app.get("/api/priority/calculate")
def calculate_priorities(current_user: TokenData = Depends(get_planner_user)):
    weights_dict = db.get_weights()
    weights = PriorityWeights(**weights_dict)
    tasks_raw = db.get_tasks()
    tasks = [MaintenanceTask(**t) for t in tasks_raw]
    tasks = calculate_all_priorities(tasks, weights)

    for t in tasks:
        t.explanation = generate_explanation(t)

    db.update_all_tasks([t.model_dump() for t in tasks])

    return {
        "distribution": get_priority_distribution(tasks),
        "top_10": [_task_summary(t) for t in tasks[:10]]
    }


def _time_to_minutes(time_str: str) -> int:
    parts = time_str.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _task_summary(task: MaintenanceTask) -> dict:
    return {
        "task_id": task.task_id,
        "department": task.department,
        "asset_id": task.asset_id,
        "task_type": task.task_type,
        "priority_score": task.priority_score,
        "criticality": task.criticality,
        "corridor_id": task.corridor_id,
        "due_date": str(task.due_date),
        "status": task.status,
        "explanation": task.explanation
    }


def _optimize_core(scenario: Optional[WhatIfScenario]) -> dict:
    """CPU-bound solve + blocking persistence, executed on the heavy pool."""
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(
        max_workers=4
    ) as pool:

        weights_future = pool.submit(
            db.get_weights
        )

        tasks_future = pool.submit(
            db.get_tasks
        )

        windows_future = pool.submit(
            db.get_block_windows
        )

        trains_future = pool.submit(
            db.get_trains
        )

        weights_dict = (
            weights_future.result()
        )

        tasks_raw = (
            tasks_future.result()
        )

        windows_raw = (
            windows_future.result()
        )

        trains_raw = (
            trains_future.result()
        )

    weights = PriorityWeights(
        **weights_dict
    )

    tasks = [
        MaintenanceTask(**task)
        for task in tasks_raw
    ]

    windows = [
        BlockWindow(**window)
        for window in windows_raw
    ]

    trains = [
        Train(**train)
        for train in trains_raw
    ]

    # Recalculate priorities if ANY pending task
    # has not been scored yet.
    needs_recalc = (
        any(
            task.priority_score <= 0
            for task in tasks
            if task.status == TaskStatus.PENDING
        )
        or
        bool(
            scenario
            and scenario.asset_criticality_changes
        )
    )

    if needs_recalc:

        if scenario:

            for (
                asset_id,
                new_criticality,
            ) in (
                scenario
                .asset_criticality_changes
                .items()
            ):

                for task in tasks:

                    if (
                        task.asset_id
                        == asset_id
                    ):
                        task.criticality = (
                            new_criticality
                        )

        tasks = calculate_all_priorities(
            tasks,
            weights,
        )

        for task in tasks:
            task.explanation = (
                generate_explanation(task)
            )

    # Resource availability changes are
    # represented as percentages.
    resource_factor = 1.0

    if (
        scenario
        and
        scenario.resource_availability_change
        is not None
    ):
        resource_factor = max(
            0.1,
            1.0
            + (
                scenario.resource_availability_change
                / 100.0
            ),
        )

    optimizer = BlockOptimizer()

    blocks, metrics = (
        optimizer.optimize(
            tasks,
            windows,
            trains,
            scenario,
            resource_factor=resource_factor,
        )
    )

    # Map scheduled tasks -> generated block.
    task_block_map = {}

    for block in blocks:

        for task_id in block.assigned_tasks:

            task_block_map[
                task_id
            ] = block.block_id

    # Update only tasks actually scheduled.
    for task in tasks:

        if (
            task.task_id
            in task_block_map
        ):

            task.assigned_block_id = (
                task_block_map[
                    task.task_id
                ]
            )

            task.status = (
                TaskStatus.SCHEDULED
            )

            task.explanation = (
                generate_explanation(task)
            )

    # Persist both outputs.
    try:

        with ThreadPoolExecutor(
            max_workers=2
        ) as pool:

            save_future = pool.submit(
                db.save_blocks,
                [
                    block.model_dump()
                    for block in blocks
                ],
            )

            update_future = pool.submit(
                db.update_all_tasks,
                [
                    task.model_dump()
                    for task in tasks
                ],
            )

            # IMPORTANT:
            # result() is called inside the try.
            # Database failures therefore reach the API
            # instead of being silently ignored.
            save_future.result()
            update_future.result()

    except Exception as exc:

        print(
            "[OPTIMIZER] "
            f"persistence failed: {exc}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Optimizer result could not "
                f"be saved: {exc}"
            ),
        ) from exc

    return {
        "blocks": [
            block.model_dump()
            for block in blocks
        ],
        "metrics": metrics.model_dump(),
        "assigned_tasks": len(
            task_block_map
        ),
        "total_tasks": len(tasks),
    }


@app.post("/api/optimize")
async def run_optimizer(
    scenario: Optional[WhatIfScenario] = None,
    current_user: TokenData = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.PLANNER,
            UserRole.OPERATIONS,
            UserRole.ENGINEER,
        )
    ),
):
    # The solve holds the GIL and each CP-SAT run spawns NUM_WORKERS
    # threads: unbounded concurrency stacked 10+ solves into 40 competing
    # threads (p95 ~16 s). The bounded heavy pool queues excess runs
    # instead — the event loop stays responsive throughout.
    return await run_heavy(_optimize_core, scenario)


@app.get("/api/plans")
def get_plans(current_user: TokenData = Depends(get_authenticated_user)):
    return db.get_plans()


@app.get("/api/plans/current")
def get_current_plan(current_user: TokenData = Depends(get_authenticated_user)):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:
        blocks = pool.submit(db.get_blocks).result()
        tasks = pool.submit(db.get_tasks).result()
    return {
        "blocks": blocks,
        "metrics": None,
        "total_tasks": len(tasks),
        "assigned_tasks": sum(len(b.get("assigned_tasks", [])) for b in blocks)
    }


@app.post("/api/plans/approve")
async def approve_plan(request: Request, current_user: TokenData = Depends(require_roles(UserRole.ADMIN, UserRole.PLANNER, UserRole.OPERATIONS, UserRole.ENGINEER))):
    # async def runs on the event loop: the synchronous PostgREST calls
    # below must go through run_io or every plan approval stalls ALL
    # concurrent requests for the duration of the DB round trips.
    import json as _json
    body = await request.body()
    try:
        data = _json.loads(body) if body else {}
    except _json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Request body is not valid JSON") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object")
    selected_ids = data.get("block_ids", [])
    if not isinstance(selected_ids, list):
        raise HTTPException(status_code=400, detail="block_ids must be a list")

    # Second-resolution timestamps collided when two approvals landed in the
    # same second (the second plan silently overwrote the first) — add a
    # uuid suffix to keep plan_ids unique.
    plan_id = f"PLAN-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    all_blocks = await run_io(db.get_blocks)
    # Use selected IDs if provided, otherwise use all
    block_ids = selected_ids if selected_ids else [b["block_id"] for b in all_blocks]

    plan = {
        "plan_id": plan_id,
        "plan_type": "Weekly",
        "week_number": datetime.now().isocalendar()[1],
        "corridor_id": "C-07",
        "status": "Approved",
        "approved_by": current_user.username,
        "metrics": {},
        "block_ids": block_ids
    }
    await run_io(db.save_plan, plan)
    await run_io(db.mark_blocks_status_by_ids, block_ids, "Approved")
    return {"message": "Plan approved", "plan_id": plan_id, "approved_blocks": block_ids}


@app.post("/api/plans/revert")
async def revert_plan(request: Request, current_user: TokenData = Depends(require_roles(UserRole.ADMIN, UserRole.PLANNER, UserRole.OPERATIONS, UserRole.ENGINEER))):
    import json as _json
    body = await request.body()
    try:
        data = _json.loads(body) if body else {}
    except _json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Request body is not valid JSON") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object")
    plan_id = data.get("plan_id")
    if not plan_id or not isinstance(plan_id, str):
        raise HTTPException(status_code=400, detail="plan_id required")

    # A non-list block_ids used to fall through silently to the DB calls,
    # reverting everything (or nothing) instead of telling the caller the
    # body was malformed. approve_plan already 400s in this case.
    raw_ids = data.get("block_ids")
    if raw_ids is not None and not isinstance(raw_ids, list):
        raise HTTPException(status_code=400, detail="block_ids must be a list")

    # Revert only the blocks that belong to this plan. The old behaviour
    # (reset EVERY block) meant undoing plan A also wiped unrelated
    # approvals from plan B. All PostgREST calls run via run_io (async def
    # endpoint — blocking the loop here stalls every concurrent request).
    requested = ([b for b in raw_ids if isinstance(b, str)]
                 if raw_ids else [])
    if requested:
        reverted = requested
    else:
        reverted = await run_io(db.get_plan_blocks, plan_id)  # read links before delete
    if reverted:
        await run_io(db.mark_blocks_status_by_ids, reverted, "Proposed")
    else:
        # Legacy plan with no recorded links: keep the old reset-all fallback.
        reverted = [b["block_id"] for b in await run_io(db.get_blocks)]
        await run_io(db.mark_blocks_status, "Proposed")
    await run_io(db.delete_plan, plan_id)
    return {"message": "Plan reverted", "plan_id": plan_id, "reverted_blocks": reverted}


@app.get("/api/explain/task/{task_id}")
def explain_task(task_id: str, current_user: TokenData = Depends(get_authenticated_user)):
    task_data = db.get_task(task_id)
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")

    task = MaintenanceTask(**task_data)

    assigned_block = None
    blocks = db.get_blocks()
    for block in blocks:
        if task_id in block.get("assigned_tasks", []):
            assigned_block = block
            break

    return {
        "task_id": task_id,
        "priority_score": task.priority_score,
        "criticality": task.criticality,
        "failure_risk": task.failure_risk,
        "days_overdue": task.days_overdue,
        "train_impact": task.train_impact,
        "safety_criticality": task.safety_criticality,
        "corridor_id": task.corridor_id,
        "assigned_block": assigned_block["block_id"] if assigned_block else None,
        "block_start": assigned_block["start_time"] if assigned_block else None,
        "block_end": assigned_block["end_time"] if assigned_block else None,
        "compatible_tasks": len(assigned_block.get("assigned_tasks", [])) - 1 if assigned_block else 0,
        "reason": task.explanation or generate_explanation(task),
        "if_moved": "Moving this task would require a separate block, increasing downtime."
    }


@app.get("/api/explain/block/{block_id}")
def explain_block(block_id: str, current_user: TokenData = Depends(get_authenticated_user)):
    blocks = db.get_blocks()
    block_data = next((b for b in blocks if b["block_id"] == block_id), None)
    if not block_data:
        raise HTTPException(status_code=404, detail="Block not found")

    tasks_in_block = []
    for tid in block_data.get("assigned_tasks", []):
        t = db.get_task(tid)
        if t:
            tasks_in_block.append(t)

    dept_list = block_data.get("departments", [])
    return {
        "block_id": block_id,
        "corridor": block_data["corridor_id"],
        "time": f"{block_data['start_time']} - {block_data['end_time']}",
        "departments": dept_list,
        "tasks": tasks_in_block,
        "utilization": block_data["utilization"],
        "explanation": block_data.get("explanation", ""),
        "coordination_benefit": (
            f"{len(dept_list)} departments coordinated in one block. "
            f"Without coordination, {len(tasks_in_block)} separate blocks "
            f"would be needed, causing {len(tasks_in_block) * 60} minutes of total downtime "
            f"vs {block_data['duration_minutes']} minutes."
        )
    }


def _simulate_core(scenario: WhatIfScenario) -> dict:
    """CPU-bound scenario solve, executed on the heavy pool."""
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=4) as pool:
        weights_dict = pool.submit(db.get_weights).result()
        tasks_raw = pool.submit(db.get_tasks).result()
        windows_raw = pool.submit(db.get_block_windows).result()
        trains_raw = pool.submit(db.get_trains).result()

    weights = PriorityWeights(**weights_dict)
    tasks = [MaintenanceTask(**t) for t in tasks_raw]
    windows = [BlockWindow(**w) for w in windows_raw]
    trains = [Train(**t) for t in trains_raw]

    # Reset task statuses for simulation (don't touch DB)
    for t in tasks:
        t.status = TaskStatus.PENDING
        t.assigned_block_id = None

    # Apply scenario: override block window durations
    if scenario.block_duration_override:
        for w in windows:
            start_min = _time_to_minutes(w.start_time)
            # Clamp at 23:59: the data model cannot express an end past
            # midnight, and "26:00" would leak into block times and the
            # train-conflict math below the optimizer.
            new_end_min = min(start_min + scenario.block_duration_override, 1439)
            w.end_time = f"{new_end_min // 60:02d}:{new_end_min % 60:02d}"

    # Apply scenario: adjust trains (traffic forecast change)
    if scenario.traffic_forecast_change:
        change = scenario.traffic_forecast_change
        if change > 0:
            import random
            # Hard cap: a hostile or buggy scenario value must not spawn an
            # unbounded number of trains (memory + optimizer CPU DoS).
            extra_count = min(int(len(trains) * change), 500)
            for _ in range(extra_count):
                t = random.choice(trains)
                trains.append(Train(
                    train_id=f"SIM-{t.train_id}-{_}",
                    train_type=t.train_type,
                    route=t.route,
                    corridor_id=t.corridor_id,
                    scheduled_time=t.scheduled_time,
                    priority=t.priority,
                    direction=t.direction,
                ))
        elif change < 0:
            remove_count = int(len(trains) * abs(change))
            trains = trains[:max(0, len(trains) - remove_count)]

    # Apply scenario: adjust task packing limit (resource availability)
    resource_factor = 1.0
    if scenario.resource_availability_change is not None:
        resource_factor = max(
            0.1, 1.0 + (scenario.resource_availability_change / 100.0)
        )

    # Always recalculate priorities for simulation
    if scenario.asset_criticality_changes:
        for asset_id, new_crit in scenario.asset_criticality_changes.items():
            for t in tasks:
                if t.asset_id == asset_id:
                    t.criticality = new_crit
    tasks = calculate_all_priorities(tasks, weights)
    for t in tasks:
        t.explanation = generate_explanation(t)

    optimizer = BlockOptimizer()
    blocks, metrics = optimizer.optimize(tasks, windows, trains, scenario, resource_factor=resource_factor)

    return {
        "blocks": [b.model_dump() for b in blocks],
        "metrics": metrics.model_dump(),
        "assigned_tasks": sum(len(b.assigned_tasks) for b in blocks),
        "total_tasks": len(tasks)
    }


@app.post("/api/simulate")
async def run_simulation(scenario: WhatIfScenario, current_user: TokenData = Depends(require_roles(UserRole.ADMIN, UserRole.PLANNER, UserRole.OPERATIONS, UserRole.ENGINEER))):
    # Same reasoning as /api/optimize: bounded heavy pool instead of
    # unbounded concurrent CP-SAT runs fighting for the GIL.
    return await run_heavy(_simulate_core, scenario)


@app.get("/api/comparison/before-after")
def get_before_after(current_user: TokenData = Depends(get_authenticated_user)):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks = pool.submit(db.get_tasks).result()
        blocks = pool.submit(db.get_blocks).result()

    total_tasks = len(tasks)
    assigned = sum(1 for t in tasks if t.get("assigned_block_id"))

    before_metrics = {
        "total_blocks": total_tasks,
        "total_downtime_minutes": total_tasks * 60,
        "train_conflicts": total_tasks // 2,
        # Clamped at 0: with 300 pending tasks the naive formula went
        # negative and the dashboard displayed e.g. "-78.6%" availability.
        "asset_availability": round(max(0.0, 100 - (total_tasks * 60 / (7 * 24 * 60)) * 100), 1),
        "multi_dept_blocks": 0,
        "block_utilization": 35.0,
        "separate_blocks_avoided": 0
    }

    after_metrics = _compute_after_metrics(blocks, tasks)

    return {
        "before": before_metrics,
        "after": after_metrics,
        "improvements": {
            "blocks_reduction": before_metrics["total_blocks"] - after_metrics["planned_blocks"],
            "downtime_reduction": before_metrics["total_downtime_minutes"] - after_metrics["total_downtime_minutes"],
            "conflicts_reduction": before_metrics["train_conflicts"] - after_metrics["train_conflicts"],
            "multi_dept_blocks": after_metrics["multi_dept_blocks"]
        }
    }


def _compute_after_metrics(blocks: list[dict], tasks: list[dict]) -> dict:
    total_tasks = len(tasks)
    assigned = sum(1 for t in tasks if t.get("assigned_block_id"))
    multi_dept = sum(1 for b in blocks if len(b.get("departments", [])) > 1)
    avg_util = sum(b["utilization"] for b in blocks) / len(blocks) if blocks else 0
    total_block_minutes = sum(b["duration_minutes"] for b in blocks)
    total_week_minutes = 7 * 24 * 60
    asset_availability = round(((total_week_minutes - total_block_minutes) / total_week_minutes) * 100, 1)

    critical_tasks = [t for t in tasks if t["priority_score"] >= 70]
    critical_assigned = sum(1 for t in critical_tasks if t.get("assigned_block_id"))

    return {
        "asset_availability": asset_availability,
        "maintenance_backlog": total_tasks - assigned,
        "planned_blocks": len(blocks),
        "train_conflicts": 0,
        "train_disruption_minutes": 0,
        "block_utilization": round(avg_util, 1),
        "multi_dept_blocks": multi_dept,
        "critical_tasks_completed": critical_assigned,
        "total_tasks": total_tasks,
        "separate_blocks_avoided": max(0, total_tasks - len(blocks) - assigned),
        "total_downtime_minutes": total_block_minutes
    }


@app.get("/api/dashboard")
def get_dashboard(current_user: TokenData = Depends(get_authenticated_user)):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=3) as pool:
        tasks_f = pool.submit(db.get_tasks)
        blocks_f = pool.submit(db.get_blocks)
        assets_f = pool.submit(db.get_assets)
        tasks = tasks_f.result()
        blocks = blocks_f.result()
        assets = assets_f.result()

    total_assets = len(assets)
    degraded_assets = sum(1 for a in assets if a.get("current_status") == "Degraded")
    maintenance_assets = sum(1 for a in assets if a.get("current_status") == "Under Maintenance")

    priority_dist = get_priority_distribution(
        [MaintenanceTask(**t) for t in tasks]
    )

    recommendations = []
    if blocks:
        multi_dept = [b for b in blocks if len(b.get("departments", [])) > 1]
        if multi_dept:
            recommendations.append(
                f"✓ {len(multi_dept)} multi-department blocks created, "
                f"reducing {len(multi_dept) * 2} separate blocks"
            )

    pending_critical = sum(
        1 for t in tasks
        if t["priority_score"] >= 70 and t["status"] == "Pending"
    )
    if pending_critical > 0:
        recommendations.append(f"⚠ {pending_critical} critical tasks still pending")

    after = _compute_after_metrics(blocks, tasks)

    return {
        "asset_availability": after["asset_availability"],
        "total_assets": total_assets,
        "degraded_assets": degraded_assets,
        "maintenance_assets": maintenance_assets,
        "maintenance_backlog": after["maintenance_backlog"],
        "planned_blocks": after["planned_blocks"],
        "block_utilization": after["block_utilization"],
        "train_conflicts": after["train_conflicts"],
        "train_disruption_minutes": after["train_disruption_minutes"],
        "priority_distribution": priority_dist,
        "recommendations": recommendations,
        "total_tasks": len(tasks),
        "scheduled_tasks": sum(1 for t in tasks if t["status"] == "Scheduled"),
        "multi_dept_blocks": after["multi_dept_blocks"]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
