"""忌日集合校验。

成员可在成员详情登记一周内若干 day 为忌日（0..6）。
越界、非整数一律拒绝，由调用方保证不写成员档。
"""

WEEK_DAYS = 7


class MemorialDayError(ValueError):
    """忌日 day 非法（越界 / 非整数）。"""


def normalize_days(days, week_days: int = WEEK_DAYS) -> list[int]:
    """把入参规整为去重排序的 day 列表。

    - 只接受 int（bool 虽是 int 子类，按非整数拒绝）
    - day 必须落在 0..week_days-1，否则 MemorialDayError
    """
    if days is None:
        return []
    if isinstance(days, (str, bytes)) or not isinstance(days, (list, tuple, set)):
        raise MemorialDayError("memorial_days_must_be_list")
    out: set[int] = set()
    for d in days:
        if isinstance(d, bool) or not isinstance(d, int):
            raise MemorialDayError("memorial_day_must_be_int")
        if d < 0 or d >= week_days:
            raise MemorialDayError("memorial_day_out_of_range")
        out.add(d)
    return sorted(out)


def unavailable_map(memorial_by_member: dict, week_days: int = WEEK_DAYS) -> dict:
    """{member_id: [days]} 原始数据 → 校验后的 {member_id: set(day)}，忽略空集合。"""
    result: dict[int, set[int]] = {}
    for mid, days in (memorial_by_member or {}).items():
        norm = normalize_days(days, week_days)
        if norm:
            result[int(mid)] = set(norm)
    return result
