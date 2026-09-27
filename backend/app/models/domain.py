from enum import Enum
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class Department(str, Enum):
    ENGINEERING = "Engineering"
    SIGNAL_TELECOM = "S&T"
    TRACTION = "Traction"


class TaskType(str, Enum):
    DEFECT = "Defect"
    OVERDUE = "Overdue"
    PREVENTIVE = "Preventive"
    INSPECTION = "Inspection"
    EMERGENCY = "Emergency"


class TaskStatus(str, Enum):
    PENDING = "Pending"
    SCHEDULED = "Scheduled"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    DEFERRED = "Deferred"


class BlockType(str, Enum):
    POSSESSION = "Possession"
    BLOCK = "Block"
    LINES_UP = "Lines Up"
    POWER_CUT = "Power Cut"


class Corridor(BaseModel):
    corridor_id: str
    name: str
    section: str
    capacity: int = 2
    restrictions: list[str] = []


class Asset(BaseModel):
    asset_id: str
    department: Department
    asset_type: str
    corridor_id: str
    location: str
    criticality: float = Field(ge=0, le=100)
    current_status: str = "Operational"
    availability: float = Field(ge=0, le=100, default=100.0)
    historical_failure_rate: float = 0.0


class MaintenanceTask(BaseModel):
    task_id: str
    asset_id: str
    department: Department
    task_type: TaskType
    priority_score: float = 0.0
    criticality: float = Field(ge=0, le=100, default=50.0)
    failure_risk: float = Field(ge=0, le=100, default=50.0)
    days_overdue: int = 0
    safety_criticality: float = Field(ge=0, le=100, default=50.0)
    train_impact: float = Field(ge=0, le=100, default=50.0)
    due_date: date
    estimated_duration_minutes: int = 60
    required_block_type: BlockType = BlockType.BLOCK
    required_resources: list[str] = []
    safety_requirements: list[str] = []
    isolation_required: bool = False
    dependencies: list[str] = []
    corridor_id: str = ""
    location: str = ""
    status: TaskStatus = TaskStatus.PENDING
    assigned_block_id: Optional[str] = None
    explanation: str = ""


class Train(BaseModel):
    train_id: str
    train_type: str
    route: str
    corridor_id: str
    scheduled_time: str
    priority: int = 1
    direction: str = "Up"


class BlockWindow(BaseModel):
    window_id: str
    corridor_id: str
    start_time: str
    end_time: str
    block_type: BlockType = BlockType.BLOCK
    day_of_week: int = 0


class MaintenanceBlock(BaseModel):
    block_id: str
    corridor_id: str
    start_time: str
    end_time: str
    duration_minutes: int = 0
    block_type: BlockType = BlockType.BLOCK
    assigned_tasks: list[str] = []
    departments: list[Department] = []
    utilization: float = 0.0
    train_impact: float = 0.0
    status: str = "Proposed"
    explanation: str = ""


class Plan(BaseModel):
    plan_id: str
    plan_type: str
    week_number: int
    corridor_id: str
    created_at: datetime = Field(default_factory=datetime.now)
    blocks: list[MaintenanceBlock] = []
    metrics: dict = {}
    status: str = "Draft"
    approved_by: Optional[str] = None


class PlanMetrics(BaseModel):
    asset_availability: float = 0.0
    maintenance_backlog: int = 0
    planned_blocks: int = 0
    train_conflicts: int = 0
    train_disruption_minutes: int = 0
    block_utilization: float = 0.0
    multi_dept_blocks: int = 0
    critical_tasks_completed: int = 0
    total_tasks: int = 0
    separate_blocks_avoided: int = 0
    total_downtime_minutes: int = 0


class PriorityWeights(BaseModel):
    asset_criticality: float = 0.30
    failure_risk: float = 0.25
    overdue_factor: float = 0.20
    train_impact: float = 0.15
    safety_criticality: float = 0.10


class WhatIfScenario(BaseModel):
    # Bounds mirror core.validation.WhatIfScenarioValidator: without them a
    # single hostile payload could hang the simulator (traffic_forecast_change
    # of 1e9 used to append ~75 billion Train objects) or poison scores with
    # NaN/inf. Units: traffic = fraction of current trains (-1..+5),
    # resource = percent (-100..100), duration = minutes (15..480).
    scenario_name: str = Field(default="", max_length=100)
    block_duration_override: Optional[int] = Field(default=None, ge=15, le=480)
    traffic_forecast_change: Optional[float] = Field(
        default=None, ge=-1.0, le=5.0, allow_inf_nan=False
    )
    asset_criticality_changes: dict[str, float] = {}
    corridor_restrictions: list[str] = Field(default_factory=list, max_length=20)
    resource_availability_change: Optional[float] = Field(
        default=None, ge=-100, le=100, allow_inf_nan=False
    )

    @field_validator("asset_criticality_changes")
    @classmethod
    def _validate_criticality_changes(cls, v: dict) -> dict:
        if len(v) > 50:
            raise ValueError("Too many asset criticality changes")
        for asset_id, crit in v.items():
            if len(asset_id) > 100:
                raise ValueError(f"Invalid asset_id: {asset_id!r}")
            # nan/inf fail these comparisons, so they are rejected here too.
            if isinstance(crit, bool) or not isinstance(crit, (int, float)) \
                    or not (0 <= crit <= 100):
                raise ValueError(f"Criticality must be 0-100: {crit!r}")
        return v
