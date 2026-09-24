"""临时展位三相配电排布 API。

启动时自动初始化 SQLite（见 database.init_db），无需额外迁移步骤。
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query

from . import database
from .schemas import (
    AllocationList,
    AllocationRequest,
    AllocationResult,
)
from .solver import SolveError, solve


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.init_db()
    yield


app = FastAPI(
    title="临时展位三相配电排布 API",
    description=(
        "提交最多 12 台设备的编号、功率与可接入相位，以及 A/B/C 各相容量，"
        "计算使三相负载极差最小的不可拆分单相接入方案；"
        "差值相同时按设备编号排序的相位序列取字典序最小。"
    ),
    version="1.0.0",
    lifespan=lifespan,
)


def _normalize_devices(request: AllocationRequest) -> list[dict]:
    return [
        {
            "id": device.id,
            "power": device.power,
            # 集合转有序列表后存储/回显，保证结果稳定
            "allowed_phases": sorted(device.allowed_phases),
        }
        for device in request.devices
    ]


@app.get("/", tags=["meta"])
def root() -> dict:
    return {"service": app.title, "docs": "/docs", "health": "/health"}


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/allocations", response_model=AllocationResult, status_code=201, tags=["allocations"])
def create_allocation(request: AllocationRequest) -> AllocationResult:
    capacities = request.capacities.model_dump()
    devices = _normalize_devices(request)

    message: str | None = None
    try:
        outcome = solve(devices, capacities)
    except SolveError as exc:
        outcome = None
        message = str(exc)

    if outcome is None:
        record = {
            "devices": devices,
            "capacities": capacities,
            "feasible": False,
            "assignments": None,
            "phase_loads": None,
            "load_diff": None,
            "message": message or "不存在满足各相容量约束的可行分配方案",
        }
        allocation_id = database.insert_allocation(record)
        persisted = database.get_allocation(allocation_id)
        return AllocationResult(**persisted)  # type: ignore[arg-type]

    record = {
        "devices": devices,
        "capacities": capacities,
        "feasible": True,
        "assignments": outcome["assignments"],
        "phase_loads": outcome["phase_loads"],
        "load_diff": outcome["load_diff"],
        "message": None,
    }
    allocation_id = database.insert_allocation(record)
    persisted = database.get_allocation(allocation_id)
    return AllocationResult(**persisted)  # type: ignore[arg-type]


@app.get("/api/allocations", response_model=AllocationList, tags=["allocations"])
def list_allocations(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> AllocationList:
    items = database.list_allocations(limit=limit, offset=offset)
    return AllocationList(
        total=database.count_allocations(),
        limit=limit,
        offset=offset,
        items=items,
    )


@app.get("/api/allocations/{allocation_id}", response_model=AllocationResult, tags=["allocations"])
def get_allocation(allocation_id: int) -> AllocationResult:
    record = database.get_allocation(allocation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="未找到该计算记录")
    return AllocationResult(**record)
