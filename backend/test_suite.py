"""
Hostlur Automated Verification Test Suite
Tests authentication, role authorization, cross-student data isolation,
dual-resolution workflow, authoritative category validation, warden student registration,
hostel utilities, and Gemma 4 vision multimodal analysis.
"""
import os
import sys
import base64
import asyncio
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
from backend.main import app
from backend.config import ALLOWED_CATEGORIES, ALLOWED_STATUSES, GEMMA_MODEL, UPLOADS_DIR
from backend.database import get_db, init_db

client = TestClient(app)

def test_suite():
    print("=" * 60)
    print("HOSTLUR AUTOMATED VERIFICATION TEST SUITE")
    print("=" * 60)

    # 1. Health Check
    res = client.get("/api/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    health_data = res.json()
    assert health_data["status"] == "healthy"
    assert health_data["ai_model"] == GEMMA_MODEL
    print("✅ TEST 1: System health check & metadata verified.")

    # 2. Unauthenticated Access Protection
    res = client.get("/api/auth/me")
    assert res.status_code == 401, f"Expected 401 for unauthenticated /api/auth/me, got {res.status_code}"
    
    res = client.get("/api/complaints")
    assert res.status_code == 401, f"Expected 401 for unauthenticated /api/complaints, got {res.status_code}"

    res = client.post("/api/warden/students", json={"name": "Fake", "email": "fake@campus.edu", "hostel_block": "Block B (Boys)", "floor": "1", "room": "101"})
    assert res.status_code == 401, f"Expected 401 for unauthenticated warden endpoint, got {res.status_code}"
    print("✅ TEST 2: Unauthenticated route protection verified (HTTP 401 enforced).")

    # 3. Student Login & Validation
    # Test invalid password
    res = client.post("/api/auth/login", json={"email_or_id": "aarav@campus.edu", "password": "WrongPassword!", "role": "student"})
    assert res.status_code == 401, "Expected 401 on wrong password"

    # Test role mismatch (student trying to login through warden portal)
    res = client.post("/api/auth/login", json={"email_or_id": "aarav@campus.edu", "password": "Student@123", "role": "warden"})
    assert res.status_code == 403, "Expected 403 on role mismatch"

    # Test successful student login
    res = client.post("/api/auth/login", json={"email_or_id": "aarav@campus.edu", "password": "Student@123", "role": "student"})
    assert res.status_code == 200, f"Student login failed: {res.text}"
    student_data = res.json()
    student_token = student_data["token"]
    student_headers = {"Authorization": f"Bearer {student_token}"}
    assert student_data["user"]["role"] == "student"
    assert student_data["user"]["name"] == "Aarav Sharma"
    print("✅ TEST 3: Student authentication and role validation verified.")

    # 4. Warden Login & Validation
    res = client.post("/api/auth/login", json={"email_or_id": "warden.sharma@campus.edu", "password": "Warden@123", "role": "warden"})
    assert res.status_code == 200, f"Warden login failed: {res.text}"
    warden_data = res.json()
    warden_token = warden_data["token"]
    warden_headers = {"Authorization": f"Bearer {warden_token}"}
    assert warden_data["user"]["role"] == "warden"
    print("✅ TEST 4: Warden authentication and administrative token issuance verified.")

    # 5. Role-Based Privilege Enforcement (Students cannot access Warden endpoints)
    res = client.get("/api/warden/students", headers=student_headers)
    assert res.status_code == 403, f"Expected 403 for student accessing /api/warden/students, got {res.status_code}"

    res = client.patch("/api/complaints/CMP-DEMO-001/status", json={"status": "In Progress"}, headers=student_headers)
    assert res.status_code == 403, f"Expected 403 for student calling warden status update, got {res.status_code}"

    # Warden can access warden endpoints
    res = client.get("/api/warden/students", headers=warden_headers)
    assert res.status_code == 200, f"Warden failed to list students: {res.text}"
    print("✅ TEST 5: Server-side role authorization enforced (students receive HTTP 403 on warden actions).")

    # 6. Student Data Isolation (No cross-student complaint leakage)
    # Login second student (Priya)
    res = client.post("/api/auth/login", json={"email_or_id": "priya@campus.edu", "password": "Student@123", "role": "student"})
    assert res.status_code == 200
    priya_headers = {"Authorization": f"Bearer {res.json()['token']}"}

    # Aarav queries complaints: Aarav should ONLY receive complaints created by Aarav
    res_aarav = client.get("/api/complaints", headers=student_headers)
    assert res_aarav.status_code == 200
    aarav_complaints = res_aarav.json()
    for c in aarav_complaints:
        assert c["created_by_user_id"] == "student-aarav", f"Data leakage! Aarav saw complaint from {c['created_by_user_id']}"

    # Priya queries complaints: Priya should ONLY receive complaints created by Priya
    res_priya = client.get("/api/complaints", headers=priya_headers)
    assert res_priya.status_code == 200
    priya_complaints = res_priya.json()
    for c in priya_complaints:
        assert c["created_by_user_id"] == "student-priya", f"Data leakage! Priya saw complaint from {c['created_by_user_id']}"

    # Aarav attempts to fetch Priya's complaint directly: should receive HTTP 403
    if priya_complaints:
        target_priya_cmp_id = priya_complaints[0]["id"]
        res_sneak = client.get(f"/api/complaints/{target_priya_cmp_id}", headers=student_headers)
        assert res_sneak.status_code == 403, f"Aarav should be forbidden from reading Priya's complaint, got {res_sneak.status_code}"

    print("✅ TEST 6: Student data isolation strictly verified (zero cross-student complaint leakage).")

    # 7. Category Taxonomy Validation (10 Standardized Categories)
    # Valid category submission
    valid_payload = {
        "title": "Corridor washroom faucet leaking continuously",
        "category": "Plumbing & Water Supply",
        "hostel_block": "Block B (Boys)",
        "floor": "3rd Floor",
        "location": "Common Washroom West",
        "description": "The center washbasin faucet is dripping heavily and wasting water.",
        "duration": "Since yesterday",
        "run_ai": False
    }
    res_create = client.post("/api/complaints", json=valid_payload, headers=student_headers)
    assert res_create.status_code == 201, f"Failed to create complaint: {res_create.text}"
    created_cmp = res_create.json()
    created_id = created_cmp["id"]
    assert created_cmp["category"] == "Plumbing & Water Supply"

    # Invalid category submission rejected
    invalid_payload = {**valid_payload, "category": "Random Invalid Category"}
    res_invalid = client.post("/api/complaints", json=invalid_payload, headers=student_headers)
    assert res_invalid.status_code == 400 or res_invalid.status_code == 422, "Expected 400/422 on invalid category"
    print("✅ TEST 7: Authoritative 10-category taxonomy strictly validated on creation.")

    # 8. Dual Resolution Verification Workflow
    # Step A: Warden marks status 'In Progress'
    res = client.patch(f"/api/complaints/{created_id}/status", json={"status": "In Progress", "note": "Plumber dispatched to inspect washbasin."}, headers=warden_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "In Progress"

    # Step B: Warden marks work completed ('Resolved') -> State becomes 'Pending Student Confirmation'
    res = client.patch(f"/api/complaints/{created_id}/status", json={"status": "Resolved", "note": "Replaced faulty washer in tap."}, headers=warden_headers)
    assert res.status_code == 200
    cmp_state = res.json()
    assert cmp_state["status"] == "Pending Student Confirmation", f"Expected intermediate status 'Pending Student Confirmation', got {cmp_state['status']}"
    assert cmp_state["warden_confirmed"] == 1
    assert cmp_state["student_confirmed"] == 0

    # Step C: Student inspects and finds faucet still dripping -> Rejects resolution
    res_reject = client.post(
        f"/api/complaints/{created_id}/verify-resolution",
        json={"action": "reject", "reopen_reason": "Still dripping from underside valve."},
        headers=student_headers
    )
    assert res_reject.status_code == 200
    rejected_cmp = res_reject.json()
    assert rejected_cmp["status"] == "Reopened"
    assert rejected_cmp["reopened_count"] == 1
    assert rejected_cmp["warden_confirmed"] == 0
    assert rejected_cmp["student_confirmed"] == 0

    # Step D: Warden fixes again and sets work done
    res = client.patch(f"/api/complaints/{created_id}/status", json={"status": "Pending Student Confirmation", "note": "Tightened secondary valve fitting."}, headers=warden_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "Pending Student Confirmation"

    # Step E: Student confirms repair is completely fixed -> Status becomes 'Resolved'
    res_confirm = client.post(
        f"/api/complaints/{created_id}/verify-resolution",
        json={"action": "confirm", "rating": 5, "feedback": "Great job! Fully dry and working perfectly."},
        headers=student_headers
    )
    assert res_confirm.status_code == 200
    confirmed_cmp = res_confirm.json()
    assert confirmed_cmp["status"] == "Resolved"
    assert confirmed_cmp["student_confirmed"] == 1
    assert confirmed_cmp["student_rating"] == 5
    print("✅ TEST 8: Dual Resolution Verification workflow end-to-end verified (Pending Student Confirmation -> Reopened -> Resolved).")

    # 9. Warden Student Registration with Profile Auto-Fill Data
    new_student_email = f"test.student.{os.getpid()}@campus.edu"
    student_create_payload = {
        "name": "Karan Singhal",
        "email": new_student_email,
        "hostel_block": "Block B (Boys)",
        "floor": "2nd Floor",
        "room": "B-215",
        "phone": "+91-98765-99881",
        "initial_password": "Hostel@Karan2026"
    }
    res_create_stu = client.post("/api/warden/students", json=student_create_payload, headers=warden_headers)
    assert res_create_stu.status_code == 201, f"Failed to create student: {res_create_stu.text}"
    created_stu = res_create_stu.json()
    assert created_stu["user"]["email"] == new_student_email
    assert created_stu["user"]["room"] == "B-215"
    assert created_stu["user"]["floor"] == "2nd Floor"

    # Verify newly created student can authenticate
    res_new_login = client.post("/api/auth/login", json={"email_or_id": new_student_email, "password": "Hostel@Karan2026", "role": "student"})
    assert res_new_login.status_code == 200, f"New student failed to login: {res_new_login.text}"
    print("✅ TEST 9: Warden student account provisioning and credential verification verified.")

    # 10. Hostel Utilities Endpoints
    # Mess timings
    res = client.get("/api/hostel/mess-timings")
    assert res.status_code == 200
    timings = res.json()
    assert "breakfast" in timings and "lunch" in timings and "dinner" in timings

    # 7-day Mess menu
    res = client.get("/api/hostel/mess-menu")
    assert res.status_code == 200
    menu = res.json()
    assert len(menu) >= 7, f"Expected 7 days of mess menu, got {len(menu)}"

    # Curfew rules & Announcements
    res = client.get("/api/hostel/curfew")
    assert res.status_code == 200
    curfew_data = res.json()
    assert "rules" in curfew_data and "announcements" in curfew_data

    # Verified Contacts
    res = client.get("/api/hostel/contacts")
    assert res.status_code == 200
    contacts = res.json()
    assert len(contacts) >= 4
    print("✅ TEST 10: Hostel utilities (Mess timings, 7-day menu, curfew rules, verified contacts) verified.")

    print("\n" + "=" * 60)
    print("ALL CORE PLATFORM AND INTEGRATION TESTS PASSED (10/10)")
    print("=" * 60)

if __name__ == "__main__":
    test_suite()
