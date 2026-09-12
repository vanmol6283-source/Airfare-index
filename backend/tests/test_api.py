"""
tests/test_api.py — Integration tests for the APIx REST API.

Run with:
    cd backend
    pytest tests/ -v
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db

# ── Test database (in-memory SQLite) ─────────────────────────────────────────
TEST_DATABASE_URL = "sqlite:///./test_airfare.db"
test_engine = create_engine(
    TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    # Seed minimal data
    from tests.fixtures import seed_test_data
    db = TestSessionLocal()
    seed_test_data(db)
    db.close()
    yield
    Base.metadata.drop_all(bind=test_engine)


client = TestClient(app)


# ── Health ────────────────────────────────────────────────────────────────────

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


# ── Summary ───────────────────────────────────────────────────────────────────

def test_summary_returns_valid_structure():
    response = client.get("/api/v1/summary")
    assert response.status_code == 200
    data = response.json()
    assert "apixToday" in data
    assert "momChange" in data
    assert "yoyChange" in data
    assert "lastUpdated" in data
    assert "routesTracked" in data
    assert "dataPointsToday" in data


def test_summary_apix_is_positive():
    response = client.get("/api/v1/summary")
    assert response.status_code == 200
    assert response.json()["apixToday"] > 0


# ── Basket ────────────────────────────────────────────────────────────────────

def test_basket_returns_list():
    response = client.get("/api/v1/basket")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_basket_item_has_required_fields():
    response = client.get("/api/v1/basket")
    item = response.json()[0]
    required = ["route", "origin", "destination", "apWindow",
                "baseFare", "currentFare", "priceRelative", "weight",
                "change7d", "change30d", "dataPoints", "history"]
    for field in required:
        assert field in item, f"Missing field: {field}"


def test_basket_weights_sum_to_approx_100():
    response = client.get("/api/v1/basket")
    data = response.json()
    total_weight = sum(item["weight"] for item in data)
    # Sum of weights across all AP windows × routes
    # Each route has 5 windows, so route weight × 5 sums to ~100
    assert 95 < total_weight < 105, f"Weights sum: {total_weight}"


# ── Route detail ──────────────────────────────────────────────────────────────

def test_route_detail_del_bom():
    response = client.get("/api/v1/route/DEL-BOM")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 5  # 5 AP windows


def test_route_detail_invalid():
    response = client.get("/api/v1/route/XXX-YYY")
    assert response.status_code == 404


def test_route_detail_all_ap_windows_present():
    response = client.get("/api/v1/route/DEL-BOM")
    windows = {item["apWindow"] for item in response.json()}
    expected = {"T+1", "T+7", "T+15", "T+30", "T+45"}
    assert windows == expected


# ── Index history ──────────────────────────────────────────────────────────────

def test_index_history_daily():
    response = client.get("/api/v1/index-history?freq=daily")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert "date" in data[0]
    assert "apix" in data[0]
    assert data[0]["frequency"] == "daily"


def test_index_history_weekly():
    response = client.get("/api/v1/index-history?freq=weekly")
    assert response.status_code == 200
    data = response.json()
    assert all(d["frequency"] == "weekly" for d in data)


def test_index_history_monthly():
    response = client.get("/api/v1/index-history?freq=monthly")
    assert response.status_code == 200
    data = response.json()
    assert all(d["frequency"] == "monthly" for d in data)


def test_index_history_invalid_freq():
    response = client.get("/api/v1/index-history?freq=yearly")
    assert response.status_code == 422  # FastAPI validation error


# ── Data quality ──────────────────────────────────────────────────────────────

def test_data_quality_returns_list():
    response = client.get("/api/v1/data-quality")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
