import re
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, ValidationError, model_validator


class TimeStringValidator:

    TIME_PATTERN = re.compile(r'^([01]?[0-9]|2[0-3]):([0-5][0-9])$')

    @classmethod
    def validate(cls, time_str: str) -> bool:
        return bool(cls.TIME_PATTERN.match(time_str))

    @classmethod
    def to_minutes(cls, time_str: str) -> int:
        if not cls.validate(time_str):
            raise ValueError(f"Invalid time format: {time_str}. Expected HH:MM")
        hours, minutes = map(int, time_str.split(":"))
        return hours * 60 + minutes

    @classmethod
    def from_minutes(cls, minutes: int) -> str:
        minutes = max(0, min(minutes, 23 * 60 + 59))
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours:02d}:{mins:02d}"


class DateValidator:

    @classmethod
    def validate(cls, date_str: str) -> bool:
        try:
            datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return True
        except ValueError:
            return False

    @classmethod
    def parse(cls, date_str: str) -> date:
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
        except ValueError as e:
            raise ValueError(f"Invalid date format: {date_str}. Expected ISO format") from e


class Sanitizer:

    MAX_STRING_LENGTH = 1000
    MAX_LIST_LENGTH = 100
    ALLOWED_CHARS = re.compile(r'^[a-zA-Z0-9\-_\.\s:,/()]+$')

    @classmethod
    def sanitize_string(cls, value: str, max_length: Optional[int] = None) -> str:
        if not isinstance(value, str):
            raise ValueError("Expected string")
        max_len = max_length or cls.MAX_STRING_LENGTH
        value = value[:max_len]
        value = value.replace('\x00', '')
        return value.strip()

    @classmethod
    def sanitize_list(cls, value: list, max_length: Optional[int] = None) -> list:
        if not isinstance(value, list):
            raise ValueError("Expected list")
        max_len = max_length or cls.MAX_LIST_LENGTH
        return [cls.sanitize_string(str(item)) for item in value[:max_len]]

    @classmethod
    def sanitize_dict(cls, value: dict, max_keys: int = 50) -> dict:
        if not isinstance(value, dict):
            raise ValueError("Expected dict")
        return {
            cls.sanitize_string(k, 100): cls.sanitize_string(str(v), 500)
            for k, v in list(value.items())[:max_keys]
        }


class WhatIfScenarioValidator(BaseModel):

    scenario_name: str = Field(default="", max_length=100)
    block_duration_override: Optional[int] = Field(default=None, ge=15, le=480)
    traffic_forecast_change: Optional[float] = Field(default=None, ge=-100, le=500)
    asset_criticality_changes: dict[str, float] = Field(default_factory=dict)
    corridor_restrictions: list[str] = Field(default_factory=list)
    resource_availability_change: Optional[float] = Field(default=None, ge=-100, le=100)

    @field_validator('scenario_name')
    @classmethod
    def validate_name(cls, v):
        return Sanitizer.sanitize_string(v, 100)

    @field_validator('asset_criticality_changes')
    @classmethod
    def validate_criticality_changes(cls, v):
        if len(v) > 50:
            raise ValueError("Too many asset criticality changes")
        for asset_id, crit in v.items():
            if not isinstance(asset_id, str) or not Sanitizer.ALLOWED_CHARS.match(asset_id):
                raise ValueError(f"Invalid asset_id: {asset_id}")
            if not isinstance(crit, (int, float)) or not (0 <= crit <= 100):
                raise ValueError(f"Criticality must be 0-100: {crit}")
        return v

    @field_validator('corridor_restrictions')
    @classmethod
    def validate_corridor_restrictions(cls, v):
        return Sanitizer.sanitize_list(v, 20)


class WeightsUpdateValidator(BaseModel):

    asset_criticality: Optional[float] = Field(default=None, ge=0, le=1)
    failure_risk: Optional[float] = Field(default=None, ge=0, le=1)
    overdue_factor: Optional[float] = Field(default=None, ge=0, le=1)
    train_impact: Optional[float] = Field(default=None, ge=0, le=1)
    safety_criticality: Optional[float] = Field(default=None, ge=0, le=1)

    @model_validator(mode='after')
    def check_sum(self):
        weights = [
            self.asset_criticality,
            self.failure_risk,
            self.overdue_factor,
            self.train_impact,
            self.safety_criticality
        ]
        total = sum(w for w in weights if w is not None)
        if total > 1.0:
            raise ValueError("Sum of weights cannot exceed 1.0")
        return self


class PlanApprovalValidator(BaseModel):

    action: str = Field(..., pattern="^(approve|reject)$")
    reason: Optional[str] = Field(default=None, max_length=500)


def validate_time_string(time_str: str) -> int:
    return TimeStringValidator.to_minutes(time_str)


def validate_positive_int(value: int, min_val: int = 1, max_val: int = 10000) -> int:
    if not isinstance(value, int):
        raise ValueError("Expected integer")
    if value < min_val or value > max_val:
        raise ValueError(f"Value must be between {min_val} and {max_val}")
    return value