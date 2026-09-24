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


class CompactError(ValueError):
    """Raised when a rail cannot be compacted; callers must roll back."""


def compact(rail_length: float, occupied: list[Segment]) -> list[Placement]:
    """Left-pack segments in their original start order, gap-free.

    Returns one Placement per input segment, aligned with the segments sorted
    by (start, end). Garment lengths and relative order are preserved. Raises
    CompactError on invalid/overlapping/out-of-range input so the caller can
    roll the whole rail back to its pre-compact spans.
    """
    if rail_length <= 0:
        raise CompactError("挂杆长度无效")
    segs = sorted(occupied, key=lambda s: (s.start_cm, s.end_cm))
    for s in segs:
        if s.length <= 0:
            raise CompactError("占位长度无效")
        if s.start_cm < -1e-9 or s.end_cm > rail_length + 1e-9:
            raise CompactError("占位超出杆长，无法紧凑")
    for prev, cur in zip(segs, segs[1:]):
        if overlaps(prev, cur):
            raise CompactError("占位存在重叠，无法紧凑")
    placed: list[Placement] = []
    cursor = 0.0
    for s in segs:
        end = cursor + s.length
        if end > rail_length + 1e-9:
            raise CompactError("紧凑后超出杆长")
        placed.append(Placement(cursor, end))
        cursor = end
    return placed
