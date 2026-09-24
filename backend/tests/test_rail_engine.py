import pytest

from app.services.rail_engine import (
    CompactError,
    Placement,
    Segment,
    compact,
    first_fit,
    free_gaps,
)


def test_first_fit_leftmost():
    occ = [Segment(20, 40)]
    p = first_fit(100, occ, 15)
    assert p is not None
    assert p.start_cm == 0
    assert p.end_cm == 15


def test_first_fit_skips_too_small_gap():
    occ = [Segment(0, 10), Segment(18, 50)]
    p = first_fit(100, occ, 10)
    assert p is not None
    assert p.start_cm == 50


def test_no_space():
    occ = [Segment(0, 80)]
    assert first_fit(100, occ, 25) is None


def test_free_gaps_edges():
    gaps = free_gaps(50, [Segment(10, 20), Segment(30, 35)])
    assert gaps == [Segment(0, 10), Segment(20, 30), Segment(35, 50)]


def test_compact_fills_middle_gap():
    packed = compact(100, [Segment(0, 20), Segment(30, 55), Segment(70, 80)])
    assert packed == [Placement(0, 20), Placement(20, 45), Placement(45, 55)]


def test_compact_preserves_order_and_lengths():
    segs = [Segment(10, 25), Segment(0, 5), Segment(40, 45)]
    packed = compact(100, segs)
    # sorted by start: len 5, 15, 5 — lengths and relative order unchanged
    assert [(p.start_cm, p.end_cm) for p in packed] == [(0, 5), (5, 20), (20, 25)]


def test_compact_noop_when_already_tight():
    packed = compact(50, [Segment(0, 10), Segment(10, 30)])
    assert packed == [Placement(0, 10), Placement(10, 30)]


def test_compact_empty_rail():
    assert compact(100, []) == []


def test_compact_rejects_overlap():
    with pytest.raises(CompactError):
        compact(100, [Segment(0, 30), Segment(20, 40)])


def test_compact_rejects_out_of_range():
    with pytest.raises(CompactError):
        compact(50, [Segment(40, 60)])


def test_compact_rejects_invalid_segment():
    with pytest.raises(CompactError):
        compact(100, [Segment(30, 20)])
