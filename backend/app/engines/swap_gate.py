"""对调门禁：在 engines.rota 的纯对调规则之上叠加现行忌日检查。

门禁按「现行忌日」判定（不是生成当周的快照）：忌日收紧后，
即使老周表/老申请是在收紧前产生的，新对调把某人派进其忌日格
仍须失败。只检查被移动成员的目标格（移出忌日格不拦）。
"""

from app.engines.rota import swap_legal as _rota_swap_legal


def memorial_block(
    slots: list[dict],
    a_day: int,
    a_task: int,
    b_day: int,
    b_task: int,
    unavailable: dict | None,
) -> dict:
    """返回 {"blocked": bool, "reason": str, "member_id": int|None}。"""
    blocked = unavailable or {}

    def find(day, task):
        for s in slots:
            if s["day"] == day and s["task_id"] == task:
                return s
        return None

    sa, sb = find(a_day, a_task), find(b_day, b_task)
    if sa is None or sb is None:
        return {"blocked": False, "reason": "", "member_id": None}
    # A 格原占用人会被派到 b_day；B 格原占用人会被派到 a_day
    if b_day in blocked.get(sa["member_id"], ()):
        return {"blocked": True, "reason": "memorial_blocked", "member_id": sa["member_id"]}
    if a_day in blocked.get(sb["member_id"], ()):
        return {"blocked": True, "reason": "memorial_blocked", "member_id": sb["member_id"]}
    return {"blocked": False, "reason": "", "member_id": None}


def swap_legal(
    slots: list[dict],
    a_day: int,
    a_task: int,
    b_day: int,
    b_task: int,
    unavailable: dict | None = None,
) -> dict:
    """基础对调规则 + 现行忌日门禁。"""
    check = _rota_swap_legal(slots, a_day, a_task, b_day, b_task)
    if not check["ok"]:
        return check
    gate = memorial_block(slots, a_day, a_task, b_day, b_task, unavailable)
    if gate["blocked"]:
        return {"ok": False, "reason": gate["reason"], "member_id": gate["member_id"]}
    return check


def apply_swap(
    slots: list[dict],
    a_day: int,
    a_task: int,
    b_day: int,
    b_task: int,
    unavailable: dict | None = None,
) -> list[dict]:
    """过门禁后执行对调；任一不过抛 ValueError(reason)，不改入参。"""
    check = swap_legal(slots, a_day, a_task, b_day, b_task, unavailable)
    if not check["ok"]:
        raise ValueError(check["reason"])
    out = [dict(s) for s in slots]
    ia = next(i for i, s in enumerate(out) if s["day"] == a_day and s["task_id"] == a_task)
    ib = next(i for i, s in enumerate(out) if s["day"] == b_day and s["task_id"] == b_task)
    out[ia]["member_id"], out[ib]["member_id"] = out[ib]["member_id"], out[ia]["member_id"]
    return out
