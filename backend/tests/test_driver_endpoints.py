from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base, Driver, Order, get_db
from backend.main import app
from backend.api import orders as orders_module

TEST_DB_URL = "sqlite:///./test_driver_api.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
  db = TestingSessionLocal()
  try:
    yield db
  finally:
    db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def clean_database():
  Base.metadata.drop_all(bind=test_engine)
  Base.metadata.create_all(bind=test_engine)
  yield
  Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
  session = TestingSessionLocal()
  try:
    yield session
  finally:
    session.close()


@pytest.fixture
def driver(db_session):
  driver = Driver(name="Test Driver", phone="+49123456", access_code="TESTCODE")
  db_session.add(driver)
  db_session.commit()
  db_session.refresh(driver)
  return driver


@pytest.fixture
def order(db_session, driver):
  order = Order(
    order_number="ORD-TEST-0001",
    delivery_address="Teststrasse 1, Stuttgart",
    customer_name="Alice Example",
    assigned_driver_id=driver.id,
    driver_status="assigned",
    status="assigned",
    priority="normal",
  )
  db_session.add(order)
  db_session.commit()
  db_session.refresh(order)
  return order


@pytest.fixture
def client(tmp_path, monkeypatch):
  proof_dir = tmp_path / "proof"
  proof_dir.mkdir(parents=True, exist_ok=True)
  monkeypatch.setattr(orders_module, "PROOF_UPLOAD_DIR", proof_dir)
  return TestClient(app)


def test_requires_driver_token(client):
  response = client.get("/api/orders/driver/orders")
  assert response.status_code == 401


def test_driver_can_list_assigned_orders(client, order, driver):
  response = client.get(
    "/api/orders/driver/orders",
    headers={"X-Driver-Code": driver.access_code},
  )
  assert response.status_code == 200
  data = response.json()
  assert len(data) == 1
  assert data[0]["order"]["delivery_address"] == order.delivery_address


def test_driver_can_update_status(client, db_session, order, driver):
  payload = {
    "status": "en_route",
    "notes": "Heading out",
    "gps_lat": 48.775,
    "gps_lng": 9.182,
  }
  response = client.post(
    f"/api/orders/driver/orders/{order.id}/status",
    json=payload,
    headers={"X-Driver-Code": driver.access_code},
  )
  assert response.status_code == 200
  db_session.refresh(order)
  assert order.driver_status == "en_route"
  assert order.driver_notes == "Heading out"
  assert order.driver_gps_lat == pytest.approx(48.775)
  assert order.driver_gps_lng == pytest.approx(9.182)


def test_driver_can_upload_signature_only(client, db_session, order, driver):
  data_url = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
  )
  response = client.post(
    f"/api/orders/driver/orders/{order.id}/proof",
    data={"signature_data": data_url, "notes": "Signed by receiver"},
    headers={"X-Driver-Code": driver.access_code},
  )
  assert response.status_code == 200
  db_session.refresh(order)
  assert order.proof_signature_path
  assert Path(order.proof_signature_path).exists()
  assert order.driver_status == "delivered"
