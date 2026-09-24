"""求解器测试：与穷举全部相位组合的参考实现交叉验证。

纯标准库，可直接运行：python3 tests/test_solver.py
"""

import itertools
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.solver import SolveError, solve  # noqa: E402


def brute_force(devices, capacities):
    """枚举所有相位组合，严格按 (极差, 相位序列) 取最优。"""
    ordered = sorted(devices, key=lambda d: d["id"])
    best = None
    for combo in itertools.product("ABC", repeat=len(ordered)):
        loads = {"A": 0, "B": 0, "C": 0}
        feasible = True
        for device, phase in zip(ordered, combo):
            if phase not in device["allowed_phases"]:
                feasible = False
                break
            loads[phase] += device["power"]
            if loads[phase] > capacities[phase]:
                feasible = False
                break
        if not feasible:
            continue
        diff = max(loads.values()) - min(loads.values())
        key = (diff, combo)
        if best is None or key < best[0]:
            best = (key, loads)
    return best


def test_basic_balance():
    devices = [
        {"id": f"D{i}", "power": p, "allowed_phases": {"A", "B", "C"}}
        for i, p in enumerate([3, 3, 3, 2, 2, 2], 1)
    ]
    result = solve(devices, {"A": 10, "B": 10, "C": 10})
    assert result["load_diff"] == 0
    assert result["phase_loads"] == {"A": 5, "B": 5, "C": 5}


def test_constrained_phases():
    devices = [
        {"id": "X1", "power": 5, "allowed_phases": {"A"}},
        {"id": "X2", "power": 4, "allowed_phases": {"A", "B"}},
        {"id": "X3", "power": 4, "allowed_phases": {"B", "C"}},
    ]
    result = solve(devices, {"A": 9, "B": 5, "C": 5})
    assert [a["phase"] for a in result["assignments"]] == ["A", "B", "C"]
    assert result["phase_loads"] == {"A": 5, "B": 4, "C": 4}
    assert result["load_diff"] == 1


def test_diff_has_priority_over_lex_order():
    # AA -> 2/0/0 极差 2；AB -> 1/1/0 极差 1，极差优先
    devices = [
        {"id": "a", "power": 1, "allowed_phases": {"A", "B", "C"}},
        {"id": "b", "power": 1, "allowed_phases": {"A", "B", "C"}},
    ]
    result = solve(devices, {"A": 2, "B": 2, "C": 2})
    assert [a["phase"] for a in result["assignments"]] == ["A", "B"]
    assert result["load_diff"] == 1


def test_lexicographic_tie_break():
    # 三台 2W 只允许 A/C：AAC 与 ACC 极差同为 4，AAC 字典序更小
    devices = [
        {"id": f"d{i}", "power": 2, "allowed_phases": {"A", "C"}} for i in range(3)
    ]
    result = solve(devices, {"A": 6, "B": 6, "C": 6})
    assert result["load_diff"] == 4
    assert tuple(a["phase"] for a in result["assignments"]) == ("A", "A", "C")
    assert result["phase_loads"] == {"A": 4, "B": 0, "C": 2}


def test_infeasible_returns_none():
    # 单设备超过其所有允许相位的容量
    assert solve(
        [{"id": "z", "power": 99, "allowed_phases": {"A"}}],
        {"A": 1, "B": 1, "C": 1},
    ) is None
    # 其他相容量再大也不可用
    assert solve(
        [{"id": "z", "power": 99, "allowed_phases": {"A"}}],
        {"A": 1, "B": 100, "C": 100},
    ) is None
    assert solve(
        [{"id": "z", "power": 5, "allowed_phases": {"A", "B"}}],
        {"A": 4, "B": 4, "C": 100},
    ) is None
    # 相位限制造成的组合冲突：两台 6W 都只能接 A
    assert solve(
        [
            {"id": "z1", "power": 6, "allowed_phases": {"A"}},
            {"id": "z2", "power": 6, "allowed_phases": {"A"}},
        ],
        {"A": 6, "B": 100, "C": 100},
    ) is None
    # 总容量不足
    assert solve(
        [{"id": "z", "power": 10, "allowed_phases": {"A", "B", "C"}}],
        {"A": 3, "B": 3, "C": 3},
    ) is None


def test_invalid_input_raises():
    for bad in (
        [],
        [{"id": "z", "power": 0, "allowed_phases": {"A"}}],
        [{"id": "z", "power": -1, "allowed_phases": {"A"}}],
        [{"id": "z", "power": 1, "allowed_phases": set()}],
        [{"id": "z", "power": 1, "allowed_phases": {"D"}}],
        [
            {"id": "z", "power": 1, "allowed_phases": {"A"}},
            {"id": "z", "power": 1, "allowed_phases": {"A"}},
        ],
    ):
        try:
            solve(bad, {"A": 1, "B": 1, "C": 1})
        except SolveError:
            continue
        raise AssertionError(f"expected SolveError for {bad!r}")


def test_result_sorted_by_device_id():
    devices = [
        {"id": "m", "power": 1, "allowed_phases": {"A", "B", "C"}},
        {"id": "a", "power": 1, "allowed_phases": {"A", "B", "C"}},
        {"id": "z", "power": 1, "allowed_phases": {"A", "B", "C"}},
    ]
    result = solve(devices, {"A": 3, "B": 3, "C": 3})
    assert [a["id"] for a in result["assignments"]] == ["a", "m", "z"]
    assert [a["phase"] for a in result["assignments"]] == ["A", "B", "C"]


def test_random_cases_match_brute_force():
    random.seed(42)
    start = time.time()
    for trial in range(300):
        n = random.randint(1, 12)
        devices = [
            {
                "id": f"dev-{i:02d}",
                "power": random.randint(1, 8),
                "allowed_phases": set(random.sample("ABC", random.randint(1, 3))),
            }
            for i in range(n)
        ]
        capacities = {p: random.randint(0, 30) for p in "ABC"}
        result = solve(devices, capacities)
        reference = brute_force(devices, capacities)
        if reference is None:
            assert result is None, (trial, devices, capacities, result)
            continue
        assert result is not None, (trial, devices, capacities)
        sequence = tuple(a["phase"] for a in result["assignments"])
        assert (result["load_diff"], sequence) == reference[0], (
            trial,
            (result["load_diff"], sequence),
            reference[0],
        )
        for phase in "ABC":
            ordered = sorted(devices, key=lambda d: d["id"])
            assert result["phase_loads"][phase] == sum(
                d["power"]
                for d, p in zip(ordered, reference[0][1])
                if p == phase
            )
    assert time.time() - start < 60


def test_max_scale_performance():
    devices = [
        {"id": f"M{i:02d}", "power": 1, "allowed_phases": {"A", "B", "C"}}
        for i in range(12)
    ]
    start = time.time()
    result = solve(devices, {"A": 4, "B": 4, "C": 4})
    elapsed = time.time() - start
    assert result["load_diff"] == 0
    assert elapsed < 2


def test_max_scale_infeasible_performance():
    devices = [
        {"id": f"M{i:02d}", "power": 3, "allowed_phases": {"A", "B", "C"}}
        for i in range(12)
    ]
    start = time.time()
    result = solve(devices, {"A": 10, "B": 10, "C": 10})
    elapsed = time.time() - start
    assert result is None
    assert elapsed < 2


if __name__ == "__main__":
    functions = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in functions:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(functions)} TESTS PASSED")
