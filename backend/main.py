import json
import uuid
import base64
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, Query, Header, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.config import (
    BASE_DIR,
    UPLOADS_DIR,
    ALLOWED_CATEGORIES,
    ALLOWED_PRIORITIES,
    ALLOWED_STATUSES,
    HOSTEL_BLOCKS,
    HOSTEL_CONTACTS,
    MESS_TIMINGS,
    CURFEW_RULES,
    GEMMA_MODEL
)
from backend.database import get_db, init_db, hash_password, verify_password
from backend.models import (
    AIAnalyzeRequest,
    AIAnalysisResult,
    ComplaintCreate,
    StatusUpdateRequest,
    StudentResolutionRequest,
    UserProfile,
    LoginRequest,
    LoginResponse,
    ChangePasswordRequest,
    StudentCreateRequest,
    StudentProfileUpdateRequest,
    ImageUploadResponse
)
from backend.auth import (
    get_current_user,
    require_warden,
    require_student,
    authenticate_user,
    create_session,
    delete_session
)
from backend.ai_service import analyze_complaint_with_gemma

app = FastAPI(
    title="Hostlur API",
    description="Hostel Life, Simplified. AI-assisted hostel complaint management system.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    init_db()

# --- HEALTH & METADATA ---
@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Hostlur",
        "version": "2.0.0",
        "ai_model": GEMMA_MODEL,
        "database": "SQLite (WAL)",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# --- AUTHENTICATION & SESSIONS ---
@app.post("/api/auth/login", response_model=LoginResponse)
def login(req: LoginRequest):
    """Logs in student or warden and returns a session token."""
    user = authenticate_user(req.email_or_id, req.password, expected_role=req.role)
    token = create_session(user.id, user.role)
    return LoginResponse(
        token=token,
        user=user,
        message=f"Welcome back, {user.name}!"
    )

@app.post("/api/auth/logout")
def logout(authorization: Optional[str] = Header(None)):
    """Logs out by terminating the session token."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        delete_session(token)
    return {"message": "Successfully logged out."}

@app.get("/api/auth/me", response_model=UserProfile)
def get_me(user: UserProfile = Depends(get_current_user)):
    """Returns the authenticated user's profile."""
    return user

@app.post("/api/auth/change-password")
def change_password(
    req: ChangePasswordRequest,
    current_user: UserProfile = Depends(get_current_user)
):
    """Allows authenticated user to update their password securely."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash, salt FROM users WHERE id = ?", (current_user.id,))
    row = cursor.fetchone()

    if not row or not verify_password(req.current_password, row["password_hash"], row["salt"]):
        conn.close()
        raise HTTPException(status_code=400, detail="Current password incorrect.")

    new_hash, new_salt = hash_password(req.new_password)
    cursor.execute("UPDATE users SET password_hash = ?, salt = ? WHERE id = ?", (new_hash, new_salt, current_user.id))
    conn.commit()
    conn.close()
    return {"message": "Password updated successfully."}

@app.patch("/api/auth/profile", response_model=UserProfile)
def update_profile(
    req: StudentProfileUpdateRequest,
    current_user: UserProfile = Depends(get_current_user)
):
    """Allows student to update their phone or room number."""
    conn = get_db()
    cursor = conn.cursor()

    updates = []
    params = []
    if req.phone is not None:
        updates.append("phone = ?")
        params.append(req.phone)
    if req.room is not None:
        updates.append("room = ?")
        params.append(req.room)
    if req.floor is not None:
        updates.append("floor = ?")
        params.append(req.floor)

    if updates:
        params.append(current_user.id)
        cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()

    cursor.execute("SELECT id, name, email, role, hostel_block, floor, room, phone FROM users WHERE id = ?", (current_user.id,))
    updated_row = dict(cursor.fetchone())
    conn.close()
    return UserProfile(**updated_row)

@app.get("/api/users")
def list_demo_users():
    """Returns available demo personas for quick switching in hackathon UI."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, role, hostel_block, floor, room, phone FROM users ORDER BY role DESC, name ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# --- STUDENT MANAGEMENT (WARDEN RESTRICTED) ---
@app.get("/api/warden/students")
def list_students(warden: UserProfile = Depends(require_warden)):
    """Wardens can view all registered student accounts."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, name, email, hostel_block, floor, room, phone, created_at
    FROM users
    WHERE role = 'student'
    ORDER BY hostel_block ASC, room ASC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@app.post("/api/warden/students", status_code=status.HTTP_201_CREATED)
def create_student_account(
    req: StudentCreateRequest,
    warden: UserProfile = Depends(require_warden)
):
    """Allows authorized warden to register a new student account securely."""
    conn = get_db()
    cursor = conn.cursor()

    # Check email uniqueness
    cursor.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (req.email,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="A user with this email already exists.")

    student_id = f"student-{uuid.uuid4().hex[:6]}"
    initial_pwd = req.initial_password or f"Hostel@{secrets.token_hex(3).upper()}"
    p_hash, p_salt = hash_password(initial_pwd)
    now = datetime.now(timezone.utc).isoformat()

    cursor.execute("""
    INSERT INTO users (id, name, email, role, hostel_block, floor, room, phone, password_hash, salt, created_at)
    VALUES (?, ?, ?, 'student', ?, ?, ?, ?, ?, ?, ?)
    """, (
        student_id,
        req.name,
        req.email,
        req.hostel_block,
        req.floor,
        req.room,
        req.phone or "+91-98765-00000",
        p_hash,
        p_salt,
        now
    ))
    conn.commit()
    conn.close()

    return {
        "message": "Student account created successfully.",
        "user": {
            "id": student_id,
            "name": req.name,
            "email": req.email,
            "role": "student",
            "hostel_block": req.hostel_block,
            "floor": req.floor,
            "room": req.room,
            "phone": req.phone
        },
        "initial_password": initial_pwd
    }

@app.post("/api/warden/students/{student_id}/reset-password")
def reset_student_password(
    student_id: str,
    warden: UserProfile = Depends(require_warden)
):
    """Allows warden to generate a new secure temporary password for a student."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM users WHERE id = ? AND role = 'student'", (student_id,))
    student = cursor.fetchone()
    if not student:
        conn.close()
        raise HTTPException(status_code=404, detail="Student not found.")

    new_temporary_pwd = f"Reset@{secrets.token_hex(4).upper()}"
    p_hash, p_salt = hash_password(new_temporary_pwd)

    cursor.execute("UPDATE users SET password_hash = ?, salt = ? WHERE id = ?", (p_hash, p_salt, student_id))
    conn.commit()
    conn.close()

    return {
        "student_id": student_id,
        "name": student["name"],
        "temporary_password": new_temporary_pwd,
        "message": "Temporary password generated. Please communicate it to the student securely."
    }

# --- IMAGE UPLOAD ---
class Base64UploadRequest(BaseModel):
    image_data: str
    filename: Optional[str] = "complaint.jpg"

@app.post("/api/upload", response_model=ImageUploadResponse)
def upload_image(
    req: Base64UploadRequest,
    current_user: UserProfile = Depends(get_current_user)
):
    """Safely saves a student-uploaded image and returns its static URL."""
    try:
        raw_b64 = req.image_data
        ext = "jpg"
        if raw_b64.startswith("data:"):
            header, raw_b64 = raw_b64.split(",", 1)
            if "png" in header:
                ext = "png"
            elif "webp" in header:
                ext = "webp"

        image_bytes = base64.b64decode(raw_b64)
        if len(image_bytes) > 8 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image size exceeds 8MB limit.")

        unique_filename = f"img_{uuid.uuid4().hex[:10]}.{ext}"
        target_path = UPLOADS_DIR / unique_filename
        with open(target_path, "wb") as f:
            f.write(image_bytes)

        return ImageUploadResponse(
            image_url=f"/static/uploads/{unique_filename}",
            filename=unique_filename,
            message="Image uploaded successfully."
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Image upload failed: {str(e)}")

# --- AI ANALYSIS (TEXT & GEMMA 4 MULTIMODAL VISION) ---
@app.post("/api/ai/analyze", response_model=AIAnalysisResult)
async def analyze_complaint(
    req: AIAnalyzeRequest,
    current_user: UserProfile = Depends(get_current_user)
):
    """
    Analyzes student complaint using Google's Gemma 4 model.
    Supports multimodal analysis when an image is attached.
    Extracts category, priority, concise summary, and checks for hazards.
    """
    desc = (req.description or "").strip()
    if not req.image_data and len(desc) < 3:
        raise HTTPException(status_code=400, detail="Description is too short for AI analysis.")
    if not desc:
        desc = "Please inspect the attached image and analyze the hostel issue."

    result = await analyze_complaint_with_gemma(
        description=desc,
        hostel_block=req.hostel_block or current_user.hostel_block,
        location=req.location,
        image_data=req.image_data
    )
    return result

# --- HOSTEL INFORMATION (CONTACTS, MESS, CURFEW) ---
@app.get("/api/hostel/contacts")
def get_hostel_contacts():
    """Returns verified warden and hostel administration contact details."""
    return HOSTEL_CONTACTS

@app.get("/api/hostel/mess-timings")
def get_mess_timings():
    """Returns breakfast, lunch, snacks, and dinner meal hours."""
    return MESS_TIMINGS

@app.get("/api/hostel/mess-menu")
def get_mess_menu():
    """Returns weekly 7-day mess menu schedule."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT day_of_week, breakfast, lunch, snacks, dinner, special_note FROM mess_menu")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

@app.get("/api/hostel/curfew")
def get_curfew_and_announcements():
    """Returns campus curfew rules and active hostel announcements."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, content, category, created_at FROM announcements WHERE active = 1 ORDER BY created_at DESC")
    announcements = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {
        "rules": CURFEW_RULES,
        "announcements": announcements
    }

# --- RELATED COMPLAINTS (DUPLICATE DETECTION) ---
@app.get("/api/complaints/related")
def get_related_complaints(
    block: str = Query(..., description="Hostel block"),
    category: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    current_user: UserProfile = Depends(get_current_user)
):
    """Finds existing open complaints in the same block/category."""
    conn = get_db()
    cursor = conn.cursor()

    query = """
    SELECT id, title, description, category, hostel_block, location, status,
           suggested_priority, supporters_count, created_at
    FROM complaints
    WHERE hostel_block = ? AND status != 'Resolved'
    """
    params = [block]

    if category and category in ALLOWED_CATEGORIES:
        query += " AND category = ?"
        params.append(category)

    if q and len(q.strip()) > 2:
        query += " AND (title LIKE ? OR description LIKE ?)"
        wildcard = f"%{q.strip()}%"
        params.extend([wildcard, wildcard])

    query += " ORDER BY supporters_count DESC, created_at DESC LIMIT 5"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    return [dict(r) for r in rows]

# --- COMPLAINTS CRUD ---
@app.post("/api/complaints", status_code=status.HTTP_201_CREATED)
async def create_complaint(
    complaint: ComplaintCreate,
    current_user: UserProfile = Depends(get_current_user)
):
    """Creates a new hostel complaint with real database persistence, image support, and AI analysis."""
    if complaint.category not in ALLOWED_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category. Must be one of: {ALLOWED_CATEGORIES}")

    is_hazard = False
    hazard_reason = None
    suggested_priority = complaint.suggested_priority or "Medium"
    summary = complaint.summary or complaint.title
    missing_info = []
    ai_analyzed = 0

    if complaint.run_ai:
        try:
            ai_res = await analyze_complaint_with_gemma(
                description=complaint.description,
                hostel_block=complaint.hostel_block,
                location=complaint.location
            )
            suggested_priority = ai_res.suggested_priority
            summary = ai_res.summary or summary
            is_hazard = ai_res.is_hazard
            hazard_reason = ai_res.hazard_reason
            missing_info = ai_res.missing_information
            ai_analyzed = 1 if ai_res.ai_status == "success" else 0
        except Exception:
            pass

    now = datetime.now(timezone.utc).isoformat()
    complaint_id = f"CMP-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:5].upper()}"

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO complaints (
        id, title, description, category, hostel_block, floor, location, duration,
        suggested_priority, confirmed_priority, status, summary,
        missing_information, is_hazard, hazard_reason, ai_analyzed,
        image_url, warden_confirmed, warden_confirmed_at, warden_note,
        student_confirmed, student_confirmed_at, student_rating, student_feedback,
        reopened_count, created_by_user_id, created_by_name, created_by_room,
        supporters_count, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, NULL, 0, NULL, NULL, NULL, 0, ?, ?, ?, 0, ?, ?)
    """, (
        complaint_id,
        complaint.title,
        complaint.description,
        complaint.category,
        complaint.hostel_block,
        complaint.floor or current_user.floor,
        complaint.location,
        complaint.duration,
        suggested_priority,
        suggested_priority,
        "Submitted",
        summary,
        json.dumps(missing_info),
        1 if is_hazard else 0,
        hazard_reason,
        ai_analyzed,
        complaint.image_url,
        current_user.id,
        current_user.name,
        current_user.room,
        now,
        now
    ))

    cursor.execute("""
    INSERT INTO complaint_history (
        complaint_id, previous_status, new_status, changed_by_user_id, changed_by_name, note, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        complaint_id,
        None,
        "Submitted",
        current_user.id,
        current_user.name,
        "Complaint submitted by student.",
        now
    ))

    conn.commit()

    cursor.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,))
    created_row = dict(cursor.fetchone())
    conn.close()

    created_row["missing_information"] = json.loads(created_row.get("missing_information") or "[]")
    return created_row

@app.get("/api/complaints")
def list_complaints(
    category: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    block: Optional[str] = None,
    priority: Optional[str] = None,
    mine: bool = False,
    search: Optional[str] = None,
    current_user: UserProfile = Depends(get_current_user)
):
    """Returns complaints authorized for current user with dual-resolution indicators."""
    conn = get_db()
    cursor = conn.cursor()

    query = "SELECT * FROM complaints WHERE 1=1"
    params = []

    if current_user.role == "student":
        # Students are strictly isolated to their own complaints
        query += " AND created_by_user_id = ?"
        params.append(current_user.id)
    elif mine:
        query += " AND created_by_user_id = ?"
        params.append(current_user.id)

    if category and category in ALLOWED_CATEGORIES:
        query += " AND category = ?"
        params.append(category)

    if status_filter and status_filter in ALLOWED_STATUSES:
        query += " AND status = ?"
        params.append(status_filter)

    if block and block in HOSTEL_BLOCKS:
        query += " AND hostel_block = ?"
        params.append(block)

    if priority and priority in ALLOWED_PRIORITIES:
        query += " AND (suggested_priority = ? OR confirmed_priority = ?)"
        params.extend([priority, priority])

    if search and len(search.strip()) > 0:
        query += " AND (title LIKE ? OR description LIKE ? OR location LIKE ? OR summary LIKE ?)"
        term = f"%{search.strip()}%"
        params.extend([term, term, term, term])

    query += " ORDER BY is_hazard DESC, created_at DESC"
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]

    for r in rows:
        r["missing_information"] = json.loads(r.get("missing_information") or "[]")
        cursor.execute(
            "SELECT 1 FROM complaint_supporters WHERE complaint_id = ? AND user_id = ?",
            (r["id"], current_user.id)
        )
        r["has_supported"] = cursor.fetchone() is not None

    conn.close()
    return rows

@app.get("/api/complaints/{complaint_id}")
def get_complaint_details(
    complaint_id: str,
    current_user: UserProfile = Depends(get_current_user)
):
    """Returns single complaint details with timeline history, supporters, and dual resolution status."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Complaint not found")

    complaint = dict(row)
    if current_user.role == "student" and complaint["created_by_user_id"] != current_user.id:
        conn.close()
        raise HTTPException(status_code=403, detail="Access denied. You can only view your own complaints.")

    complaint["missing_information"] = json.loads(complaint.get("missing_information") or "[]")

    cursor.execute("""
    SELECT id, previous_status, new_status, changed_by_user_id, changed_by_name, note, created_at
    FROM complaint_history
    WHERE complaint_id = ?
    ORDER BY id ASC
    """, (complaint_id,))
    complaint["history"] = [dict(h) for h in cursor.fetchall()]

    cursor.execute(
        "SELECT 1 FROM complaint_supporters WHERE complaint_id = ? AND user_id = ?",
        (complaint_id, current_user.id)
    )
    complaint["has_supported"] = cursor.fetchone() is not None

    conn.close()
    return complaint

# --- DUAL RESOLUTION: WARDEN WORKFLOW ---
@app.patch("/api/complaints/{complaint_id}/status")
def update_complaint_status(
    complaint_id: str,
    req: StatusUpdateRequest,
    warden: UserProfile = Depends(require_warden)
):
    """
    Warden updates complaint status.
    If warden marks work done, status becomes 'Pending Student Confirmation'
    until the student verifies that the repair was actually successful.
    """
    if req.status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {ALLOWED_STATUSES}")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT status, confirmed_priority, student_confirmed FROM complaints WHERE id = ?", (complaint_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Complaint not found")

    previous_status = row["status"]
    now = datetime.now(timezone.utc).isoformat()
    new_priority = req.confirmed_priority if req.confirmed_priority in ALLOWED_PRIORITIES else row["confirmed_priority"]

    # Dual Resolution Rule:
    # If warden chooses 'Resolved', but student has not verified yet,
    # intermediate status is 'Pending Student Confirmation'.
    target_status = req.status
    warden_confirmed = 0
    warden_confirmed_at = None
    warden_note = req.note

    if req.status in ("Resolved", "Pending Student Confirmation"):
        warden_confirmed = 1
        warden_confirmed_at = now
        if row["student_confirmed"] == 1:
            target_status = "Resolved"
        else:
            target_status = "Pending Student Confirmation"

    cursor.execute("""
    UPDATE complaints
    SET status = ?, confirmed_priority = ?, warden_confirmed = ?,
        warden_confirmed_at = COALESCE(?, warden_confirmed_at),
        warden_note = COALESCE(?, warden_note), updated_at = ?
    WHERE id = ?
    """, (target_status, new_priority, warden_confirmed, warden_confirmed_at, warden_note, now, complaint_id))

    note_text = req.note or f"Warden changed status from {previous_status} to {target_status}"
    if target_status == "Pending Student Confirmation":
        note_text += " (Work marked complete by Warden. Awaiting Student Verification)."

    cursor.execute("""
    INSERT INTO complaint_history (
        complaint_id, previous_status, new_status, changed_by_user_id, changed_by_name, note, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        complaint_id,
        previous_status,
        target_status,
        warden.id,
        warden.name,
        note_text,
        now
    ))

    conn.commit()

    cursor.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,))
    updated_complaint = dict(cursor.fetchone())
    conn.close()

    updated_complaint["missing_information"] = json.loads(updated_complaint.get("missing_information") or "[]")
    return updated_complaint

# --- DUAL RESOLUTION: STUDENT VERIFICATION & REOPENING ---
@app.post("/api/complaints/{complaint_id}/verify-resolution")
def verify_complaint_resolution(
    complaint_id: str,
    req: StudentResolutionRequest,
    student: UserProfile = Depends(require_student)
):
    """
    Student confirms or rejects the resolution.
    - Confirm: Sets student_confirmed = 1, status = 'Resolved', records rating & feedback.
    - Reject: Reopens ticket (status = 'Reopened'), increments reopened_count, records reason.
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Complaint not found")

    # Verify authorization: only complaint author can confirm/reject
    if row["created_by_user_id"] != student.id:
        conn.close()
        raise HTTPException(status_code=403, detail="Only the student who reported this issue can verify its resolution.")

    now = datetime.now(timezone.utc).isoformat()
    previous_status = row["status"]

    if req.action == "confirm":
        new_status = "Resolved"
        cursor.execute("""
        UPDATE complaints
        SET status = ?, student_confirmed = 1, student_confirmed_at = ?,
            student_rating = ?, student_feedback = ?, updated_at = ?
        WHERE id = ?
        """, (new_status, now, req.rating or 5, req.feedback or "Resolution verified by student.", now, complaint_id))

        cursor.execute("""
        INSERT INTO complaint_history (
            complaint_id, previous_status, new_status, changed_by_user_id, changed_by_name, note, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            complaint_id,
            previous_status,
            new_status,
            student.id,
            student.name,
            f"Student confirmed resolution. Rating: {req.rating or 5}/5. Note: {req.feedback or 'Problem solved.'}",
            now
        ))

    elif req.action == "reject":
        new_status = "Reopened"
        reopen_msg = req.reopen_reason or "Issue still persists after technician visit."
        cursor.execute("""
        UPDATE complaints
        SET status = ?, student_confirmed = 0, warden_confirmed = 0,
            reopened_count = reopened_count + 1, updated_at = ?
        WHERE id = ?
        """, (new_status, now, complaint_id))

        cursor.execute("""
        INSERT INTO complaint_history (
            complaint_id, previous_status, new_status, changed_by_user_id, changed_by_name, note, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            complaint_id,
            previous_status,
            new_status,
            student.id,
            student.name,
            f"Resolution rejected by student: '{reopen_msg}'. Ticket reopened for re-inspection.",
            now
        ))
    else:
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid action. Must be 'confirm' or 'reject'.")

    conn.commit()

    cursor.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,))
    updated = dict(cursor.fetchone())
    conn.close()

    updated["missing_information"] = json.loads(updated.get("missing_information") or "[]")
    return updated

# --- COMPLAINT SUPPORT / UPVOTE ---
@app.post("/api/complaints/{complaint_id}/support")
def toggle_complaint_support(
    complaint_id: str,
    current_user: UserProfile = Depends(get_current_user)
):
    """Students can upvote/support an existing complaint to signal wide impact."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, supporters_count FROM complaints WHERE id = ?", (complaint_id,))
    complaint = cursor.fetchone()
    if not complaint:
        conn.close()
        raise HTTPException(status_code=404, detail="Complaint not found")

    cursor.execute(
        "SELECT id FROM complaint_supporters WHERE complaint_id = ? AND user_id = ?",
        (complaint_id, current_user.id)
    )
    existing = cursor.fetchone()
    now = datetime.now(timezone.utc).isoformat()

    if existing:
        cursor.execute("DELETE FROM complaint_supporters WHERE id = ?", (existing["id"],))
        cursor.execute("UPDATE complaints SET supporters_count = MAX(0, supporters_count - 1) WHERE id = ?", (complaint_id,))
        supported = False
    else:
        cursor.execute(
            "INSERT INTO complaint_supporters (complaint_id, user_id, created_at) VALUES (?, ?, ?)",
            (complaint_id, current_user.id, now)
        )
        cursor.execute("UPDATE complaints SET supporters_count = supporters_count + 1 WHERE id = ?", (complaint_id,))
        supported = True

    conn.commit()

    cursor.execute("SELECT supporters_count FROM complaints WHERE id = ?", (complaint_id,))
    new_count = cursor.fetchone()["supporters_count"]
    conn.close()

    return {"complaint_id": complaint_id, "supported": supported, "supporters_count": new_count}

# --- STATS ---
@app.get("/api/stats")
def get_dashboard_stats(current_user: UserProfile = Depends(get_current_user)):
    """Computes real database statistics including dual-resolution states."""
    conn = get_db()
    cursor = conn.cursor()

    # User-specific counts
    cursor.execute("SELECT COUNT(*) FROM complaints WHERE created_by_user_id = ?", (current_user.id,))
    my_total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE created_by_user_id = ? AND status = 'Submitted'", (current_user.id,))
    my_submitted = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE created_by_user_id = ? AND (status = 'Under Review' OR status = 'In Progress')", (current_user.id,))
    my_in_progress = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE created_by_user_id = ? AND status = 'Pending Student Confirmation'", (current_user.id,))
    my_pending_verify = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE created_by_user_id = ? AND status = 'Resolved'", (current_user.id,))
    my_resolved = cursor.fetchone()[0]

    # Global / Warden counts
    cursor.execute("SELECT COUNT(*) FROM complaints WHERE status != 'Resolved'")
    warden_open = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE (suggested_priority = 'Urgent' OR is_hazard = 1) AND status != 'Resolved'")
    warden_urgent = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'In Progress'")
    warden_in_progress = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'Pending Student Confirmation'")
    warden_pending_confirmation = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'Resolved'")
    warden_resolved = cursor.fetchone()[0]

    cursor.execute("""
    SELECT category, COUNT(*) as count
    FROM complaints
    GROUP BY category
    ORDER BY count DESC
    """)
    category_breakdown = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return {
        "student": {
            "total_submitted": my_total,
            "submitted": my_submitted,
            "in_progress": my_in_progress,
            "pending_verification": my_pending_verify,
            "resolved": my_resolved
        },
        "warden": {
            "total_open": warden_open,
            "urgent": warden_urgent,
            "in_progress": warden_in_progress,
            "pending_student_confirmation": warden_pending_confirmation,
            "resolved": warden_resolved,
            "category_breakdown": category_breakdown
        }
    }

# --- STATIC FILES & UPLOAD SERVING ---
@app.get("/static/uploads/{filename}")
def serve_uploaded_image(filename: str):
    """Serves uploaded complaint images across local and serverless environments."""
    candidate = UPLOADS_DIR / filename
    if candidate.is_file():
        return FileResponse(str(candidate))
    fallback = BASE_DIR / "frontend" / "uploads" / filename
    if fallback.is_file():
        return FileResponse(str(fallback))
    raise HTTPException(status_code=404, detail="Uploaded image not found")

frontend_dir = BASE_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

@app.get("/")
def serve_root():
    index_file = BASE_DIR / "frontend" / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Hostlur API Running. Frontend directory not found."}

@app.get("/{full_path:path}")
def serve_spa(full_path: str):
    if full_path.startswith("api/") or full_path.startswith("static/"):
        raise HTTPException(status_code=404, detail="Not found")

    file_candidate = BASE_DIR / "frontend" / full_path
    if file_candidate.is_file():
        return FileResponse(str(file_candidate))

    index_file = BASE_DIR / "frontend" / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    raise HTTPException(status_code=404, detail="Page not found")
