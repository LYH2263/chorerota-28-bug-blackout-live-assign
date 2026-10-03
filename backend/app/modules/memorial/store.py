"""忌日落库：成员现行忌日、当周忌日快照、周表整表替换。

成员现行忌日写 members.memorial_days（JSON 文本）；
生成时把当时的忌日集合快照写入 weeks.memorial_snapshot，
此后只改现行忌日不会回刷已生成周。
"""

import json

from app.modules.memorial.validation import normalize_days


def _decode(raw) -> list[int]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    return [int(d) for d in data] if isinstance(data, list) else []


def get_member_memorial(c, member_id: int) -> list[int]:
    row = c.execute("SELECT memorial_days FROM members WHERE id=?", (member_id,)).fetchone()
    if row is None:
        return []
    return _decode(row["memorial_days"])


def member_exists(c, member_id: int) -> bool:
    return c.execute("SELECT 1 FROM members WHERE id=?", (member_id,)).fetchone() is not None


def set_member_memorial(c, member_id: int, days) -> list[int]:
    """先校验后写：越界 / 非整数抛 MemorialDayError，不动成员档。

    返回规整后的 day 列表。成员不存在抛 LookupError。
    """
    norm = normalize_days(days)
    if not member_exists(c, member_id):
        raise LookupError("member_not_found")
    c.execute(
        "UPDATE members SET memorial_days=? WHERE id=?",
        (json.dumps(norm) if norm else None, member_id),
    )
    return norm


def current_memorial(c, member_ids=None):
    """现行忌日读口：{member_id: set(day)}，仅含非空集合。

    member_ids 为 None 时读全体成员，否则只读给定成员。
    读的是 members 表现行值，与已生成周的快照无关。
    """
    if member_ids is None:
        rows = c.execute("SELECT id, memorial_days FROM members").fetchall()
    else:
        ids = [int(m) for m in member_ids]
        if not ids:
            return {}
        marks = ",".join("?" for _ in ids)
        rows = c.execute(
            f"SELECT id, memorial_days FROM members WHERE id IN ({marks})", ids
        ).fetchall()
    out: dict[int, set[int]] = {}
    for r in rows:
        days = _decode(r["memorial_days"])
        if days:
            out[r["id"]] = set(days)
    return out


def build_snapshot(c, member_ids) -> dict:
    """生成时的忌日快照：{member_id(str): [sorted days]}，仅含非空集合。"""
    current = current_memorial(c, member_ids)
    return {str(mid): sorted(days) for mid, days in current.items()}


def save_week_snapshot(c, week_id: int, snapshot: dict) -> None:
    c.execute("UPDATE weeks SET memorial_snapshot=? WHERE id=?",
              (json.dumps(snapshot, sort_keys=True) if snapshot else None, week_id))


def load_week_snapshot(c, week_id: int) -> dict:
    """读当周快照 → {member_id(int): set(day)}。"""
    row = c.execute("SELECT memorial_snapshot FROM weeks WHERE id=?", (week_id,)).fetchone()
    if row is None or not row["memorial_snapshot"]:
        return {}
    try:
        data = json.loads(row["memorial_snapshot"])
    except (ValueError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {int(mid): set(days) for mid, days in data.items() if isinstance(days, list)}


def week_snapshot_json(c, week_id: int):
    """给看板/回包用的原始快照 dict（字符串键、有序 day 列表）。"""
    row = c.execute("SELECT memorial_snapshot FROM weeks WHERE id=?", (week_id,)).fetchone()
    if row is None or not row["memorial_snapshot"]:
        return {}
    try:
        data = json.loads(row["memorial_snapshot"])
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def replace_week_assignments(c, week_id: int, slots: list[dict]) -> None:
    """整表替换该周格位（调用方与快照/状态更新同一事务提交）。"""
    c.execute("DELETE FROM assignments WHERE week_id=?", (week_id,))
    c.executemany(
        "INSERT INTO assignments(week_id,day,task_id,member_id) VALUES (?,?,?,?)",
        [(week_id, s["day"], s["task_id"], s["member_id"]) for s in slots],
    )
