"""请求/响应模型与输入校验。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Phase = Literal["A", "B", "C"]


class DeviceIn(BaseModel):
    model_config = ConfigDict(strict=True)

    id: str = Field(..., description="设备唯一编号")
    power: int = Field(..., strict=True, description="设备功率（瓦，正整数）")
    allowed_phases: set[Phase] = Field(
        ..., min_length=1, description="非空可接入相位集合，取值 A/B/C"
    )

    @field_validator("id")
    @classmethod
    def _id_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("设备编号不能为空")
        return value

    @field_validator("power")
    @classmethod
    def _power_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("设备功率必须为正整数")
        return value


class Capacities(BaseModel):
    model_config = ConfigDict(strict=True)

    A: int = Field(..., strict=True, ge=0, description="A 相容量（瓦，非负整数）")
    B: int = Field(..., strict=True, ge=0, description="B 相容量（瓦，非负整数）")
    C: int = Field(..., strict=True, ge=0, description="C 相容量（瓦，非负整数）")


class AllocationRequest(BaseModel):
    devices: list[DeviceIn] = Field(..., min_length=1, max_length=12)
    capacities: Capacities

    @model_validator(mode="after")
    def _unique_device_ids(self) -> "AllocationRequest":
        ids = [device.id for device in self.devices]
        duplicates = sorted({device_id for device_id in ids if ids.count(device_id) > 1})
        if duplicates:
            raise ValueError(f"设备编号必须唯一，重复编号: {', '.join(duplicates)}")
        return self


class AssignmentOut(BaseModel):
    id: str
    phase: Phase


class DeviceOut(BaseModel):
    id: str
    power: int
    allowed_phases: list[Phase]


class AllocationResult(BaseModel):
    id: int
    created_at: str
    feasible: bool
    devices: list[DeviceOut]
    capacities: dict[str, int]
    assignments: list[AssignmentOut] | None
    phase_loads: dict[str, int] | None
    load_diff: int | None
    message: str | None


class AllocationSummary(BaseModel):
    id: int
    created_at: str
    feasible: bool
    load_diff: int | None
    message: str | None


class AllocationList(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[AllocationSummary]
