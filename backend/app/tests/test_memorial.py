"""忌日空档回归：生成钉快照派格、对调吃现行忌日、快照不回刷、全员忌日整次失败。"""

import pytest

from app.db import connect
from app.engines.rota import build_week_slots, AllMembersUnavailableError
from app.engines import swap_gate
from app.modules.memorial import store as memorial_store
from app.modules.memorial.validation import MemorialDayError, normalize_days


def _clean_member_ids(c):
    return [r["id"] for r in c.execute(
        "SELECT id FROM members WHERE active=1 AND data_quality='clean' ORDER BY id")]


# ---------- 编排引擎 ----------

def test_slots_skip_unavailable_member_days():
    slots = build_week_slots([1, 2], [10], days=3, unavailable={1: {0, 2}})
    assert [s["member_id"] for s in slots] == [2, 1, 2]
    assert all(not (s["member_id"] == 1 and s["day"] in (0, 2)) for s in slots)


def test_slots_without_memorial_match_plain_round_robin():
    assert build_week_slots([1, 2, 3], [10, 20], days=7) == \
        build_week_slots([1, 2, 3], [10, 20], days=7, unavailable={})


def test_slots_all_unavailable_raises():
    with pytest.raises(AllMembersUnavailableError) as ei:
        build_week_slots([1, 2], [10], days=1, unavailable={1: {0}, 2: {0}})
    assert ei.value.day == 0 and ei.value.reason == "all_unavailable"


# ---------- 忌日集合校验 ----------

def test_normalize_days_sorts_and_dedups():
    assert normalize_days([3, 1, 1, 0]) == [0, 1, 3]
    assert normalize_days(None) == []


@pytest.mark.parametrize("bad", [[7], [-1], [1.5], [True], ["1"], "1", 3])
def test_normalize_days_rejects_bad_input(bad):
    with pytest.raises(MemorialDayError):
        normalize_days(bad)


# ---------- 现行忌日读口 / 快照 ----------

def test_current_memorial_reads_live_days(c):
    mids = _clean_member_ids(c)
    assert memorial_store.current_memorial(c) == {}
    memorial_store.set_member_memorial(c, mids[0], [1, 3])
    assert memorial_store.current_memorial(c) == {mids[0]: {1, 3}}
    assert memorial_store.current_memorial(c, [mids[1]]) == {}
    assert memorial_store.current_memorial(c, mids) == {mids[0]: {1, 3}}
    # 清空后从读口消失
    memorial_store.set_member_memorial(c, mids[0], [])
    assert memorial_store.current_memorial(c) == {}


def test_snapshot_pinned_not_rewritten_by_live_edits(c):
    mids = _clean_member_ids(c)
    memorial_store.set_member_memorial(c, mids[0], [2])
    snap = memorial_store.build_snapshot(c, mids)
    assert snap == {str(mids[0]): [2]}
    memorial_store.save_week_snapshot(c, 1, snap)
    # 收紧 / 新增现行忌日不得回刷已生成周的快照
    memorial_store.set_member_memorial(c, mids[0], [2, 4])
    memorial_store.set_member_memorial(c, mids[1], [0])
    assert memorial_store.week_snapshot_json(c, 1) == {str(mids[0]): [2]}
    assert memorial_store.load_week_snapshot(c, 1) == {mids[0]: {2}}


def test_set_member_memorial_validates_and_404(c):
    with pytest.raises(MemorialDayError):
        memorial_store.set_member_memorial(c, 1, [7])
    with pytest.raises(LookupError):
        memorial_store.set_member_memorial(c, 999, [1])


# ---------- 对调门禁 ----------

SLOTS = [
    {"day": 0, "task_id": 10, "member_id": 1},
    {"day": 1, "task_id": 10, "member_id": 2},
]


def test_swap_into_memorial_day_blocked():
    r = swap_gate.swap_legal(SLOTS, 0, 10, 1, 10, unavailable={1: {1}})
    assert r["ok"] is False and r["reason"] == "memorial_blocked" and r["member_id"] == 1


def test_swap_out_of_memorial_day_allowed():
    # 只检查被移动成员的目标格：移出忌日格不拦
    r = swap_gate.swap_legal(SLOTS, 0, 10, 1, 10, unavailable={1: {0}})
    assert r["ok"] is True


def test_apply_swap_blocked_raises_without_mutating():
    before = [dict(s) for s in SLOTS]
    with pytest.raises(ValueError):
        swap_gate.apply_swap(SLOTS, 0, 10, 1, 10, unavailable={2: {0}})
    assert SLOTS == before


# ---------- 端点接线（需 fastapi 环境，缺失时跳过） ----------

@pytest.fixture()
def api():
    return pytest.importorskip("app.main")


def _two_swappable_slots(board):
    by_member = {}
    for a in board["assignments"]:
        by_member.setdefault(a["member_id"], []).append(a)
    (m1, s1), (m2, s2) = list(by_member.items())[:2]
    sa = s1[0]
    sb = next(s for s in s2 if s["day"] != sa["day"])
    return (m1, sa), (m2, sb)


def test_generate_honours_current_memorial(tmp_db, api):
    c = connect(); mids = _clean_member_ids(c); c.close()
    api.put_member_memorial(mids[0], api.MemorialBody(days=[0]))
    out = api.generate(1, api.GenBody())
    assert out["memorial_snapshot"] == {str(mids[0]): [0]}
    assert all(not (s["member_id"] == mids[0] and s["day"] == 0) for s in out["slots"])
    board = api.week_board(1)
    assert board["memorial_snapshot"] == {str(mids[0]): [0]}
    assert all(not (a["member_id"] == mids[0] and a["day"] == 0) for a in board["assignments"])


def test_generate_all_unavailable_fails_and_keeps_board(tmp_db, api):
    api.generate(1, api.GenBody())
    before = api.week_board(1)["assignments"]
    c = connect(); mids = _clean_member_ids(c); c.close()
    for m in mids:
        api.put_member_memorial(m, api.MemorialBody(days=[0]))
    with pytest.raises(api.HTTPException) as ei:
        api.generate(1, api.GenBody(days=1))
    assert ei.value.status_code == 400 and ei.value.detail == "all_unavailable"
    assert api.week_board(1)["assignments"] == before


def test_live_memorial_edit_does_not_rewrite_generated_week(tmp_db, api):
    c = connect(); mids = _clean_member_ids(c); c.close()
    api.put_member_memorial(mids[0], api.MemorialBody(days=[2]))
    api.generate(1, api.GenBody())
    api.put_member_memorial(mids[0], api.MemorialBody(days=[2, 4]))
    api.put_member_memorial(mids[1], api.MemorialBody(days=[2]))
    assert api.week_board(1)["memorial_snapshot"] == {str(mids[0]): [2]}


def test_put_memorial_rejects_out_of_range_without_writing(tmp_db, api):
    with pytest.raises(api.HTTPException) as ei:
        api.put_member_memorial(1, api.MemorialBody(days=[7]))
    assert ei.value.status_code == 400
    c = connect()
    assert c.execute("SELECT memorial_days FROM members WHERE id=1").fetchone()["memorial_days"] is None
    c.close()
    with pytest.raises(api.HTTPException) as ei2:
        api.put_member_memorial(999, api.MemorialBody(days=[1]))
    assert ei2.value.status_code == 404


def test_swap_request_blocked_by_live_memorial(tmp_db, api):
    api.generate(1, api.GenBody())
    (m1, sa), (m2, sb) = _two_swappable_slots(api.week_board(1))
    api.put_member_memorial(m1, api.MemorialBody(days=[sb["day"]]))
    with pytest.raises(api.HTTPException) as ei:
        api.request_swap(1, api.SwapBody(a_day=sa["day"], a_task=sa["task_id"],
                                         b_day=sb["day"], b_task=sb["task_id"]))
    assert ei.value.status_code == 400 and ei.value.detail == "memorial_blocked"
    assert api.list_swaps() == []


def test_swap_confirm_recalled_when_memorial_tightened(tmp_db, api):
    api.generate(1, api.GenBody())
    board = api.week_board(1)
    (m1, sa), (m2, sb) = _two_swappable_slots(board)
    r = api.request_swap(1, api.SwapBody(a_day=sa["day"], a_task=sa["task_id"],
                                         b_day=sb["day"], b_task=sb["task_id"]))
    assert r["ok"] is True
    # 申请后收紧忌日，确认时仍须被拦且看板不动
    api.put_member_memorial(m1, api.MemorialBody(days=[sb["day"]]))
    with pytest.raises(api.HTTPException) as ei:
        api.confirm_swap(r["id"])
    assert ei.value.status_code == 400 and ei.value.detail == "memorial_blocked"
    after = {(a["day"], a["task_id"]): a["member_id"] for a in api.week_board(1)["assignments"]}
    assert after == {(a["day"], a["task_id"]): a["member_id"] for a in board["assignments"]}


def test_swap_without_memorial_conflict_confirms(tmp_db, api):
    api.generate(1, api.GenBody())
    (m1, sa), (m2, sb) = _two_swappable_slots(api.week_board(1))
    r = api.request_swap(1, api.SwapBody(a_day=sa["day"], a_task=sa["task_id"],
                                         b_day=sb["day"], b_task=sb["task_id"]))
    assert api.confirm_swap(r["id"])["ok"] is True
    after = {(a["day"], a["task_id"]): a["member_id"] for a in api.week_board(1)["assignments"]}
    assert after[(sa["day"], sa["task_id"])] == m2
    assert after[(sb["day"], sb["task_id"])] == m1
