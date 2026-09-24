from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import HangRail, RailPlacement, Store, WorkOrder


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False)
    db = TestingSession()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield db
    app.dependency_overrides.clear()
    db.close()


@pytest.fixture()
def client(db_session):
    return TestClient(app)


def _make_order(db, store_id, ticket, length_cm=20):
    o = WorkOrder(
        store_id=store_id,
        ticket_code=ticket,
        garment_name=ticket,
        length_cm=length_cm,
        status="hung",
        due_at=datetime.utcnow(),
    )
    db.add(o)
    db.flush()
    return o


def _placements(db, rail_id):
    rows = db.scalars(
        select(RailPlacement)
        .where(RailPlacement.rail_id == rail_id, RailPlacement.active == 1)
        .order_by(RailPlacement.start_cm)
    ).all()
    return [(r.order_id, r.start_cm, r.end_cm) for r in rows]


def test_compact_endpoint_fills_gap(db_session, client):
    store = Store(name="本店")
    db_session.add(store)
    db_session.flush()
    rail = HangRail(store_id=store.id, label="R1", length_cm=100)
    other = HangRail(store_id=store.id, label="R2", length_cm=100)
    db_session.add_all([rail, other])
    db_session.flush()
    o1 = _make_order(db_session, store.id, "T1", 20)
    o2 = _make_order(db_session, store.id, "T2", 25)
    o3 = _make_order(db_session, store.id, "T3", 10)
    db_session.add_all(
        [
            RailPlacement(rail_id=rail.id, order_id=o1.id, start_cm=0, end_cm=20),
            RailPlacement(rail_id=rail.id, order_id=o2.id, start_cm=30, end_cm=55),
            RailPlacement(rail_id=rail.id, order_id=o3.id, start_cm=70, end_cm=80),
        ]
    )
    # same store, other rail: must stay untouched
    x = _make_order(db_session, store.id, "TX", 20)
    db_session.add(RailPlacement(rail_id=other.id, order_id=x.id, start_cm=10, end_cm=30))
    # other store: must stay untouched
    other_store = Store(name="它店")
    db_session.add(other_store)
    db_session.flush()
    foreign_rail = HangRail(store_id=other_store.id, label="F1", length_cm=100)
    db_session.add(foreign_rail)
    db_session.flush()
    fo = _make_order(db_session, other_store.id, "TF", 10)
    db_session.add(
        RailPlacement(rail_id=foreign_rail.id, order_id=fo.id, start_cm=5, end_cm=15)
    )
    db_session.commit()

    res = client.post(f"/api/rails/{rail.id}/compact")
    assert res.status_code == 200, res.text
    data = res.json()

    # middle gap filled, ruler continuous, no overlap, within rail length
    spans = [(s["start_cm"], s["end_cm"]) for s in data["segments"]]
    assert spans == [(0.0, 20.0), (20.0, 45.0), (45.0, 55.0)]
    # ticket set and relative order preserved
    assert [s["ticket_code"] for s in data["segments"]] == ["T1", "T2", "T3"]

    db_session.expire_all()
    assert _placements(db_session, rail.id) == [
        (o1.id, 0.0, 20.0),
        (o2.id, 20.0, 45.0),
        (o3.id, 45.0, 55.0),
    ]
    # other rail / other store untouched
    assert _placements(db_session, other.id) == [(x.id, 10.0, 30.0)]
    assert _placements(db_session, foreign_rail.id) == [(fo.id, 5.0, 15.0)]


def test_compact_endpoint_rolls_back_on_failure(db_session, client):
    store = Store(name="本店")
    db_session.add(store)
    db_session.flush()
    rail = HangRail(store_id=store.id, label="R1", length_cm=100)
    db_session.add(rail)
    db_session.flush()
    o1 = _make_order(db_session, store.id, "T1", 30)
    o2 = _make_order(db_session, store.id, "T2", 20)
    # corrupt, overlapping state written directly to the DB
    db_session.add_all(
        [
            RailPlacement(rail_id=rail.id, order_id=o1.id, start_cm=0, end_cm=30),
            RailPlacement(rail_id=rail.id, order_id=o2.id, start_cm=20, end_cm=40),
        ]
    )
    db_session.commit()

    res = client.post(f"/api/rails/{rail.id}/compact")
    assert res.status_code == 409

    db_session.expire_all()
    # whole rail rolled back to pre-compact spans
    assert set(_placements(db_session, rail.id)) == {
        (o1.id, 0.0, 30.0),
        (o2.id, 20.0, 40.0),
    }


def test_compact_endpoint_missing_rail(client):
    res = client.post("/api/rails/999/compact")
    assert res.status_code == 404
