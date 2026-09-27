"""Specialized agents: Engineer, Planner, Operations.

Each agent exposes one `analyze` method taking the structured AgentTask and
returning an AgentResult. They are deterministic heuristics (no LLM), which
keeps the MVP pipeline reproducible and fast, while the Admin Agent handles
decomposition and candidate assembly.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.protocol import AgentResult, AgentTask

# ─── Knowledge tables ─────────────────────────────────────────────────

DEFECT_KB: dict[str, dict] = {
    "track_defect": {
        "maintenance": "Rail Repair",
        "department": "Engineering",
        "duration_minutes": 60,
        "resources": ["track_crew", "repair_equipment"],
        "block_type": "Possession",
        "safety": ["Track Isolation"],
        "isolation_required": True,
    },
    "light_pole": {
        "maintenance": "Pole Inspection / Repair",
        "department": "Traction",
        "duration_minutes": 45,
        "resources": ["linemen", "access_equipment"],
        "block_type": "Lines Up",
        "safety": ["Lines Up"],
        "isolation_required": False,
    },
    "rail_crack": {
        "maintenance": "Rail Repair",
        "department": "Engineering",
        "duration_minutes": 60,
        "resources": ["track_crew", "repair_equipment"],
        "block_type": "Possession",
        "safety": ["Track Isolation"],
        "isolation_required": True,
    },
}

SEVERITY_MULTIPLIER = {"critical": 1.25, "high": 1.0, "medium": 0.85, "low": 0.7}


@dataclass
class EngineerAgent:
    """Determines what physical maintenance is required (PRD §7)."""

    name: str = "engineer_agent"

    def analyze(self, task: AgentTask) -> AgentResult:
        import time

        started = time.time()
        d = task.input.get("detection", {})
        defect_type = d.get("defect_type", "track_defect")
        severity = d.get("severity", "medium")
        kb = DEFECT_KB.get(defect_type, DEFECT_KB["track_defect"])

        duration = int(kb["duration_minutes"] * SEVERITY_MULTIPLIER.get(severity, 1.0))

        detail = {
            "maintenance": kb["maintenance"],
            "department": kb["department"],
            "estimated_duration_minutes": duration,
            "resources": kb["resources"],
            "required_block_type": kb["block_type"],
            "safety_requirements": kb["safety"],
            "isolation_required": kb["isolation_required"],
        }
        return AgentResult(
            task_id=task.task_id,
            agent=self.name,
            result="repair_required",
            detail=detail,
            duration_ms=round((time.time() - started) * 1000, 1),
        )


@dataclass
class PlannerAgent:
    """Finds compatible maintenance activities that can share a block (PRD §8)."""

    name: str = "planner_agent"

    # Isolation regimes that can never coexist in one block (mirrors the
    # optimizer's SAFETY_CONFLICTS). Canonical DB names use the
    # '... Required' suffix; short aliases are normalized first.
    INCOMPATIBLE_SAFETY = {
        frozenset({"Track Isolation", "Power Block Required"}),
        frozenset({"Track Isolation", "Lines Up"}),
        frozenset({"Power Block Required", "Lines Up"}),
    }

    # Cap on bundled tasks so a coordinated block stays reviewable.
    MAX_COMPATIBLE = 8

    @staticmethod
    def _normalize_safety(reqs: list[str]) -> set[str]:
        out = set()
        for r in reqs or []:
            r = str(r)
            if r.startswith("Power Block"):
                out.add("Power Block Required")
            elif r.startswith("Lines Up"):
                out.add("Lines Up")
            elif r.startswith("Track Isolation"):
                out.add("Track Isolation")
            else:
                out.add(r)  # procedural reqs (lookout, speed limit, …) don't conflict
        return out

    def analyze(self, task: AgentTask) -> AgentResult:
        import time

        started = time.time()
        engineer = task.input.get("engineer_result", {})
        target_dept = engineer.get("department", "Engineering")
        target_safety = self._normalize_safety(engineer.get("safety_requirements", []))
        target_block = engineer.get("required_block_type", "Possession")
        corridor_id = task.input.get("corridor_id", "")
        window_minutes = int(task.input.get("window_minutes") or 120)

        # Candidate pool of pending tasks in the same corridor that are not
        # the triggering task itself.
        pool: list[dict] = task.input.get("candidate_pool", [])
        candidates: list[tuple[float, dict]] = []
        for t in pool:
            if t.get("corridor_id") != corridor_id:
                continue
            if t.get("status") not in ("Pending", "pending"):
                continue
            safety = self._normalize_safety(t.get("safety_requirements", []))
            union = safety | target_safety
            if union and frozenset(union) in self.INCOMPATIBLE_SAFETY:
                # conflicting isolation regimes (e.g. Track Isolation +
                # Power Block) can never share a block
                continue
            dur = int(t.get("estimated_duration_minutes") or 60)
            score = float(t.get("priority_score") or 0.0)
            # prefer higher-priority, shorter tasks (pack more work in)
            candidates.append((score / max(dur, 1), {
                "task_id": t.get("task_id"),
                "department": t.get("department"),
                "estimated_duration_minutes": dur,
                "task_type": t.get("task_type"),
                "priority_score": score,
            }))

        # Greedy pack: highest value first, stop when the coordinated block
        # would exceed the target window (parallel depts run concurrently,
        # so block length = max dept workload, not the sum).
        candidates.sort(key=lambda x: x[0], reverse=True)
        compatible: list[dict] = []
        dept_load: dict[str, int] = {}
        for _score, c in candidates:
            dept = c["department"] or "Unknown"
            new_load = dept_load.get(dept, 0) + c["estimated_duration_minutes"]
            if new_load > window_minutes:
                continue
            dept_load[dept] = new_load
            compatible.append(c)
            if len(compatible) >= self.MAX_COMPATIBLE:
                break

        depts = sorted({target_dept} | {c["department"] for c in compatible if c.get("department")})
        dept_load[target_dept] = dept_load.get(target_dept, 0) + engineer.get("estimated_duration_minutes", 60)
        total_duration = max(dept_load.values()) if dept_load else engineer.get("estimated_duration_minutes", 60)

        return AgentResult(
            task_id=task.task_id,
            agent=self.name,
            result="compatible_tasks_found" if compatible else "no_compatible_tasks",
            detail={
                "compatible_tasks": compatible,
                "departments_involved": depts,
                "coordinated_block_minutes": total_duration,
                "corridor_id": corridor_id,
                "candidate_block_type": target_block,
            },
            duration_ms=round((time.time() - started) * 1000, 1),
        )


@dataclass
class OperationsAgent:
    """Evaluates operational impact of a candidate block (PRD §9)."""

    name: str = "operations_agent"

    def analyze(self, task: AgentTask) -> AgentResult:
        import time

        started = time.time()
        trains: list[dict] = task.input.get("trains", [])
        block_start_min = task.input.get("block_start_min", 0)
        block_end_min = task.input.get("block_end_min", 0)
        corridor_id = task.input.get("corridor_id", "")

        conflicts: list[dict] = []
        passenger_conflicts = 0
        freight_conflicts = 0

        for tr in trains:
            if tr.get("corridor_id") != corridor_id:
                continue
            parts = str(tr.get("scheduled_time", "00:00")).split(":")
            t_min = int(parts[0]) * 60 + int(parts[1])
            if block_start_min <= t_min < block_end_min:
                conflicts.append({
                    "train_id": tr.get("train_id"),
                    "train_type": tr.get("train_type"),
                    "scheduled_time": tr.get("scheduled_time"),
                })
                if str(tr.get("train_type", "")).lower().startswith("freight"):
                    freight_conflicts += 1
                else:
                    passenger_conflicts += 1

        if passenger_conflicts:
            impact = "High"
        elif freight_conflicts:
            impact = "Low"
        else:
            impact = "None"

        return AgentResult(
            task_id=task.task_id,
            agent=self.name,
            result="impact_assessed",
            detail={
                "corridor_id": corridor_id,
                "train_conflicts": conflicts,
                "passenger_conflicts": passenger_conflicts,
                "freight_conflicts": freight_conflicts,
                "operational_impact": impact,
            },
            duration_ms=round((time.time() - started) * 1000, 1),
        )
