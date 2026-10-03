"""现行忌日读口 / 快照 / 引擎门禁的单元测试。"""

import json

import pytest

from app.engines.rota import build_week_slots, AllMembersUnavailableError
from app.engines.swap_gate import swap_legal as gate_swap_legal
from app.modules.memorial import store


def _set_days(c, member_id, days):
    c.execute("UPDATE members SET memorial_days=? WHERE id=?",
              (json.dumps(days) if days else None, member_id))
    c.commit()


# ---------- 现行忌日读口 ----------

def test_current_memorial_reads_member_days(c):
    _set_days(c, 1, [0, 3])
    _set_days(c, 2, [5])
    assert store.current_memorial(c) == {1: [0, 3], 2: [5]}


def test_current_memorial_filters_by_member_ids(c):
    _set_days(c, 1, [0])
    _set_days(c, 2, [1])
    assert store.current_memorial(c, [1]) == {1: [0]}
    assert store.current_memorial(c, []) == {}


def test_current_memorial_skips_empty_and_bad_json(c):
    _set_days(c, 1, [])
    c.execute("UPDATE members SET memorial_days='{bad' WHERE id=2")
    c.commit()
    assert store.current_memorial(c) == {}


def test_current_unavailable_sets(c):
    _set_days(c, 1, [3, 3, 0])
    assert store.current_unavailable(c, [1]) == {1: {0, 3}}


def test_build_snapshot_matches_current(c):
    _set_days(c, 1, [2, 0])
    snap = store.build_snapshot(c, [1, 2])
    assert snap == {"1": [0, 2]}  # 字符串键、去重排序，仅非空


# ---------- 生成派格 ----------

def test_generate_skips_memorial_day():
    slots = build_week_slots([1, 2, 3], [10, 20], days=3, unavailable={1: {0}})
    assert all(not (s["day"] == 0 and s["member_id"] == 1) for s in slots)
    # day0 两格由后续成员承接，相位前进：成员 2、3
    day0 = [s["member_id"] for s in slots if s["day"] == 0]
    assert day0 == [2, 3]


def test_generate_without_memorial_matches_baseline():
    base = build_week_slots([1, 2, 3], [10, 20, 30], days=7)
    assert build_week_slots([1, 2, 3], [10, 20, 30], days=7, unavailable={}) == base
    assert build_week_slots([1, 2, 3], [10, 20, 30], days=7, unavailable=None) == base


def test_generate_all_unavailable_same_day_raises():
    with pytest.raises(AllMembersUnavailableError) as ei:
        build_week_slots([1, 2, 3], [10], days=7, unavailable={1: {2}, 2: {2}, 3: {2}})
    assert ei.value.day == 2
    assert ei.value.reason == "all_unavailable"


def test_snapshot_pins_after_current_changes(c):
    """快照钉住：现行忌日随后收紧/改日，不回刷已生成周的快照。"""
    _set_days(c, 1, [0])
    snap_v1 = store.build_snapshot(c, [1, 2, 3])
    store.save_week_snapshot(c, 1, snap_v1)
    _set_days(c, 1, [5])  # 之后改现行忌日
    assert store.load_week_snapshot(c, 1) == {1: {0}}
    assert store.week_snapshot_json(c, 1) == {"1": [0]}


# ---------- 对调门禁（现行忌日，非快照） ----------

def _two_day_slots():
    # day0: m1,m2 ; day1: m1,m2
    return [
        {"day": 0, "task_id": 10, "member_id": 1},
        {"day": 0, "task_id": 20, "member_id": 2},
        {"day": 1, "task_id": 10, "member_id": 1},
        {"day": 1, "task_id": 20, "member_id": 2},
    ]


def test_swap_blocked_moving_into_memorial():
    r = gate_swap_legal(_two_day_slots(), 0, 10, 1, 20, {1: {1}})
    assert r["ok"] is False and r["reason"] == "memorial_blocked" and r["member_id"] == 1


def test_swap_allowed_moving_out_of_memorial():
    # m1 此刻正占在自己的忌日格 day0，把他移出不拦；m2 进 day0 无忌日
    r = gate_swap_legal(_two_day_slots(), 0, 10, 1, 20, {1: {0}})
    assert r["ok"] is True


def test_swap_tightening_takes_effect_immediately():
    slots = _two_day_slots()
    assert gate_swap_legal(slots, 0, 10, 1, 20, {}).get("ok") is True
    # 同一周表、同一对调，现行忌日收紧后立即被拦
    r = gate_swap_legal(slots, 0, 10, 1, 20, {1: {1}, 2: {0}})
    assert r["ok"] is False and r["reason"] == "memorial_blocked"
