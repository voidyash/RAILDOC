import json
import os
import threading
from copy import deepcopy
from datetime import datetime
from typing import Any, Optional

from app.models.domain import (
    MaintenanceTask, MaintenanceBlock, BlockWindow, Train,
    Asset, Corridor, Plan, PlanMetrics, PriorityWeights,
    WhatIfScenario, Department, TaskStatus
)


class DataStore:

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.lock = threading.RLock()
        self._version = 0

        self._assets: list[dict] = []
        self._tasks: list[dict] = []
        self._trains: list[dict] = []
        self._corridors: list[dict] = []
        self._block_windows: list[dict] = []
        self._blocks: list[dict] = []
        self._plans: list[dict] = []
        self._metrics: Optional[dict] = None
        self._weights = PriorityWeights()
        self._plan_versions: dict[str, list[dict]] = {}

    def _increment_version(self):
        self._version += 1
        return self._version

    def _deepcopy(self, data: Any) -> Any:
        return deepcopy(data)

    @property
    def version(self) -> int:
        with self.lock:
            return self._version

    def load_or_generate(self, generator_func):
        with self.lock:
            assets_path = os.path.join(self.data_dir, "assets.json")
            if os.path.exists(assets_path):
                for key, attr in [
                    ("assets", "_assets"),
                    ("tasks", "_tasks"),
                    ("trains", "_trains"),
                    ("corridors", "_corridors"),
                    ("block_windows", "_block_windows"),
                ]:
                    filepath = os.path.join(self.data_dir, f"{key}.json")
                    if os.path.exists(filepath):
                        with open(filepath) as f:
                            setattr(self, attr, json.load(f))
            else:
                data = generator_func()
                for key, value in data.items():
                    attr_name = f"_{key}"
                    if hasattr(self, attr_name):
                        setattr(self, attr_name, value)

    def get_assets(self) -> list[dict]:
        with self.lock:
            return self._deepcopy(self._assets)

    def set_assets(self, assets: list[dict]):
        with self.lock:
            self._assets = self._deepcopy(assets)

    def get_tasks(self) -> list[dict]:
        with self.lock:
            return self._deepcopy(self._tasks)

    def set_tasks(self, tasks: list[dict]):
        with self.lock:
            self._tasks = self._deepcopy(tasks)

    def update_task(self, task_id: str, updates: dict) -> bool:
        with self.lock:
            for i, task in enumerate(self._tasks):
                if task.get("task_id") == task_id:
                    self._tasks[i].update(updates)
                    return True
            return False

    def get_trains(self) -> list[dict]:
        with self.lock:
            return self._deepcopy(self._trains)

    def set_trains(self, trains: list[dict]):
        with self.lock:
            self._trains = self._deepcopy(trains)

    def get_corridors(self) -> list[dict]:
        with self.lock:
            return self._deepcopy(self._corridors)

    def set_corridors(self, corridors: list[dict]):
        with self.lock:
            self._corridors = self._deepcopy(corridors)

    def get_block_windows(self) -> list[dict]:
        with self.lock:
            return self._deepcopy(self._block_windows)

    def set_block_windows(self, windows: list[dict]):
        with self.lock:
            self._block_windows = self._deepcopy(windows)

    def get_blocks(self) -> list[dict]:
        with self.lock:
            return self._deepcopy(self._blocks)

    def set_blocks(self, blocks: list[dict]):
        with self.lock:
            self._blocks = self._deepcopy(blocks)

    def get_metrics(self) -> Optional[dict]:
        with self.lock:
            return self._deepcopy(self._metrics) if self._metrics else None

    def set_metrics(self, metrics: dict):
        with self.lock:
            self._metrics = self._deepcopy(metrics)

    def get_weights(self) -> PriorityWeights:
        with self.lock:
            return self._deepcopy(self._weights)

    def update_weights(self, updates: dict) -> PriorityWeights:
        with self.lock:
            for key, value in updates.items():
                if value is not None and hasattr(self._weights, key):
                    setattr(self._weights, key, value)
            return self._deepcopy(self._weights)

    def get_plans(self) -> list[dict]:
        with self.lock:
            return self._deepcopy(self._plans)

    def create_plan(self, plan_data: dict, username: str) -> dict:
        with self.lock:
            plan_id = f"PLAN-{datetime.now().strftime('%Y%m%d-%H%M%S')}-v{self._increment_version()}"
            plan = {
                **plan_data,
                "plan_id": plan_id,
                "created_at": datetime.now().isoformat(),
                "created_by": username,
                "version": 1,
                "status": "Draft",
            }
            self._plans.append(self._deepcopy(plan))
            self._plan_versions[plan_id] = [self._deepcopy(plan)]
            return plan

    def approve_plan(self, plan_id: str, username: str) -> Optional[dict]:
        with self.lock:
            for i, plan in enumerate(self._plans):
                if plan.get("plan_id") == plan_id:
                    if plan.get("status") == "Approved":
                        return None
                    plan["status"] = "Approved"
                    plan["approved_by"] = username
                    plan["approved_at"] = datetime.now().isoformat()
                    plan["version"] += 1
                    self._plan_versions[plan_id].append(self._deepcopy(plan))
                    return self._deepcopy(plan)
            return None

    def reject_plan(self, plan_id: str, username: str, reason: str) -> Optional[dict]:
        with self.lock:
            for i, plan in enumerate(self._plans):
                if plan.get("plan_id") == plan_id:
                    plan["status"] = "Rejected"
                    plan["rejected_by"] = username
                    plan["rejected_at"] = datetime.now().isoformat()
                    plan["rejection_reason"] = reason
                    plan["version"] += 1
                    self._plan_versions[plan_id].append(self._deepcopy(plan))
                    return self._deepcopy(plan)
            return None

    def get_plan_history(self, plan_id: str) -> list[dict]:
        with self.lock:
            return self._deepcopy(self._plan_versions.get(plan_id, []))

    def get_current_plan(self) -> dict:
        with self.lock:
            return {
                "blocks": self._deepcopy(self._blocks),
                "metrics": self._deepcopy(self._metrics),
                "total_tasks": len(self._tasks),
                "assigned_tasks": sum(len(b.get("assigned_tasks", [])) for b in self._blocks),
            }


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "synthetic")
data_store = DataStore(DATA_DIR)