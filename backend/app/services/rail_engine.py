"""1D First-Fit placement by garment length on a hang rail."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    start_cm: float
    end_cm: float  # exclusive

    @property
    def length(self) -> float:
        return self.end_cm - self.start_cm


@dataclass(frozen=True)
class Placement:
    start_cm: float
    end_cm: float


class CompactError(ValueError):
    """紧凑重排校验失败：非法衣长、重叠或越出杆长。"""


def compact(rail_length: float, occupied: list[Segment]) -> list[Placement]:
    """将全部占位按原 start 排序后无间隙左移贴齐。

    保持相对次序、衣长（end-start）与票号集合不变；不产生重叠、
    不越出杆长。任一占位非法（衣长 <= 0、相互重叠、总长超杆长）则抛
    CompactError，由调用方整杆回滚到重排前起止。
    """
    ordered = sorted(occupied, key=lambda s: (s.start_cm, s.end_cm))
    result: list[Placement] = []
    cursor = 0.0
    prev: Segment | None = None
    for seg in ordered:
        length = seg.end_cm - seg.start_cm
        if length <= 0:
            raise CompactError(f"占位衣长非法: {seg.start_cm}-{seg.end_cm}")
        if prev is not None and seg.start_cm + 1e-9 < prev.end_cm:
            raise CompactError("重排前占位相互重叠，无法紧凑")
        end = cursor + length
        if end > rail_length + 1e-9:
            raise CompactError("占位总衣长超出杆长，无法紧凑")
        result.append(Placement(cursor, end))
        cursor = end
        prev = seg
    return result


def free_gaps(rail_length: float, occupied: list[Segment]) -> list[Segment]:
    occ = sorted(occupied, key=lambda s: s.start_cm)
    gaps: list[Segment] = []
    cursor = 0.0
    for seg in occ:
        if seg.start_cm > cursor:
            gaps.append(Segment(cursor, seg.start_cm))
        cursor = max(cursor, seg.end_cm)
    if cursor < rail_length:
        gaps.append(Segment(cursor, rail_length))
    return gaps


def first_fit(rail_length: float, occupied: list[Segment], garment_cm: float) -> Placement | None:
    if garment_cm <= 0 or garment_cm > rail_length:
        return None
    for gap in free_gaps(rail_length, occupied):
        if gap.length + 1e-9 >= garment_cm:
            return Placement(gap.start_cm, gap.start_cm + garment_cm)
    return None


def overlaps(a: Segment, b: Segment) -> bool:
    return not (a.end_cm <= b.start_cm or b.end_cm <= a.start_cm)
