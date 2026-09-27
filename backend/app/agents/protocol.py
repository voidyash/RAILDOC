"""Structured agent-to-agent communication protocol (PRD §29).

Agents exchange task objects, not free-form chat. Every request carries a
`task_id`, `requested_by`, `assigned_to` and `action`; every response echoes
the `task_id` plus a structured `result`. This keeps the multi-agent flow
deterministic, debuggable and auditable.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@dataclass
class AgentTask:
    """Request object sent by the Admin Agent to a specialized agent."""

    task_id: str = field(default_factory=lambda: new_id("AGT"))
    requested_by: str = "admin_agent"
    assigned_to: str = ""
    action: str = ""
    input: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AgentResult:
    """Response object returned by a specialized agent."""

    task_id: str
    agent: str
    result: str                      # machine-readable outcome tag
    detail: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    error: Optional[str] = None
    completed_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WorkflowEvent:
    """Human-readable timeline entry for the Agent Monitor UI."""

    seq: int
    agent: str
    message: str
    status: str = "done"             # done | running | error | approval
    task_id: Optional[str] = None
    at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


class WorkflowLog:
    """Ordered event log for one orchestration run."""

    def __init__(self) -> None:
        self._events: list[WorkflowEvent] = []
        self._seq = 0

    def add(self, agent: str, message: str, status: str = "done",
            task_id: Optional[str] = None) -> WorkflowEvent:
        self._seq += 1
        ev = WorkflowEvent(seq=self._seq, agent=agent, message=message,
                           status=status, task_id=task_id)
        self._events.append(ev)
        return ev

    def events(self) -> list[dict]:
        return [e.to_dict() for e in self._events]
