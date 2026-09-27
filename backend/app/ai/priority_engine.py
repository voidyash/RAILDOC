from typing import Optional
from app.models.domain import MaintenanceTask, PriorityWeights


DEFAULT_WEIGHTS = PriorityWeights()


def normalize(value: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))


def calculate_overdue_factor(days_overdue: int) -> float:
    if days_overdue <= 0:
        return 0.0
    import math
    return min(1.0, math.log1p(days_overdue) / math.log1p(30))


def calculate_priority_score(
    task: MaintenanceTask,
    weights: Optional[PriorityWeights] = None
) -> float:
    w = weights or DEFAULT_WEIGHTS

    asset_crit = normalize(task.criticality)
    failure_risk = normalize(task.failure_risk)
    overdue = calculate_overdue_factor(task.days_overdue)
    train_impact = normalize(task.train_impact)
    safety_crit = normalize(task.safety_criticality)

    score = (
        w.asset_criticality * asset_crit +
        w.failure_risk * failure_risk +
        w.overdue_factor * overdue +
        w.train_impact * train_impact +
        w.safety_criticality * safety_crit
    ) * 100

    return round(score, 2)


def calculate_all_priorities(
    tasks: list[MaintenanceTask],
    weights: Optional[PriorityWeights] = None
) -> list[MaintenanceTask]:
    for task in tasks:
        task.priority_score = calculate_priority_score(task, weights)

    tasks.sort(key=lambda t: t.priority_score, reverse=True)
    return tasks


def generate_explanation(task: MaintenanceTask) -> str:
    parts = []

    if task.priority_score >= 80:
        parts.append("CRITICAL: High-priority task requiring immediate attention")
    elif task.priority_score >= 60:
        parts.append("HIGH: Important maintenance needed soon")
    elif task.priority_score >= 40:
        parts.append("MEDIUM: Scheduled maintenance recommended")
    else:
        parts.append("LOW: Can be deferred if needed")

    if task.days_overdue > 7:
        parts.append(f"Overdue by {task.days_overdue} days")
    elif task.days_overdue > 0:
        parts.append(f"Due date passed ({task.days_overdue} days)")

    if task.criticality >= 80:
        parts.append(f"Asset criticality: {task.criticality}/100")
    if task.failure_risk >= 70:
        parts.append(f"High failure risk: {task.failure_risk}%")
    if task.safety_criticality >= 70:
        parts.append("Safety-critical work")
    if task.train_impact >= 60:
        parts.append(f"High train impact: {task.train_impact}%")
    if task.isolation_required:
        parts.append("Isolation/power block required")

    compatible_count = 0
    parts.append(f"Corridor: {task.corridor_id}")

    return " | ".join(parts)


def get_priority_distribution(tasks: list[MaintenanceTask]) -> dict:
    critical = sum(1 for t in tasks if t.priority_score >= 80)
    high = sum(1 for t in tasks if 60 <= t.priority_score < 80)
    medium = sum(1 for t in tasks if 40 <= t.priority_score < 60)
    low = sum(1 for t in tasks if t.priority_score < 40)

    return {
        "critical": critical,
        "high": high,
        "medium": medium,
        "low": low,
        "total": len(tasks)
    }
