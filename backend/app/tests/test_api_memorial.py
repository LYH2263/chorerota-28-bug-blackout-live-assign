"""忌日端到端：成员档 → 生成 / 对调 → 看板回包，语义前后端一致。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client(tmp_db):
    with TestClient(app) as c:
        yield c


def _set_memorial(client, member_id, days):
    return client.put(f"/api/members/{member_id}/memorial", json={"days": days})


def _board(client, week_id=1):
    return client.get(f"/api/weeks/{week_id}/board").json()


# ---------- 越界拒存 ----------

def test_out_of_range_memorial_rejected_and_not_persisted(client):
    r = _set_memorial(client, 1, [7])
    assert r.status_code == 400 and r.json()["detail"] == "memorial_day_out_of_range"
    r = _set_memorial(client, 1, [1.5])
    assert r.status_code == 400 and r.json()["detail"] == "memorial_day_must_be_int"
    members = {m["id"]: m["memorial_days"] for m in client.get("/api/members").json()}
    assert members[1] == []


# ---------- 生成按现行忌日派格 ----------

def test_generate_keeps_member_off_memorial_day(client):
    _set_memorial(client, 1, [0])
    r = client.post("/api/weeks/1/generate", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["memorial_snapshot"] == {"1": [0]}
    assert all(not (s["day"] == 0 and s["member_id"] == 1) for s in body["slots"])

    board = _board(client)
    assert board["memorial_snapshot"] == {"1": [0]}
    assert all(not (a["day"] == 0 and a["member_id"] == 1) for a in board["assignments"])


def test_generated_week_pinned_when_current_memorial_changes(client):
    _set_memorial(client, 1, [0])
    client.post("/api/weeks/1/generate", json={})
    before = _board(client)

    # 之后收紧/改日：只改现行忌日，不回刷已生成周的格位与快照
    _set_memorial(client, 1, [5])
    after = _board(client)
    assert after["memorial_snapshot"] == {"1": [0]}
    key = lambda b: sorted((a["day"], a["task_id"], a["member_id"]) for a in b["assignments"])
    assert key(after) == key(before)

    # 但对「新生成」立即生效
    r = client.post("/api/weeks/1/generate", json={})
    assert r.status_code == 200
    refreshed = _board(client)
    assert refreshed["memorial_snapshot"] == {"1": [5]}
    assert all(not (a["day"] == 5 and a["member_id"] == 1) for a in refreshed["assignments"])


def test_all_members_same_memorial_day_fails_and_keeps_old_grid(client):
    client.post("/api/weeks/1/generate", json={})
    old = _board(client)
    for mid in (1, 2, 3):
        _set_memorial(client, mid, [2])
    r = client.post("/api/weeks/1/generate", json={})
    assert r.status_code == 400 and r.json()["detail"] == "all_unavailable"

    kept = _board(client)
    key = lambda b: sorted((a["day"], a["task_id"], a["member_id"]) for a in b["assignments"])
    assert key(kept) == key(old)              # 原格位不动
    assert kept["week"]["status"] == "ready"  # 状态不回退
    assert kept["memorial_snapshot"] == {}    # 失败快照不写入


# ---------- 对调按现行忌日（收紧立即生效） ----------

def test_swap_request_blocked_by_tightened_memorial(client):
    client.post("/api/weeks/1/generate", json={})
    # (day0, task1)=成员1 ↔ (day1, task2)=成员2，会把成员1移入 day1
    _set_memorial(client, 1, [1])
    r = client.post("/api/weeks/1/swaps",
                    json={"a_day": 0, "a_task": 1, "b_day": 1, "b_task": 2})
    assert r.status_code == 400 and r.json()["detail"] == "memorial_blocked"
    assert client.get("/api/swaps").json() == []  # 拒绝不落成功行


def test_swap_confirm_rechecks_tightened_memorial(client):
    client.post("/api/weeks/1/generate", json={})
    payload = {"a_day": 0, "a_task": 1, "b_day": 1, "b_task": 2}
    sid = client.post("/api/weeks/1/swaps", json=payload).json()["id"]
    before = _board(client)

    # 申请受理后收紧忌日：确认必须再按现行忌日拦截，格位不变
    _set_memorial(client, 1, [1])
    r = client.post(f"/api/swaps/{sid}/confirm", json={})
    assert r.status_code == 400 and r.json()["detail"] == "memorial_blocked"
    key = lambda b: sorted((a["day"], a["task_id"], a["member_id"]) for a in b["assignments"])
    assert key(_board(client)) == key(before)

    # 放开后同一申请可确认，格位真正交换
    _set_memorial(client, 1, [])
    r = client.post(f"/api/swaps/{sid}/confirm", json={})
    assert r.status_code == 200
    a0t1 = next(a for a in _board(client)["assignments"] if a["day"] == 0 and a["task_id"] == 1)
    assert a0t1["member_id"] == 2


def test_legal_swap_without_memorial_still_succeeds(client):
    client.post("/api/weeks/1/generate", json={})
    r = client.post("/api/weeks/1/swaps",
                    json={"a_day": 0, "a_task": 1, "b_day": 1, "b_task": 2})
    assert r.status_code == 200
    sid = r.json()["id"]
    assert client.post(f"/api/swaps/{sid}/confirm", json={}).status_code == 200
