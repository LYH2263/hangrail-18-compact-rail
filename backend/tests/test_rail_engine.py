import pytest

from app.services.rail_engine import CompactError, Placement, Segment, compact, first_fit, free_gaps


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


# —— 紧凑重排 ——

def test_compact_fills_middle_gap():
    # 中间被取件挖空：0-10、40-50、80-95 → 左移贴齐，空洞消失
    occ = [Segment(0, 10), Segment(40, 50), Segment(80, 95)]
    result = compact(200, occ)
    assert result == [Placement(0, 10), Placement(10, 20), Placement(20, 35)]
    # 尺线连续无空洞，尾部留空
    assert result[0].start_cm == 0
    assert result[-1].end_cm == 35


def test_compact_preserves_order_and_length():
    # 相对次序（按原 start）与衣长不变
    occ = [Segment(60, 90), Segment(0, 20), Segment(30, 55)]
    result = compact(100, occ)
    lengths = [p.end_cm - p.start_cm for p in result]
    assert lengths == [20, 25, 30]
    # 票号集合语义：输入乱序给出，结果仍按原 start 排序
    assert result == [Placement(0, 20), Placement(20, 45), Placement(45, 75)]


def test_compact_already_packed_is_noop():
    occ = [Segment(0, 30), Segment(30, 60)]
    result = compact(100, occ)
    assert result == [Placement(0, 30), Placement(30, 60)]


def test_compact_empty_rail():
    assert compact(100, []) == []


def test_compact_rejects_overlap():
    # 重排前数据已相互重叠（脏数据），拒绝紧凑
    occ = [Segment(0, 30), Segment(20, 50)]
    with pytest.raises(CompactError):
        compact(100, occ)


def test_compact_rejects_overflow():
    # 总衣长超出杆长，拒绝（段间不重叠）
    occ = [Segment(0, 50), Segment(50, 100)]
    with pytest.raises(CompactError):
        compact(90, occ)


def test_compact_rejects_nonpositive_length():
    with pytest.raises(CompactError):
        compact(100, [Segment(10, 10)])
