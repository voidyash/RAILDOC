import json
import logging
import threading
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger("audit")


class AuditEventType(str, Enum):
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    PLAN_CREATED = "plan_created"
    PLAN_APPROVED = "plan_approved"
    PLAN_REJECTED = "plan_rejected"
    PLAN_MODIFIED = "plan_modified"
    WEIGHTS_UPDATED = "weights_updated"
    DATA_REGENERATED = "data_regenerated"
    OPTIMIZATION_RUN = "optimization_run"
    SIMULATION_RUN = "simulation_run"
    TASK_PRIORITY_CALCULATED = "task_priority_calculated"
    BLOCK_ASSIGNED = "block_assigned"
    CONFIG_CHANGED = "config_changed"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"


@dataclass
class AuditEntry:
    timestamp: str
    event_type: str
    username: str
    client_ip: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    action: Optional[str] = None
    details: Optional[dict] = None
    status: str = "success"
    error_message: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), default=str)


class AuditLogger:

    def __init__(self, log_dir: str = "logs/audit", max_file_size_mb: int = 10, max_files: int = 30):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.max_file_size = max_file_size_mb * 1024 * 1024
        self.max_files = max_files
        self.current_file: Optional[Path] = None
        self.current_size = 0
        self.lock = threading.Lock()
        self._init_file()

    def _init_file(self):
        timestamp = datetime.now().strftime("%Y%m%d")
        self.current_file = self.log_dir / f"audit_{timestamp}.log"
        if self.current_file.exists():
            self.current_size = self.current_file.stat().st_size
        else:
            self.current_size = 0

    def _rotate_if_needed(self):
        if self.current_size >= self.max_file_size:
            self._rotate()

    def _rotate(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_file = self.log_dir / f"audit_{timestamp}.log"
        self.current_file.rename(new_file)
        self._cleanup_old_files()
        self._init_file()

    def _cleanup_old_files(self):
        files = sorted(self.log_dir.glob("audit_*.log"), key=lambda f: f.stat().st_mtime, reverse=True)
        for old_file in files[self.max_files:]:
            old_file.unlink(missing_ok=True)

    def log(
        self,
        event_type: AuditEventType,
        username: str,
        client_ip: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        action: Optional[str] = None,
        details: Optional[dict] = None,
        status: str = "success",
        error_message: Optional[str] = None,
    ):
        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            event_type=event_type.value,
            username=username,
            client_ip=client_ip,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            details=details,
            status=status,
            error_message=error_message,
        )

        with self.lock:
            self._rotate_if_needed()
            with open(self.current_file, "a", encoding="utf-8") as f:
                f.write(entry.to_json() + "\n")
            self.current_size += len(entry.to_json()) + 1

        logger.info(entry.to_json())


audit_logger = AuditLogger()


def log_audit(
    event_type: AuditEventType,
    username: str,
    client_ip: str,
    **kwargs,
):
    audit_logger.log(event_type, username, client_ip, **kwargs)