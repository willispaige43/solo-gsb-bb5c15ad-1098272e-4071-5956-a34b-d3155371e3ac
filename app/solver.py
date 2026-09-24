"""三相负载均衡求解器。

规则：
- 每台设备不可拆分，只能接入其允许相位集合中的一个相位（A/B/C）。
- 各相负载之和不得超过该相容量。
- 目标 1：三相负载最大值与最小值之差最小。
- 目标 2（差值相同时）：按设备编号排序后的相位序列字典序最小。

设备按编号排序后做 DFS，分支按 A -> B -> C 顺序枚举，
因此同一差值下第一次命中的可行解就是字典序最小的相位序列。
最多 12 台设备时最坏仅 3^12 = 531441 个叶节点，穷举即可。
"""

from __future__ import annotations

from typing import Mapping, Sequence

PHASES = ("A", "B", "C")


class SolveError(ValueError):
    """输入结构非法（数量、编号、功率、相位取值等）。"""


def _normalize(
    devices: Sequence[Mapping[str, object]],
    capacities: Mapping[str, int],
) -> list[dict]:
    if not 1 <= len(devices) <= 12:
        raise SolveError("设备数量必须在 1 到 12 台之间")

    normalized: list[dict] = []
    seen_ids: set[str] = set()
    for raw in devices:
        device_id = str(raw["id"])
        if not device_id:
            raise SolveError("设备编号不能为空")
        if device_id in seen_ids:
            raise SolveError(f"设备编号重复: {device_id}")
        seen_ids.add(device_id)

        power = int(raw["power"])  # 类型/范围由 Pydantic 层保证，这里兜底
        if power <= 0:
            raise SolveError(f"设备 {device_id} 功率必须为正整数")

        allowed = tuple(sorted(set(raw["allowed_phases"])))  # type: ignore[arg-type]
        if not allowed:
            raise SolveError(f"设备 {device_id} 的可接入相位集合不能为空")
        for phase in allowed:
            if phase not in PHASES:
                raise SolveError(f"设备 {device_id} 存在非法相位: {phase}")

        normalized.append(
            {"id": device_id, "power": power, "allowed_phases": allowed}
        )

    normalized.sort(key=lambda d: d["id"])
    return normalized


def solve(
    devices: Sequence[Mapping[str, object]],
    capacities: Mapping[str, int],
) -> dict | None:
    """返回最优分配；无可行方案时返回 ``None``。

    返回结构::

        {
            "assignments": [{"id": ..., "phase": "A"}, ...],  # 按设备编号排序
            "phase_loads": {"A": int, "B": int, "C": int},
            "load_diff": int,
        }
    """
    ordered = _normalize(devices, capacities)

    # 显然不可行的快速判定，不影响搜索正确性
    if sum(d["power"] for d in ordered) > sum(capacities[p] for p in PHASES):
        return None
    if any(
        all(d["power"] > capacities[phase] for phase in d["allowed_phases"])
        for d in ordered
    ):
        return None

    loads = {p: 0 for p in PHASES}
    assignment: list[str | None] = [None] * len(ordered)

    best_key: tuple[int, tuple[str, ...]] | None = None
    best_assignment: tuple[str, ...] | None = None

    def dfs(index: int) -> None:
        nonlocal best_key, best_assignment

        if index == len(ordered):
            values = [loads[p] for p in PHASES]
            diff = max(values) - min(values)
            sequence = tuple(assignment)  # type: ignore[arg-type]
            key = (diff, sequence)
            if best_key is None or key < best_key:
                best_key = key
                best_assignment = sequence
            return

        # 已找到差值为 0 的理论最优解后无需继续枚举
        if best_key is not None and best_key[0] == 0:
            return

        device = ordered[index]
        for phase in device["allowed_phases"]:
            new_load = loads[phase] + device["power"]
            if new_load > capacities[phase]:
                continue

            loads[phase] = new_load
            assignment[index] = phase
            dfs(index + 1)
            loads[phase] -= device["power"]
            assignment[index] = None

    dfs(0)

    if best_assignment is None:
        return None

    phase_loads = {p: 0 for p in PHASES}
    result_assignments = []
    for device, phase in zip(ordered, best_assignment):
        phase_loads[phase] += device["power"]
        result_assignments.append({"id": device["id"], "phase": phase})

    values = [phase_loads[p] for p in PHASES]
    return {
        "assignments": result_assignments,
        "phase_loads": phase_loads,
        "load_diff": max(values) - min(values),
    }
