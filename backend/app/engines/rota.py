"""Round-robin weekly chore assignments + swap legality."""


class AllMembersUnavailableError(Exception):
    """某 day 全部活跃 clean 成员均忌日，整次生成必须放弃。"""

    def __init__(self, day: int):
        super().__init__("all_unavailable")
        self.day = day
        self.reason = "all_unavailable"


def build_week_slots(
    member_ids: list[int],
    task_ids: list[int],
    days: int = 7,
    unavailable: dict | None = None,
) -> list[dict]:
    """按 task→day 顺序 round-robin 落位。

    unavailable: {member_id: set(day)}，命中忌日的成员不得出现在该 day
    的任何格子；指针相位继续前进，改由其后第一位可用的活跃成员承接。
    无忌日时格位与原 round-robin 完全一致。
    某 day 全员忌日抛 AllMembersUnavailableError（不产生部分结果）。
    """
    if not member_ids or not task_ids:
        return []
    blocked = {mid: set(ds) for mid, ds in (unavailable or {}).items() if ds}
    n = len(member_ids)
    slots = []
    idx = 0
    for day in range(days):
        for tid in task_ids:
            tried = 0
            while day in blocked.get(member_ids[idx % n], ()):
                idx += 1
                tried += 1
                if tried >= n:
                    raise AllMembersUnavailableError(day)
            mid = member_ids[idx % n]
            slots.append({"day": day, "task_id": tid, "member_id": mid})
            idx += 1
    return slots


def swap_legal(slots: list[dict], a_day: int, a_task: int, b_day: int, b_task: int) -> dict:
    """Two slots may swap only if both exist, different assignees, same week grid."""
    def find(day, task):
        for s in slots:
            if s["day"] == day and s["task_id"] == task:
                return s
        return None
    sa, sb = find(a_day, a_task), find(b_day, b_task)
    if sa is None or sb is None:
        return {"ok": False, "reason": "slot_missing"}
    if sa["member_id"] == sb["member_id"]:
        return {"ok": False, "reason": "same_assignee"}
    if a_day == b_day and a_task == b_task:
        return {"ok": False, "reason": "same_slot"}
    return {
        "ok": True,
        "reason": "",
        "a_member": sa["member_id"],
        "b_member": sb["member_id"],
    }


def apply_swap(slots: list[dict], a_day: int, a_task: int, b_day: int, b_task: int) -> list[dict]:
    check = swap_legal(slots, a_day, a_task, b_day, b_task)
    if not check["ok"]:
        raise ValueError(check["reason"])
    out = [dict(s) for s in slots]
    ia = next(i for i, s in enumerate(out) if s["day"] == a_day and s["task_id"] == a_task)
    ib = next(i for i, s in enumerate(out) if s["day"] == b_day and s["task_id"] == b_task)
    out[ia]["member_id"], out[ib]["member_id"] = out[ib]["member_id"], out[ia]["member_id"]
    return out
