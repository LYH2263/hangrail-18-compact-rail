"""API 集成测试夹具：sqlite 内存库 + 依赖覆盖。

生产使用 Postgres（with_for_update 行锁生效）；sqlite 下 SELECT ... FOR UPDATE
被 SQLAlchemy 渲染为空操作，不影响紧凑逻辑本身的正确性。
"""

import os

# 必须在导入 app.* 之前：database.py 导入时即按 DATABASE_URL 创建 engine
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SEED_ON_EMPTY", "false")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def _get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
