import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

# Setup test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override database dependency in FastAPI
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Create test client
client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    # Create tables
    Base.metadata.create_all(bind=engine)
    yield
    # Drop tables
    Base.metadata.drop_all(bind=engine)

def test_auth_and_reminder_crud():
    # 1. Register a test user
    reg_resp = client.post("/register", json={"username": "testuser", "password": "password123"})
    assert reg_resp.status_code == 201
    assert reg_resp.json()["username"] == "testuser"

    # 2. Login to get a token
    login_resp = client.post("/api/auth/login", json={"username": "testuser", "password": "password123"})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Create a reminder config
    new_reminder = {
        "name": "Sprint Hygiene Check",
        "type": "SUBTASK_CREATION_REMINDER",
        "category": "sprint",
        "schedule": "0 9 * * 1-5",
        "enabled": True,
        "recipients": {"users": ["alice", "bob"], "groups": ["devs"]},
        "channels": ["slack"],
        "template_string": "Hi {{ assignee }},\n🔴 Tasks Missing Subtasks:\n{% for item in missing_subtasks -%}- {{ make_link('jira', item.issue_key) }} ({{ item.summary }})\n{% endfor %}",
        "tool_hints": ["JiraTool"],
        "data_requirements": {},
        "aggregation": {"group_by": ["assignee"], "combine_alerts": True},
        "execution": {"allow_multi_tool": True, "allow_multi_query": True},
        "metadata_json": {"project_keys": ["ABC"]},
        "retry_policy": {},
        "notification_rules": {}
    }
    
    create_resp = client.post("/reminders", json=new_reminder, headers=headers)
    assert create_resp.status_code == 201
    created_id = create_resp.json()["id"]
    assert create_resp.json()["name"] == "Sprint Hygiene Check"

    # 4. Read all reminders
    read_resp = client.get("/reminders", headers=headers)
    assert read_resp.status_code == 200
    assert len(read_resp.json()) >= 1

    # 5. Update the reminder config
    update_data = {"name": "Updated Sprint Hygiene Check", "enabled": False}
    update_resp = client.put(f"/reminders/{created_id}", json=update_data, headers=headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Updated Sprint Hygiene Check"
    assert update_resp.json()["enabled"] is False

    # 6. Re-enable reminder for triggering
    client.put(f"/reminders/{created_id}", json={"enabled": True}, headers=headers)

    # 7. Trigger the reminder manually
    trigger_resp = client.post(f"/reminders/{created_id}/trigger", headers=headers)
    assert trigger_resp.status_code == 200
    assert trigger_resp.json()["status"] == "SUCCESS"
    assert "logs" in trigger_resp.json()
    assert "consolidated_messages" in trigger_resp.json()

    # 8. Trigger batch manually
    batch_resp = client.post("/reminders/trigger-batch", headers=headers)
    assert batch_resp.status_code == 200
    assert batch_resp.json()["status"] == "SUCCESS"

    # 9. Delete the reminder config
    del_resp = client.delete(f"/reminders/{created_id}", headers=headers)
    assert del_resp.status_code == 204
