"""Admin Agent — master orchestrator (PRD §5).

Receives a detection ticket, decomposes the problem into structured
subtasks, dispatches them to the Engineer / Planner / Operations agents,
collects results, builds candidate plans, scores them with the utility
engine and hands the best candidate to the OR-Tools optimizer.

The full run is recorded as a WorkflowLog so the UI can replay it in the
Agent Monitor.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from app.agents.protocol import AgentTask, WorkflowLog, new_id
from app.agents.specialists import EngineerAgent, OperationsAgent, PlannerAgent

# Utility weights (configurable; PRD §10).
UTILITY_WEIGHTS = {
    "critical_completion": 0.30,
    "block_utilization": 0.20,
    "multi_department": 0.15,
    "train_disruption": 0.20,      # negative
    "downtime": 0.15,              # negative
}


@dataclass
class CandidatePlan:
    """One candidate strategy evaluated by the utility engine."""

    plan_id: str
    strategy: str                       # 'immediate' | 'coordinated' | 'deferred'
    block_start_min: int
    block_end_min: int
    task_ids: list[str]
    departments: list[str]
    operational_impact: str = "None"
    freight_conflicts: int = 0
    passenger_conflicts: int = 0
    utilization: float = 0.0
    utility: float = 0.0
    explanation: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class OrchestrationResult:
    workflow_id: str
    ticket_id: str
    log: WorkflowLog
    engineer: dict
    planner: dict
    candidates: list[CandidatePlan]
    selected: Optional[CandidatePlan]
    tasks_created: list[str]

    def to_dict(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "ticket_id": self.ticket_id,
            "log": self.log.events(),
            "engineer": self.engineer,
            "planner": self.planner,
            "candidates": [c.to_dict() for c in self.candidates],
            "selected": self.selected.to_dict() if self.selected else None,
            "tasks_created": self.tasks_created,
        }


class AdminAgent:
    """Coordinates the full detect → analyze → plan → optimize flow."""

    def __init__(self, tasks: list[dict], trains: list[dict],
                 block_windows: list[dict]) -> None:
        self.engineer = EngineerAgent()
        self.planner = PlannerAgent()
        self.operations = OperationsAgent()
        self.tasks = tasks
        self.trains = trains
        self.block_windows = block_windows

    # ── helpers ──────────────────────────────────────────────────────

    def _windows_for(self, corridor_id: str, block_type: str) -> list[dict]:
        out = []
        for w in self.block_windows:
            if w.get("corridor_id") != corridor_id:
                continue
            if block_type and w.get("block_type") not in (block_type, "Block"):
                continue
            out.append(w)
        return out or [w for w in self.block_windows if w.get("corridor_id") == corridor_id]

    @staticmethod
    def _to_minutes(hhmm: str) -> int:
        parts = str(hhmm).split(":")
        return int(parts[0]) * 60 + int(parts[1])

    @staticmethod
    def _train_disruption_minutes(cand: CandidatePlan, trains: list[dict]) -> int:
        disruption = 0
        for tr in trains:
            if tr.get("corridor_id") != cand.task_ids and False:
                continue
        return disruption

    # ── main entry ───────────────────────────────────────────────────

    def orchestrate(self, ticket: dict) -> OrchestrationResult:
        started = time.time()
        log = WorkflowLog()
        workflow_id = new_id("WF")

        detection = ticket.get("detection", {})
        corridor_id = ticket.get("corridor_id", "C-01")
        log.add("detection_agent",
                f"Defect identified: {detection.get('defect_type', 'unknown')} "
                f"({detection.get('severity', 'medium')}, "
                f"confidence {detection.get('confidence', 0):.0%})")

        # STEP 1 — Engineer Agent: what work is required?
        eng_task = AgentTask(assigned_to="engineer_agent", action="assess_repair",
                             input={"detection": detection})
        eng_result = self.engineer.analyze(eng_task)
        log.add("engineer_agent",
                f"Repair requirements determined: "
                f"{eng_result.detail['maintenance']}, "
                f"{eng_result.detail['estimated_duration_minutes']} min, "
                f"dept {eng_result.detail['department']}",
                task_id=eng_task.task_id)

        # STEP 2 — Planner Agent: which pending tasks can share the block?
        # Use the default target window from the engineer estimate as the
        # packing budget; per-window candidates are re-derived below.
        plan_task = AgentTask(assigned_to="planner_agent", action="find_compatible",
                              input={
                                  "engineer_result": eng_result.detail,
                                  "candidate_pool": self.tasks,
                                  "corridor_id": corridor_id,
                                  "window_minutes": max(
                                      120,
                                      int(eng_result.detail.get("estimated_duration_minutes", 60) * 1.5)),
                              })
        plan_result = self.planner.analyze(plan_task)
        compat = plan_result.detail["compatible_tasks"]
        log.add("planner_agent",
                f"{len(compat)} compatible task(s) found in corridor "
                f"{corridor_id}; departments: "
                f"{', '.join(plan_result.detail['departments_involved'])}",
                task_id=plan_task.task_id)

        # STEP 3 — Build candidate plans over available block windows.
        windows = self._windows_for(corridor_id,
                                    eng_result.detail.get("required_block_type", ""))
        candidates: list[CandidatePlan] = []

        task_ids = [ticket.get("task_id", new_id("ENG"))] + \
                   [c["task_id"] for c in compat]
        departments = plan_result.detail["departments_involved"]
        duration_needed = plan_result.detail["coordinated_block_minutes"]

        for w in windows[:5]:
            w_start = self._to_minutes(w["start_time"])
            w_end = self._to_minutes(w["end_time"])
            window_len = w_end - w_start
            if window_len <= 0:
                continue

            # three strategies per window
            for strategy, end_offset in (
                ("immediate", min(w_start + duration_needed, w_end)),
                ("coordinated", min(w_start + int(duration_needed * 1.15), w_end)),
                ("deferred", w_end),
            ):
                if end_offset <= w_start:
                    continue
                cand = CandidatePlan(
                    plan_id=new_id("CAND"),
                    strategy=strategy,
                    block_start_min=w_start,
                    block_end_min=end_offset,
                    task_ids=task_ids,
                    departments=departments,
                )
                used = (end_offset - w_start)
                cand.utilization = round(
                    min(1.0, duration_needed / max(used, 1)), 3)

                # Operations Agent evaluates each candidate window
                ops_task = AgentTask(
                    assigned_to="operations_agent",
                    action="assess_impact",
                    input={
                        "trains": self.trains,
                        "corridor_id": corridor_id,
                        "block_start_min": cand.block_start_min,
                        "block_end_min": cand.block_end_min,
                    })
                ops_result = self.operations.analyze(ops_task)
                cand.operational_impact = ops_result.detail["operational_impact"]
                cand.freight_conflicts = ops_result.detail["freight_conflicts"]
                cand.passenger_conflicts = ops_result.detail["passenger_conflicts"]

                candidates.append(cand)

        # STEP 4 — Utility scoring (PRD §10).
        for cand in candidates:
            cand.utility = _score_candidate(cand, duration_needed)

        candidates.sort(key=lambda c: c.utility, reverse=True)
        log.add("operations_agent",
                f"{len(candidates)} candidate plan(s) evaluated; "
                f"best utility {candidates[0].utility:.1f}" if candidates
                else "No feasible candidate window found")

        selected = candidates[0] if candidates else None
        log.add("admin_agent",
                f"Selected candidate {selected.plan_id} "
                f"({selected.strategy})" if selected
                else "Escalating: no candidate plan feasible — human review required")

        return OrchestrationResult(
            workflow_id=workflow_id,
            ticket_id=ticket.get("ticket_id", ""),
            log=log,
            engineer=eng_result.detail,
            planner=plan_result.detail,
            candidates=candidates,
            selected=selected,
            tasks_created=task_ids,
        )


def _score_candidate(cand: CandidatePlan, duration_needed: int) -> float:
    """Utility = benefits − penalties, weighted per PRD §10."""
    critical_completion = 1.0 if "Engineering" in cand.departments else 0.6
    multi_dept = min(1.0, (len(cand.departments) - 1) / 2)

    disruption_penalty = {
        "None": 0.0, "Low": 0.35, "High": 1.0,
    }[cand.operational_impact]

    downtime_min = cand.block_end_min - cand.block_start_min
    downtime_penalty = min(1.0, downtime_min / 240)

    utility = 100 * (
        UTILITY_WEIGHTS["critical_completion"] * critical_completion
        + UTILITY_WEIGHTS["block_utilization"] * cand.utilization
        + UTILITY_WEIGHTS["multi_department"] * multi_dept
        - UTILITY_WEIGHTS["train_disruption"] * disruption_penalty
        - UTILITY_WEIGHTS["downtime"] * downtime_penalty
    )
    return round(utility, 1)
