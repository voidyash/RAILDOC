"""Inspection workflow API: upload → CV inference → detection ticket →
Admin Agent orchestration → candidate plans → maintenance task creation.

Endpoints:
  POST /api/inspection/analyze      image + asset_type → detections
  POST /api/inspection/ticket       create maintenance ticket from a detection
  POST /api/inspection/workflow     run the full multi-agent orchestration
  GET  /api/inspection/models       CV model availability/status
"""

from __future__ import annotations

import base64
import threading
import time
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import httpx
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from app.core.audit import AuditEventType
from app.api.auth import get_client_ip
from app.core.security import (
    TokenData,
    get_authenticated_user,
    require_roles,
    UserRole,
)
from app.cv import inference as cv
from app.core.pools import run_heavy, run_io
from app.db import queries as db

router = APIRouter(prefix="/api/inspection", tags=["inspection"])

ROOT = Path(__file__).resolve().parents[3]

severity_criticality = {"critical": 95, "high": 80, "medium": 60, "low": 40}

# In-memory workflow store (audit rows are persisted separately). Keeps the
# MVP dependency-free; swap for the DB in a production build. Bounded so a
# long-running process cannot grow without limit under sustained load.
_WORKFLOWS: dict[str, dict] = {}
_MAX_WORKFLOWS = 100
# Serialises commit decisions so two concurrent commits of the same workflow
# cannot both pass the "already committed" check and double-insert the block.
_COMMIT_LOCK = threading.Lock()


def _store_workflow(payload: dict) -> None:
    _WORKFLOWS[payload["workflow_id"]] = payload
    while len(_WORKFLOWS) > _MAX_WORKFLOWS:
        _WORKFLOWS.pop(next(iter(_WORKFLOWS)))


MAX_UPLOAD_BYTES = 15 * 1024 * 1024   # reject oversized bodies before decode
MAX_IMAGE_PIXELS = 40_000_000         # ~40 MP decode cap


async def _read_upload_capped(file: UploadFile, limit: int = MAX_UPLOAD_BYTES) -> bytes:
    """Read an upload in chunks so a huge body is rejected instead of being
    buffered whole in memory (OOM risk under hostile/concurrent uploads)."""
    """Read an upload in chunks so a huge body is rejected instead of being
    buffered whole in memory (OOM risk under hostile/concurrent uploads)."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(
                status_code=413,
                detail=f"Image exceeds the {limit // (1024 * 1024)} MB upload limit",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _decode_image(data: bytes) -> np.ndarray:
    import cv2

    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid or unreadable image file")
    height, width = img.shape[:2]
    if height * width > MAX_IMAGE_PIXELS:
        raise HTTPException(status_code=422, detail="Image resolution is too large")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


@router.get("/models")
def model_status(current_user: TokenData = Depends(get_authenticated_user)):
    status = cv.registry.status()
    training = cv.read_model_metrics()
    # merge training info into each model's status object
    for key in ("raildoc_detector",):
        status[key]["training"] = training.get(key, {})
    return status


def _serve_model_image(rel: Path) -> FileResponse:
    if not rel.exists():
        raise HTTPException(status_code=404, detail="artifact not found")
    return FileResponse(rel, media_type="image/jpeg")


@router.get("/models/{model_key}/artifact/{name}")
def model_artifact(
    model_key: str,
    name: str,
    current_user: TokenData = Depends(get_authenticated_user),
):
    """Serve training artifacts (results.png, confusion_matrix.png,
    val_batch*_pred.jpg) for the Model Info screen."""
    dirs = {
        "raildoc_detector": cv.RAILDOC_DET_DIR,
    }
    base = dirs.get(model_key)
    if base is None or not name.isascii() or "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=404, detail="unknown artifact")
    return _serve_model_image(base / name)


@router.get("/samples")
def sample_predictions(
    current_user: TokenData = Depends(get_authenticated_user),
):
    """Run live inference on a few bundled dataset images so the Model Info
    screen shows real predictions with bounding boxes."""
    import glob as _glob

    samples: list[dict] = []

    def _first(pattern: str) -> Optional[str]:
        files = sorted(_glob.glob(str(ROOT / pattern)))
        return files[0] if files else None

    # Sample frames from the bundled RAILDOC_02.yolo26 test/valid splits.
    # The unified detector reports every class it finds on each frame.
    jobs = [
        "RAILDOC_02.yolo26/test/images/*.jpg",
        "RAILDOC_02.yolo26/valid/images/*.jpg",
    ]
    for pattern in jobs:
        path = _first(pattern)
        if not path:
            continue
        try:
            from PIL import Image

            img = np.array(Image.open(path).convert("RGB"))
            result = cv.run_inference_auto(img, draw=True)
            samples.append({
                "asset_type": result.asset_type,
                "source": Path(path).name,
                "is_defective": result.is_defective,
                "detections": [
                    {
                        "defect_type": d.defect_type,
                        "confidence": d.confidence,
                        "bbox": d.bbox,
                        "severity": d.severity,
                    }
                    for d in result.detections
                ],
                "annotated_image_b64": result.annotated_image_b64,
            })
        except Exception as e:
            # `asset_type` is not in scope here — referencing it turned any
            # sample-inference failure into a NameError 500 instead of the
            # graceful per-sample error entry.
            samples.append({"asset_type": "auto", "source": Path(path).name,
                            "error": str(e)})

    return {"samples": samples}


@router.post("/analyze")
async def analyze_image(
    file: UploadFile = File(...),
    asset_type: str = Form("track"),
    draw: bool = Form(True),
    current_user: TokenData = Depends(get_authenticated_user),
):
    if asset_type not in ("track", "light_pole"):
        raise HTTPException(status_code=422, detail="asset_type must be 'track' or 'light_pole'")

    data = await _read_upload_capped(file)
    # Decode + YOLO are CPU-bound: both move off the event loop onto the
    # bounded heavy pool, so concurrent uploads cannot stall unrelated
    # requests. Bounded means excess jobs QUEUE instead of piling onto
    # threads that only fight each other for the GIL.
    image = await run_heavy(_decode_image, data)

    started = time.time()
    try:
        result = await run_heavy(cv.run_inference, image, asset_type, draw=draw)
    except RuntimeError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "CV model not available — training may still be running.",
                "reason": str(e),
                "models": cv.registry.status(),
            },
        )

    return {
        "analysis_id": uuid.uuid4().hex[:12],
        "asset_type": asset_type,
        "is_defective": result.is_defective,
        "detections": [
            {
                "label": d.label,
                "confidence": d.confidence,
                "bbox": d.bbox,
                "severity": d.severity,
                "defect_type": d.defect_type,
                "asset_type": d.asset_type,
            }
            for d in result.detections
        ],
        "annotated_image_b64": result.annotated_image_b64,
        "model_info": result.model_info,
        "inference_ms": round((time.time() - started) * 1000, 1),
    }


class TicketRequest(dict):
    pass


@router.post("/ticket")
def create_ticket(
    body: dict,
    current_user: TokenData = Depends(require_roles(
        UserRole.ADMIN, UserRole.PLANNER, UserRole.ENGINEER, UserRole.OPERATIONS,
    )),
):
    """Create a pending maintenance task from a detection result.

    Expected body: { detection: {...}, corridor_id, location, asset_id? }

    The generated task references an existing asset row of the matching
    department/corridor (FK constraint); if none exists a new asset is
    inserted first.
    """
    detection = body.get("detection") or {}
    if not detection:
        raise HTTPException(status_code=422, detail="detection object is required")

    corridor_id = body.get("corridor_id", "C-01")

    # FK safety: a corridor_id that doesn't exist in the corridors table
    # (stale UI state, empty dropdown, hostile payload) violates
    # assets_corridor_id_fkey on the generated asset — PostgREST surfaces
    # that as an opaque HTTP 409. Substitute a real corridor instead of
    # failing the whole ticket.
    try:
        valid_corridors = {c.get("corridor_id") for c in db.get_corridors()} - {None}
    except Exception:
        valid_corridors = None  # cannot validate (DB down) — keep as-is
    if valid_corridors and corridor_id not in valid_corridors:
        corridor_id = sorted(valid_corridors)[0]

    defect_type = detection.get("defect_type", "track_defect")
    severity = detection.get("severity", "medium")
    department = ("Engineering" if defect_type in ("track_defect", "rail_crack")
                  else "Traction")

    # Resolve a real asset_id (FK) — prefer same corridor + department.
    asset_id = body.get("asset_id")
    if not asset_id:
        try:
            assets = db.get_assets()
            match = next((a for a in assets
                          if a.get("corridor_id") == corridor_id
                          and a.get("department") == department), None)
            match = match or next((a for a in assets
                                   if a.get("corridor_id") == corridor_id), None)
            asset_id = match["asset_id"] if match else None
        except Exception:
            asset_id = None
    if not asset_id:
        asset_id = cv.make_asset_id(detection.get("asset_type", "track"))
        try:
            db._upsert("assets", [{
                "asset_id": asset_id,
                "department": department,
                "asset_type": detection.get("asset_type", "track"),
                "corridor_id": corridor_id,
                "location": body.get("location", "KM 000.0"),
                "criticality": severity_criticality.get(severity, 60),
                "current_status": "Defect Detected",
                "availability": 60.0,
                "historical_failure_rate": 0.2,
            }])
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status is None or status >= 500:
                raise HTTPException(
                    status_code=502,
                    detail=f"Asset store rejected the generated asset (HTTP {status}).",
                ) from exc
            # 409/400/422: the generated asset cannot be written to the
            # remote table (merge-duplicates needs a matching unique
            # constraint; department/corridor FKs must already exist).
            # Reuse an existing asset instead of failing the whole ticket.
            try:
                assets = db.get_assets()
            except Exception:
                assets = []
            fallback = (
                next((a for a in assets
                      if a.get("corridor_id") == corridor_id
                      and a.get("department") == department), None)
                or next((a for a in assets
                         if a.get("corridor_id") == corridor_id), None)
                or (assets[0] if assets else None)
            )
            if fallback is None:
                raise HTTPException(
                    status_code=503,
                    detail=("No assets available to attach the ticket to — "
                            "seed the database first."),
                ) from exc
            asset_id = fallback["asset_id"]

    task_id = f"ENG-{uuid.uuid4().hex[:6].upper()}"

    task = {
        "task_id": task_id,
        "asset_id": asset_id,
        "department": department,
        "task_type": "Defect",
        "priority_score": 0.0,
        "criticality": severity_criticality.get(severity, 60),
        "failure_risk": min(99, int(detection.get("confidence", 0.7) * 100)),
        "days_overdue": 0,
        "safety_criticality": 90 if severity == "critical" else 65,
        "train_impact": 55,
        "due_date": str(date.today() + timedelta(days=1 if severity == "critical" else 7)),
        "estimated_duration_minutes": 60 if defect_type in ("track_defect", "rail_crack") else 45,
        "required_block_type": "Possession" if defect_type in ("track_defect", "rail_crack") else "Lines Up",
        "required_resources": ["track_crew", "repair_equipment"],
        "safety_requirements": ["Track Isolation"] if defect_type in ("track_defect", "rail_crack") else ["Lines Up"],
        "isolation_required": defect_type in ("track_defect", "rail_crack"),
        "dependencies": [],
        "corridor_id": corridor_id,
        "location": body.get("location", "KM 000.0"),
        "status": "Pending",
        "explanation": f"Created from inspection: {defect_type} detected "
                       f"with {detection.get('confidence', 0):.0%} confidence "
                       f"(severity: {severity}).",
    }

    # Persist the ticket. The asset may still have been resolved/inserted
    # moments ago, and the 6-hex task_id can in principle collide — a 409
    # here gets one retry with a fresh id before giving up with a clear
    # error (previously any conflict escaped as an unhandled 500).
    try:
        db._upsert("maintenance_tasks", [task])
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status is None or status >= 500:
            raise HTTPException(
                status_code=502,
                detail=f"Task store rejected the ticket (HTTP {status}).",
            ) from exc
        task_id = f"ENG-{uuid.uuid4().hex[:6].upper()}"
        task["task_id"] = task_id
        try:
            db._upsert("maintenance_tasks", [task])
        except httpx.HTTPStatusError as retry_exc:
            raise HTTPException(
                status_code=502,
                detail="Could not persist the maintenance ticket — please retry.",
            ) from retry_exc
    return {"ticket_id": task_id, "task": task}


@router.post("/workflow")
def run_workflow(
    body: dict,
    current_user: TokenData = Depends(require_roles(
        UserRole.ADMIN, UserRole.PLANNER, UserRole.ENGINEER, UserRole.OPERATIONS,
    )),
):
    """Run the full Admin-Agent orchestration for a detection ticket.

    Expected body: { ticket: { task_id, detection, corridor_id, location } }
    Returns the workflow log, engineer/planner results and ranked candidates.
    """
    from app.agents.admin import AdminAgent

    ticket = body.get("ticket") or {}
    if not ticket.get("detection"):
        raise HTTPException(status_code=422, detail="ticket.detection is required")

    tasks = db.get_tasks()
    trains = db.get_trains()
    windows = db.get_block_windows()

    agent = AdminAgent(tasks=tasks, trains=trains, block_windows=windows)
    result = agent.orchestrate(ticket)

    payload = result.to_dict()
    payload["corridor_id"] = ticket.get("corridor_id", "C-07")
    payload["location"] = ticket.get("location", "KM 000.0")
    _store_workflow(payload)
    return payload


@router.get("/workflow/{workflow_id}")
def get_workflow(workflow_id: str,
                 current_user: TokenData = Depends(get_authenticated_user)):
    wf = _WORKFLOWS.get(workflow_id)
    if wf is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    return wf


@router.post("/workflow/{workflow_id}/commit")
def commit_workflow(
    workflow_id: str,
    body: dict,
    request: Request,
    current_user: TokenData = Depends(require_roles(
        UserRole.ADMIN, UserRole.PLANNER, UserRole.ENGINEER, UserRole.OPERATIONS,
    )),
):
    """Human approval step: persist the selected candidate as a real
    maintenance block, mark its tasks Scheduled, and store an audit record.

    Body: { decision: 'approve', block_id? }  (reject simply returns ack)
    """
    from datetime import datetime

    from app.db import queries as db

    decision = str(body.get("decision") or "approve").lower()
    if decision not in ("approve", "reject"):
        raise HTTPException(status_code=400,
                            detail="decision must be 'approve' or 'reject'")

    # The check-then-set on wf["decision"] and the block insert are done under
    # a lock: two concurrent commits otherwise both pass the guard and
    # double-insert the same block_id (PK conflict -> 500).
    with _COMMIT_LOCK:
        wf = _WORKFLOWS.get(workflow_id)
        if wf is None:
            raise HTTPException(status_code=404, detail="workflow not found")

        if decision == "reject":
            wf["decision"] = "rejected"
            wf["decided_by"] = current_user.username
            try:
                from app.core.audit import log_audit

                log_audit(AuditEventType.PLAN_REJECTED, current_user.username,
                          get_client_ip(request), workflow_id=workflow_id)
            except Exception:
                pass
            return {"message": "Workflow rejected — no changes persisted",
                    "workflow_id": workflow_id}

        selected = wf.get("selected")
        if not selected:
            raise HTTPException(status_code=409,
                                detail="workflow has no selected candidate to commit")
        if wf.get("decision") == "approved":
            raise HTTPException(status_code=409, detail="workflow already committed")

        def _mins_to_hhmm(m: int) -> str:
            return f"{m // 60 % 24:02d}:{m % 60:02d}"

        block_id = str(body.get("block_id") or f"BLK-WF-{workflow_id[-8:]}")
        if len(block_id) > 64 or not all(c.isalnum() or c in "-_." for c in block_id):
            raise HTTPException(status_code=400, detail="invalid block_id")
        start_hhmm = _mins_to_hhmm(selected["block_start_min"])
        end_hhmm = _mins_to_hhmm(selected["block_end_min"])
        duration = selected["block_end_min"] - selected["block_start_min"]

        # Only persist tasks that actually exist in the DB. The triggering
        # ticket was created via /ticket, so it should be present; any legacy
        # task id referenced by the planner is included only if found.
        existing = {t["task_id"]: t for t in db.get_tasks()
                    if t["task_id"] in set(wf.get("tasks_created", []))}
        task_ids = list(existing.keys())

        block = {
            "block_id": block_id,
            "corridor_id": wf.get("corridor_id", "C-07"),
            "start_time": start_hhmm,
            "end_time": end_hhmm,
            "duration_minutes": duration,
            "block_type": wf.get("engineer", {}).get("required_block_type", "Block"),
            "utilization": selected["utilization"],
            "train_impact": float(selected["freight_conflicts"] + selected["passenger_conflicts"]),
            "status": "Approved",
            "explanation": (
                f"Approved from inspection workflow {workflow_id}: "
                f"{selected['strategy']} strategy, utility {selected['utility']}, "
                f"impact {selected['operational_impact']}."
            ),
            "assigned_tasks": task_ids,
            "departments": selected["departments"],
        }
        db.add_block(block)

        # Mark committed tasks Scheduled and linked to the block.
        for tid in existing:
            db.update_task(tid, {
                "status": "Scheduled",
                "assigned_block_id": block_id,
            })

        wf["decision"] = "approved"
        wf["decided_by"] = current_user.username
        wf["block_id"] = block_id

    # Audit trail (PRD §38): every approval must be recorded.
    try:
        from app.core.audit import log_audit

        log_audit(
            AuditEventType.PLAN_APPROVED,
            current_user.username,
            get_client_ip(request),
            block_id=block_id,
            workflow_id=workflow_id,
            scheduled_tasks=task_ids,
            utility=selected["utility"],
            strategy=selected["strategy"],
        )
    except Exception:
        pass  # audit failure must not roll back the approved plan

    return {
        "message": "Candidate committed as approved maintenance block",
        "workflow_id": workflow_id,
        "block_id": block_id,
        "scheduled_tasks": task_ids,
        "decided_by": current_user.username,
    }


@router.get("/workflows")
def list_workflows(current_user: TokenData = Depends(get_authenticated_user)):
    return [
        {k: wf[k] for k in ("workflow_id", "ticket_id", "selected")}
        for wf in _WORKFLOWS.values()
    ]


def _replan_core(body: dict, request: Request) -> dict:
    """Dynamic replanning (PRD §18): recalculate priorities, rerun the
    OR-Tools optimizer over current data, and persist the new plan.

    Body: { reason?: str }  — e.g. 'new_critical_defect'
    Returns the new blocks + before/after summary.

    CPU-bound (priority recalc + full solve): executed on the heavy pool
    by the async endpoint wrapper below.
    """
    from datetime import datetime

    from app.ai.priority_engine import calculate_all_priorities, generate_explanation
    from app.core.audit import log_audit
    from app.models.domain import (
        BlockWindow, MaintenanceTask, PriorityWeights, TaskStatus, Train,
    )
    from app.optimizer.block_optimizer import BlockOptimizer

    reason = body.get("reason", "manual_trigger")

    tasks_raw = db.get_tasks()
    weights_dict = db.get_weights()
    windows = db.get_block_windows()
    trains = db.get_trains()

    # 1. Recalculate priorities for pending tasks (typed models, as the
    #    /optimize endpoint builds them).
    tasks = [MaintenanceTask(**t) for t in tasks_raw]
    weights = PriorityWeights(**weights_dict)
    tasks = calculate_all_priorities(tasks, weights)
    for t in tasks:
        t.explanation = generate_explanation(t)

    # 2. Rerun the optimizer with typed windows/trains.
    windows_t = [BlockWindow(**w) for w in windows]
    trains_t = [Train(**t) for t in trains]

    optimizer = BlockOptimizer()
    blocks, metrics = optimizer.optimize(tasks, windows_t, trains_t, None, resource_factor=1.0)

    # 3. Persist blocks + reschedule tasks (same convention as /optimize).
    task_block_map = {}
    for block in blocks:
        for task_id in block.assigned_tasks:
            task_block_map[task_id] = block.block_id
    for t in tasks:
        if t.task_id in task_block_map:
            t.assigned_block_id = task_block_map[t.task_id]
            t.status = "Scheduled"
            t.explanation = generate_explanation(t)

    db.save_blocks([b.model_dump() for b in blocks])
    db.update_all_tasks([t.model_dump() for t in tasks])

    # 4. Audit trail.
    try:
        from app.api.auth import get_client_ip

        log_audit(
            AuditEventType.OPTIMIZATION_RUN,
            current_user.username,
            get_client_ip(request),
            reason=reason,
            blocks_created=len(blocks),
            tasks_scheduled=len(task_block_map),
        )
    except Exception:
        pass

    return {
        "message": f"Replan complete ({reason})",
        "reason": reason,
        "blocks": [b.model_dump() for b in blocks],
        "metrics": metrics.model_dump(),
        "tasks_scheduled": len(task_block_map),
        "total_tasks": len(tasks),
    }


@router.post("/replan")
async def dynamic_replan(
    body: dict,
    request: Request,
    current_user: TokenData = Depends(require_roles(
        UserRole.ADMIN, UserRole.PLANNER, UserRole.ENGINEER, UserRole.OPERATIONS,
    )),
):
    # Bounded heavy pool, same as /optimize and /simulate: concurrent
    # replans queue instead of stacking unbounded solver runs.
    return await run_heavy(_replan_core, body, request)
