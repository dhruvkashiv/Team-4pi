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
    assert data["service"] == "Hostlur"
    assert data["version"] == "2.0.0"

def test_login_flow():
    # 1. Student login with valid credentials
    resp = client.post("/api/auth/login", json={"email_or_id": "aarav@campus.edu", "password": "student123", "role": "student"})
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["user"]["role"] == "student"

    # 2. Invalid password failure
    bad_resp = client.post("/api/auth/login", json={"email_or_id": "aarav@campus.edu", "password": "wrongpassword"})
    assert bad_resp.status_code == 401

    # 3. Warden login
    w_resp = client.post("/api/auth/login", json={"email_or_id": "warden.sharma@campus.edu", "password": "warden123", "role": "warden"})
    assert w_resp.status_code == 200
    assert w_resp.json()["user"]["role"] == "warden"

def test_warden_student_management():
    # Warden creates new student
    new_student_data = {
        "name": "Rohan Mehta",
        "email": "rohan.mehta@campus.edu",
        "hostel_block": "Block B (Boys)",
        "floor": "2nd Floor",
        "room": "B-210",
        "phone": "+91-98765-44332",
        "initial_password": "RohanSecret123"
    }
    create_resp = client.post(
        "/api/warden/students",
        json=new_student_data,
        headers={"X-User-Id": "warden-sharma"}
    )
    assert create_resp.status_code == 201
    created_id = create_resp.json()["user"]["id"]

    # Student cannot create students (403 Forbidden)
    forbidden_resp = client.post(
        "/api/warden/students",
        json=new_student_data,
        headers={"X-User-Id": "student-aarav"}
    )
    assert forbidden_resp.status_code == 403

    # Warden resets student password
    reset_resp = client.post(
        f"/api/warden/students/{created_id}/reset-password",
        headers={"X-User-Id": "warden-sharma"}
    )
    assert reset_resp.status_code == 200
    assert "temporary_password" in reset_resp.json()

def test_dual_resolution_verification():
    # 1. Create a complaint
    c_resp = client.post(
        "/api/complaints",
        json={
            "title": "Bathroom tap dripping on 3rd floor",
            "category": "Water Supply",
            "hostel_block": "Block B (Boys)",
            "floor": "3rd Floor",
            "location": "Room B-302 Washroom",
            "description": "The sink faucet has a constant leak that wastes water.",
            "run_ai": False
        },
        headers={"X-User-Id": "student-aarav"}
    )
    assert c_resp.status_code == 201
    cid = c_resp.json()["id"]

    # 2. Warden marks repair complete -> transitions to Pending Student Confirmation
    patch_resp = client.patch(
        f"/api/complaints/{cid}/status",
        json={"status": "Pending Student Confirmation", "note": "Plumber replaced washer."},
        headers={"X-User-Id": "warden-sharma"}
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "Pending Student Confirmation"
    assert patch_resp.json()["warden_confirmed"] == 1

    # 3. Student rejects resolution if issue still persists -> transitions to Reopened
    reject_resp = client.post(
        f"/api/complaints/{cid}/verify-resolution",
        json={"action": "reject", "reopen_reason": "Still dripping after plumber left"},
        headers={"X-User-Id": "student-aarav"}
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "Reopened"
    assert reject_resp.json()["reopened_count"] == 1

    # 4. Warden revisits and marks complete again
    client.patch(
        f"/api/complaints/{cid}/status",
        json={"status": "Pending Student Confirmation", "note": "New faucet installed."},
        headers={"X-User-Id": "warden-sharma"}
    )

    # 5. Student confirms resolution -> transitions to fully Resolved with rating
    confirm_resp = client.post(
        f"/api/complaints/{cid}/verify-resolution",
        json={"action": "confirm", "rating": 5, "feedback": "Working perfectly now!"},
        headers={"X-User-Id": "student-aarav"}
    )
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["status"] == "Resolved"
    assert confirm_resp.json()["student_confirmed"] == 1
    assert confirm_resp.json()["student_rating"] == 5

def test_hostel_info_endpoints():
    # Contacts
    c_resp = client.get("/api/hostel/contacts")
    assert c_resp.status_code == 200
    assert "chief_warden" in c_resp.json()

    # Mess Timings
    m_resp = client.get("/api/hostel/mess-timings")
    assert m_resp.status_code == 200
    assert "breakfast" in m_resp.json()

    # Mess Menu
    menu_resp = client.get("/api/hostel/mess-menu")
    assert menu_resp.status_code == 200
    assert len(menu_resp.json()) == 7  # 7 days

    # Curfew Rules
    curfew_resp = client.get("/api/hostel/curfew")
    assert curfew_resp.status_code == 200
    assert "weekday" in curfew_resp.json()["rules"]
    assert len(curfew_resp.json()["announcements"]) >= 1

def test_deterministic_hazard_safety_check():
    from backend.ai_service import detect_hazards
    is_hazard, reason = detect_hazards("Live wire touching puddle of water on floor 2!")
    assert is_hazard is True
    assert "live wire" in reason

if __name__ == "__main__":
    init_db()
    test_health_check()
    test_login_flow()
    test_warden_student_management()
    test_dual_resolution_verification()
    test_hostel_info_endpoints()
    test_deterministic_hazard_safety_check()
    print("ALL TEST SUITES PASSED CLEANLY FOR HOSTLUR V2.0!")
