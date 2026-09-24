"""紧凑重排 API 集成测试：中间挖空被填、次序与衣长不变、票号集合不变、
失败整杆回滚、不影响其它杆或其它店。"""

from datetime import datetime, timedelta

from app.models.models import HangRail, RailPlacement, Store, WorkOrder


def _make_store_rail(db, label="A 杆", length=200.0, store_name="测试店"):
    store = Store(name=store_name)
    db.add(store)
    db.flush()
    rail = HangRail(store_id=store.id, label=label, length_cm=length)
    db.add(rail)
    db.flush()
    return store, rail


def _hung_order(db, store, ticket, name, length):
    order = WorkOrder(
        store_id=store.id,
        ticket_code=ticket,
        garment_name=name,
        length_cm=length,
        status="hung",
        due_at=datetime.utcnow() + timedelta(days=1),
        hung_at=datetime.utcnow(),
    )
    db.add(order)
    db.flush()
    return order


def _place(db, rail, order, start, end, active=1):
    p = RailPlacement(
        rail_id=rail.id, order_id=order.id, start_cm=start, end_cm=end, active=active
    )
    db.add(p)
    db.flush()
    return p


def test_compact_fills_middle_gap(client, db_session):
    store, rail = _make_store_rail(db_session, length=200.0)
    o1 = _hung_order(db_session, store, "T-1", "大衣", 10)
    o2 = _hung_order(db_session, store, "T-2", "西装", 10)
    o3 = _hung_order(db_session, store, "T-3", "风衣", 15)
    _place(db_session, rail, o1, 0, 10)
    _place(db_session, rail, o2, 40, 50)   # 中间空洞 10-40
    _place(db_session, rail, o3, 80, 95)
    db_session.commit()

    res = client.post(f"/api/rails/{rail.id}/compact")
    assert res.status_code == 200
    data = res.json()
    starts = [s["start_cm"] for s in data["segments"]]
    ends = [s["end_cm"] for s in data["segments"]]
    # 无间隙左移贴齐，尺线连续
    assert list(zip(starts, ends)) == [(0.0, 10.0), (10.0, 20.0), (20.0, 35.0)]


def test_compact_preserves_order_length_and_tickets(client, db_session):
    store, rail = _make_store_rail(db_session, length=100.0)
    # 故意按非 start 顺序插入，验证按原 start 排序后次序不变
    o_big = _hung_order(db_session, store, "T-BIG", "羽绒服", 30)
    o_mid = _hung_order(db_session, store, "T-MID", "西装", 25)
    o_small = _hung_order(db_session, store, "T-SML", "衬衫", 20)
    _place(db_session, rail, o_big, 60, 90)
    _place(db_session, rail, o_small, 0, 20)
    _place(db_session, rail, o_mid, 30, 55)
    db_session.commit()

    res = client.post(f"/api/rails/{rail.id}/compact")
    assert res.status_code == 200
    segs = res.json()["segments"]
    # 相对次序按原 start：衬衫 → 西装 → 羽绒服；衣长不变
    assert [s["ticket_code"] for s in segs] == ["T-SML", "T-MID", "T-BIG"]
    assert [s["end_cm"] - s["start_cm"] for s in segs] == [20.0, 25.0, 30.0]
    # 票号集合不变
    assert {s["ticket_code"] for s in segs} == {"T-SML", "T-MID", "T-BIG"}
    # 无重叠、无空洞
    for prev, cur in zip(segs, segs[1:]):
        assert cur["start_cm"] == prev["end_cm"]


def test_compact_failure_rolls_back_whole_rail(client, db_session):
    store, rail = _make_store_rail(db_session, length=90.0)
    o1 = _hung_order(db_session, store, "T-1", "甲", 50)
    o2 = _hung_order(db_session, store, "T-2", "乙", 50)
    # 脏数据：两段不重叠但总衣长 100 > 杆长 90
    p1 = _place(db_session, rail, o1, 0, 50)
    p2 = _place(db_session, rail, o2, 50, 100)
    db_session.commit()

    res = client.post(f"/api/rails/{rail.id}/compact")
    assert res.status_code == 409

    db_session.expire_all()
    rows = (
        db_session.query(RailPlacement)
        .filter(RailPlacement.rail_id == rail.id, RailPlacement.active == 1)
        .order_by(RailPlacement.id)
        .all()
    )
    # 整杆回滚到重排前起止
    assert [(r.start_cm, r.end_cm) for r in rows] == [(0.0, 50.0), (50.0, 100.0)]
    assert rows[0].id == p1.id and rows[1].id == p2.id


def test_compact_does_not_touch_other_rails_or_stores(client, db_session):
    s1, r1 = _make_store_rail(db_session, label="甲店 A 杆", length=200.0, store_name="甲店")
    o = _hung_order(db_session, s1, "T-1", "大衣", 30)
    _place(db_session, r1, o, 50, 80)

    # 同店另一杆
    r1b = HangRail(store_id=s1.id, label="甲店 B 杆", length_cm=160.0)
    db_session.add(r1b)
    db_session.flush()
    ob = _hung_order(db_session, s1, "T-B", "西装", 20)
    pb = _place(db_session, r1b, ob, 70, 90)

    # 其它店的杆
    s2, r2 = _make_store_rail(db_session, label="乙店 A 杆", length=200.0, store_name="乙店")
    o2 = _hung_order(db_session, s2, "T-2", "风衣", 25)
    p2 = _place(db_session, r2, o2, 90, 115)
    db_session.commit()

    res = client.post(f"/api/rails/{r1.id}/compact")
    assert res.status_code == 200

    db_session.expire_all()
    untouched_b = db_session.get(RailPlacement, pb.id)
    untouched_2 = db_session.get(RailPlacement, p2.id)
    # 其它杆、其它店起止原样不变
    assert (untouched_b.start_cm, untouched_b.end_cm) == (70.0, 90.0)
    assert (untouched_2.start_cm, untouched_2.end_cm) == (90.0, 115.0)


def test_compact_ignores_inactive_placements(client, db_session):
    store, rail = _make_store_rail(db_session, length=100.0)
    o1 = _hung_order(db_session, store, "T-1", "大衣", 30)
    o2 = _hung_order(db_session, store, "T-2", "西装", 20)
    active = _place(db_session, rail, o1, 60, 90)
    picked = _place(db_session, rail, o2, 0, 20, active=0)  # 已取件释放
    db_session.commit()

    res = client.post(f"/api/rails/{rail.id}/compact")
    assert res.status_code == 200
    assert [s["ticket_code"] for s in res.json()["segments"]] == ["T-1"]

    db_session.expire_all()
    still_inactive = db_session.get(RailPlacement, picked.id)
    assert still_inactive.active == 0
    assert (still_inactive.start_cm, still_inactive.end_cm) == (0.0, 20.0)
    moved = db_session.get(RailPlacement, active.id)
    assert (moved.start_cm, moved.end_cm) == (0.0, 30.0)


def test_compact_unknown_rail_404(client):
    res = client.post("/api/rails/9999/compact")
    assert res.status_code == 404
