from fastapi import Header, HTTPException, status
from backend.database import get_db
from backend.models import UserProfile

def get_current_user(x_user_id: str = Header(default="student-aarav")) -> UserProfile:
    """
    Retrieves the current user based on the session header X-User-Id.
    Defaults to the demo student account for rapid evaluation.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, role, hostel_block, room FROM users WHERE id = ?", (x_user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user session or user not found."
        )

    return UserProfile(
        id=row["id"],
        name=row["name"],
        email=row["email"],
        role=row["role"],
        hostel_block=row["hostel_block"],
        room=row["room"]
    )

def require_warden(x_user_id: str = Header(default="student-aarav")) -> UserProfile:
    """Enforces server-side warden role check."""
    user = get_current_user(x_user_id)
    if user.role != "warden":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Only hostel wardens and administrators can perform this action."
        )
    return user
