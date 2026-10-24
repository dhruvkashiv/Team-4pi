from fastapi.testclient import TestClient
from backend.main import app
from backend.database import init_db

client = TestClient(app)

def setup_module(module):
    init_db()

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "ai_model" in data
    assert data["service"] == "Hostlur"

def test_auth_me_default_student():
    response = client.get("/api/auth/me", headers={"X-User-Id": "student-aarav"})
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "student-aarav"
    assert data["role"] == "student"

def test_auth_me_warden():
    response = client.get("/api/auth/me", headers={"X-User-Id": "warden-sharma"})
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "warden-sharma"
    assert data["role"] == "warden"

def test_get_stats():
    response = client.get("/api/stats", headers={"X-User-Id": "student-aarav"})
    assert response.status_code == 200
    data = response.json()
    assert "student" in data
    assert "warden" in data
    assert data["student"]["total_submitted"] >= 0
    assert data["warden"]["total_open"] >= 0

def test_create_complaint_and_read():
    payload = {
        "title": "Study table light flickers in room B-302",
        "category": "Electricity",
        "hostel_block": "Block B (Boys)",
        "location": "Room B-302",
        "duration": "Since yesterday",
        "description": "The study table fluorescent bulb flickers continuously and hurts my eyes when studying.",
        "run_ai": False
    }
    create_resp = client.post(
        "/api/complaints",
        json=payload,
        headers={"X-User-Id": "student-aarav"}
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["title"] == payload["title"]
    assert created["category"] == "Electricity"
    assert created["status"] == "Submitted"
    complaint_id = created["id"]

    # Verify retrieval
    get_resp = client.get(f"/api/complaints/{complaint_id}", headers={"X-User-Id": "student-aarav"})
    assert get_resp.status_code == 200
    details = get_resp.json()
    assert details["id"] == complaint_id
    assert len(details["history"]) >= 1

def test_support_complaint_toggle():
    # First get an existing complaint
    list_resp = client.get("/api/complaints", headers={"X-User-Id": "student-priya"})
    assert list_resp.status_code == 200
    complaints = list_resp.json()
    assert len(complaints) > 0
    target_id = complaints[0]["id"]
    initial_count = complaints[0]["supporters_count"]

    # Support it
    support_resp = client.post(f"/api/complaints/{target_id}/support", headers={"X-User-Id": "student-priya"})
    assert support_resp.status_code == 200
    res_data = support_resp.json()
    assert res_data["supported"] is True
    assert res_data["supporters_count"] == initial_count + 1

    # Toggle off
    unsupport_resp = client.post(f"/api/complaints/{target_id}/support", headers={"X-User-Id": "student-priya"})
    assert unsupport_resp.status_code == 200
    unres_data = unsupport_resp.json()
    assert unres_data["supported"] is False
    assert unres_data["supporters_count"] == initial_count

def test_warden_authorization_restriction():
    list_resp = client.get("/api/complaints", headers={"X-User-Id": "student-aarav"})
    target_id = list_resp.json()[0]["id"]

    # 1. Student trying to update status -> MUST FAIL with 403 Forbidden
    student_patch = client.patch(
        f"/api/complaints/{target_id}/status",
        json={"status": "Resolved", "note": "Trying to resolve my own ticket"},
        headers={"X-User-Id": "student-aarav"}
    )
    assert student_patch.status_code == 403

    # 2. Warden updating status -> MUST SUCCEED with 200 OK
    warden_patch = client.patch(
        f"/api/complaints/{target_id}/status",
        json={"status": "In Progress", "note": "Warden dispatched technician."},
        headers={"X-User-Id": "warden-sharma"}
    )
    assert warden_patch.status_code == 200
    assert warden_patch.json()["status"] == "In Progress"

def test_deterministic_hazard_safety_check():
    from backend.ai_service import detect_hazards
    is_hazard, reason = detect_hazards("There is a short circuit and spark in the ceiling fan!")
    assert is_hazard is True
    assert "spark" in reason or "short circuit" in reason

def test_related_complaints():
    resp = client.get(
        "/api/complaints/related?block=Block+B+(Boys)&category=Wi-Fi+and+Internet",
        headers={"X-User-Id": "student-aarav"}
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

if __name__ == "__main__":
    init_db()
    test_health_check()
    test_auth_me_default_student()
    test_auth_me_warden()
    test_get_stats()
    test_create_complaint_and_read()
    test_support_complaint_toggle()
    test_warden_authorization_restriction()
    test_deterministic_hazard_safety_check()
    test_related_complaints()
    print("ALL 9 TEST SUITES PASSED CLEANLY!")
