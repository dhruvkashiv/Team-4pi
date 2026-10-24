import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import (
    BASE_DIR,
    ALLOWED_CATEGORIES,
    ALLOWED_PRIORITIES,
    ALLOWED_STATUSES,
    HOSTEL_BLOCKS,
    GEMMA_MODEL
)
from backend.database import get_db, init_db
from backend.models import (
    AIAnalyzeRequest,
    AIAnalysisResult,
    ComplaintCreate,
    StatusUpdateRequest,
    UserProfile
)
from backend.auth import get_current_user, require_warden
from backend.ai_service import analyze_complaint_with_gemma

app = FastAPI(
    title="Hostlur API",
    description="Hostel Life, Simplified. AI-assisted hostel complaint management system.",
    version="1.0.0"
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

# --- HEALTH & CONFIG ---
@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Hostlur",
        "ai_model": GEMMA_MODEL,
        "database": "SQLite (WAL)",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# --- AUTH & USERS ---
@app.get("/api/auth/me", response_model=UserProfile)
def get_me(user: UserProfile = Depends(get_current_user)):
    return user

@app.get("/api/users")
def list_demo_users():
    """Returns available demo personas for quick switching in hackathon UI."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, role, hostel_block, room FROM users ORDER BY role DESC, name ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# --- AI ANALYSIS ---
@app.post("/api/ai/analyze", response_model=AIAnalysisResult)
async def analyze_complaint(
    req: AIAnalyzeRequest,
    current_user: UserProfile = Depends(get_current_user)
):
    """
    Analyzes student complaint using Google's Gemma model.
    Extracts category, priority, concise summary, and checks for hazards.
    """
    if len(req.description.strip()) < 5:
        raise HTTPException(status_code=400, detail="Description is too short for AI analysis.")

    result = await analyze_complaint_with_gemma(
        description=req.description,
        hostel_block=req.hostel_block or current_user.hostel_block,
        location=req.location
    )
    return result

# --- RELATED COMPLAINTS (DUPLICATE DETECTION) ---
@app.get("/api/complaints/related")
def get_related_complaints(
    block: str = Query(..., description="Hostel block"),
    category: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    current_user: UserProfile = Depends(get_current_user)
):
    """
    Finds existing open complaints in the same block/category so students can
    support an existing issue instead of creating redundant duplicates.
    """
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
    """Creates a new hostel complaint with real database persistence and AI analysis."""
    # Validate category
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
            # AI failure must NEVER block saving student complaint
            pass

    now = datetime.now(timezone.utc).isoformat()
    complaint_id = f"CMP-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:5].upper()}"

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO complaints (
        id, title, description, category, hostel_block, location, duration,
        suggested_priority, confirmed_priority, status, summary,
        missing_information, is_hazard, hazard_reason, ai_analyzed,
        created_by_user_id, created_by_name, created_by_room, supporters_count,
        created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        complaint_id,
        complaint.title,
        complaint.description,
        complaint.category,
        complaint.hostel_block,
        complaint.location,
        complaint.duration,
        suggested_priority,
        suggested_priority,  # initial confirmed priority matches suggestion
        "Submitted",
        summary,
        json.dumps(missing_info),
        1 if is_hazard else 0,
        hazard_reason,
        ai_analyzed,
        current_user.id,
        current_user.name,
        current_user.room,
        0,
        now,
        now
    ))

    # Log initial status in history
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

    # Retrieve created record
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
    """
    Returns complaints authorized for current user.
    Students see their own complaints when mine=true, or all hostel complaints.
    Wardens see all complaints across their authorized blocks.
    """
    conn = get_db()
    cursor = conn.cursor()

    query = "SELECT * FROM complaints WHERE 1=1"
    params = []

    # Student viewing their own complaints
    if mine:
        query += " AND created_by_user_id = ?"
        params.append(current_user.id)

    # Filtering by category
    if category and category in ALLOWED_CATEGORIES:
        query += " AND category = ?"
        params.append(category)

    # Filtering by status
    if status_filter and status_filter in ALLOWED_STATUSES:
        query += " AND status = ?"
        params.append(status_filter)

    # Filtering by block
    if block and block in HOSTEL_BLOCKS:
        query += " AND hostel_block = ?"
        params.append(block)

    # Filtering by priority
    if priority and priority in ALLOWED_PRIORITIES:
        query += " AND (suggested_priority = ? OR confirmed_priority = ?)"
        params.extend([priority, priority])

    # Text search
    if search and len(search.strip()) > 0:
        query += " AND (title LIKE ? OR description LIKE ? OR location LIKE ? OR summary LIKE ?)"
        term = f"%{search.strip()}%"
        params.extend([term, term, term, term])

    query += " ORDER BY is_hazard DESC, created_at DESC"
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]

    for r in rows:
        r["missing_information"] = json.loads(r.get("missing_information") or "[]")
        # Check if current user has supported this complaint
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
    """Returns single complaint details with timeline history and supporters."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Complaint not found")

    complaint = dict(row)
    complaint["missing_information"] = json.loads(complaint.get("missing_information") or "[]")

    # History timeline
    cursor.execute("""
    SELECT id, previous_status, new_status, changed_by_user_id, changed_by_name, note, created_at
    FROM complaint_history
    WHERE complaint_id = ?
    ORDER BY id ASC
    """, (complaint_id,))
    complaint["history"] = [dict(h) for h in cursor.fetchall()]

    # Check if supported
    cursor.execute(
        "SELECT 1 FROM complaint_supporters WHERE complaint_id = ? AND user_id = ?",
        (complaint_id, current_user.id)
    )
    complaint["has_supported"] = cursor.fetchone() is not None

    conn.close()
    return complaint

@app.patch("/api/complaints/{complaint_id}/status")
def update_complaint_status(
    complaint_id: str,
    req: StatusUpdateRequest,
    warden: UserProfile = Depends(require_warden)
):
    """
    Updates complaint status. Strictly restricted to authorized wardens.
    Maintains complete audit history.
    """
    if req.status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {ALLOWED_STATUSES}")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT status, confirmed_priority FROM complaints WHERE id = ?", (complaint_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Complaint not found")

    previous_status = row["status"]
    now = datetime.now(timezone.utc).isoformat()

    new_priority = req.confirmed_priority if req.confirmed_priority in ALLOWED_PRIORITIES else row["confirmed_priority"]

    cursor.execute("""
    UPDATE complaints
    SET status = ?, confirmed_priority = ?, updated_at = ?
    WHERE id = ?
    """, (req.status, new_priority, now, complaint_id))

    cursor.execute("""
    INSERT INTO complaint_history (
        complaint_id, previous_status, new_status, changed_by_user_id, changed_by_name, note, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        complaint_id,
        previous_status,
        req.status,
        warden.id,
        warden.name,
        req.note or f"Status changed from {previous_status} to {req.status}",
        now
    ))

    conn.commit()

    cursor.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,))
    updated_complaint = dict(cursor.fetchone())
    conn.close()

    updated_complaint["missing_information"] = json.loads(updated_complaint.get("missing_information") or "[]")
    return updated_complaint

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
        # Remove support
        cursor.execute("DELETE FROM complaint_supporters WHERE id = ?", (existing["id"],))
        cursor.execute("UPDATE complaints SET supporters_count = MAX(0, supporters_count - 1) WHERE id = ?", (complaint_id,))
        supported = False
    else:
        # Add support
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

@app.get("/api/stats")
def get_dashboard_stats(current_user: UserProfile = Depends(get_current_user)):
    """Computes real database statistics for both student and warden views."""
    conn = get_db()
    cursor = conn.cursor()

    # User-specific counts
    cursor.execute("SELECT COUNT(*) FROM complaints WHERE created_by_user_id = ?", (current_user.id,))
    my_total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE created_by_user_id = ? AND status = 'Submitted'", (current_user.id,))
    my_submitted = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE created_by_user_id = ? AND (status = 'Under Review' OR status = 'In Progress')", (current_user.id,))
    my_in_progress = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE created_by_user_id = ? AND status = 'Resolved'", (current_user.id,))
    my_resolved = cursor.fetchone()[0]

    # Global / Warden counts
    cursor.execute("SELECT COUNT(*) FROM complaints WHERE status != 'Resolved'")
    warden_open = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE (suggested_priority = 'Urgent' OR is_hazard = 1) AND status != 'Resolved'")
    warden_urgent = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'In Progress'")
    warden_in_progress = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'Resolved'")
    warden_resolved = cursor.fetchone()[0]

    # Breakdown by category
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
            "resolved": my_resolved
        },
        "warden": {
            "total_open": warden_open,
            "urgent": warden_urgent,
            "in_progress": warden_in_progress,
            "resolved": warden_resolved,
            "category_breakdown": category_breakdown
        }
    }

# --- STATIC FILES FOR FRONTEND ---
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
    # If requesting static assets or api, let normal routing handle it
    if full_path.startswith("api/") or full_path.startswith("static/"):
        raise HTTPException(status_code=404, detail="Not found")

    file_candidate = BASE_DIR / "frontend" / full_path
    if file_candidate.is_file():
        return FileResponse(str(file_candidate))

    index_file = BASE_DIR / "frontend" / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    raise HTTPException(status_code=404, detail="Page not found")
