import sqlite3
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from backend.config import SQLITE_PATH

def get_db():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        role TEXT NOT NULL, -- 'student' or 'warden'
        hostel_block TEXT,
        room TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS complaints (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        category TEXT NOT NULL,
        hostel_block TEXT NOT NULL,
        location TEXT NOT NULL,
        duration TEXT,
        suggested_priority TEXT DEFAULT 'Medium',
        confirmed_priority TEXT,
        status TEXT DEFAULT 'Submitted',
        summary TEXT,
        missing_information TEXT, -- JSON array
        is_hazard INTEGER DEFAULT 0,
        hazard_reason TEXT,
        ai_analyzed INTEGER DEFAULT 0,
        created_by_user_id TEXT NOT NULL,
        created_by_name TEXT NOT NULL,
        created_by_room TEXT,
        supporters_count INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (created_by_user_id) REFERENCES users (id)
    );

    CREATE TABLE IF NOT EXISTS complaint_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        complaint_id TEXT NOT NULL,
        previous_status TEXT,
        new_status TEXT NOT NULL,
        changed_by_user_id TEXT NOT NULL,
        changed_by_name TEXT NOT NULL,
        note TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (complaint_id) REFERENCES complaints (id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS complaint_supporters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        complaint_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(complaint_id, user_id),
        FOREIGN KEY (complaint_id) REFERENCES complaints (id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_complaints_user ON complaints (created_by_user_id);
    CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints (status);
    CREATE INDEX IF NOT EXISTS idx_complaints_category ON complaints (category);
    CREATE INDEX IF NOT EXISTS idx_complaints_block ON complaints (hostel_block);
    CREATE INDEX IF NOT EXISTS idx_complaints_created_at ON complaints (created_at);
    """)

    # Seed Default Demo Users if empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        now = datetime.now(timezone.utc).isoformat()
        demo_users = [
            ("student-aarav", "Aarav Sharma", "aarav@campus.edu", "student", "Block B (Boys)", "B-302", now),
            ("student-priya", "Priya Patel", "priya@campus.edu", "student", "Block C (Girls)", "C-204", now),
            ("warden-sharma", "Dr. R. K. Sharma", "warden.sharma@campus.edu", "warden", "All Blocks", "Warden Office", now)
        ]
        cursor.executemany(
            "INSERT INTO users (id, name, email, role, hostel_block, room, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            demo_users
        )

        # Seed initial realistic complaints for hackathon demo
        demo_complaints = [
            (
                "CMP-2026-101",
                "Wi-Fi disconnects repeatedly on 3rd floor corridor",
                "The Wi-Fi access point near Room 302 keeps dropping connection every 10 minutes since yesterday evening. Students cannot complete their online submissions.",
                "Wi-Fi and Internet",
                "Block B (Boys)",
                "3rd Floor, West Wing corridor near B-302",
                "Since yesterday evening",
                "High",
                "High",
                "In Progress",
                "Intermittent Wi-Fi connectivity dropouts affecting multiple rooms on 3rd floor west wing.",
                json.dumps([]),
                0,
                None,
                1,
                "student-aarav",
                "Aarav Sharma",
                "B-302",
                3,
                "2026-10-24T09:15:00Z",
                "2026-10-24T11:30:00Z"
            ),
            (
                "CMP-2026-102",
                "Geyser leaking water and sparking near switchboard",
                "The water geyser in bathroom #2 on 2nd floor has a water leak that is dripping onto the adjacent power socket. Sparks were visible when turning it on.",
                "Electricity",
                "Block B (Boys)",
                "2nd Floor Common Bathroom #2",
                "Discovered 30 mins ago",
                "Urgent",
                "Urgent",
                "Under Review",
                "Electrical sparking caused by water leak dripping into power outlet in bathroom.",
                json.dumps([]),
                1,
                "Exposed sparking near electrical power socket with water leak present.",
                1,
                "student-aarav",
                "Aarav Sharma",
                "B-302",
                7,
                "2026-10-24T12:00:00Z",
                "2026-10-24T12:05:00Z"
            ),
            (
                "CMP-2026-103",
                "Low water pressure in 4th floor showers",
                "Water pressure in Block C 4th floor washrooms is extremely low in the morning between 7 AM and 9 AM.",
                "Water Supply",
                "Block C (Girls)",
                "4th Floor Common Washroom",
                "Past 3 days",
                "Medium",
                "Medium",
                "Submitted",
                "Morning low water pressure issue affecting 4th floor showers.",
                json.dumps(["Exact shower stalls affected"]),
                0,
                None,
                1,
                "student-priya",
                "Priya Patel",
                "C-204",
                1,
                "2026-10-24T08:00:00Z",
                "2026-10-24T08:00:00Z"
            ),
            (
                "CMP-2026-104",
                "Broken window latch during heavy rain",
                "The latch on the window in Room 204 is broken and does not stay locked. Rainwater enters the room during storms.",
                "Maintenance",
                "Block C (Girls)",
                "Room C-204",
                "1 week",
                "Low",
                "Low",
                "Resolved",
                "Window lock replacement requested for room C-204.",
                json.dumps([]),
                0,
                None,
                1,
                "student-priya",
                "Priya Patel",
                "C-204",
                0,
                "2026-10-22T14:00:00Z",
                "2026-10-23T16:00:00Z"
            )
        ]

        cursor.executemany("""
        INSERT INTO complaints (
            id, title, description, category, hostel_block, location, duration,
            suggested_priority, confirmed_priority, status, summary,
            missing_information, is_hazard, hazard_reason, ai_analyzed,
            created_by_user_id, created_by_name, created_by_room, supporters_count,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, demo_complaints)

        # Seed history
        history_records = [
            ("CMP-2026-101", "Submitted", "Under Review", "warden-sharma", "Dr. R. K. Sharma", "Acknowledged. IT network team notified.", "2026-10-24T10:00:00Z"),
            ("CMP-2026-101", "Under Review", "In Progress", "warden-sharma", "Dr. R. K. Sharma", "Technician dispatched to replace router.", "2026-10-24T11:30:00Z"),
            ("CMP-2026-102", "Submitted", "Under Review", "warden-sharma", "Dr. R. K. Sharma", "EMERGENCY: Electrician instructed to shut off 2nd floor bathroom circuit breaker.", "2026-10-24T12:05:00Z"),
            ("CMP-2026-104", "Submitted", "Resolved", "warden-sharma", "Dr. R. K. Sharma", "Carpenter replaced latch assembly.", "2026-10-23T16:00:00Z"),
        ]
        cursor.executemany("""
        INSERT INTO complaint_history (
            complaint_id, previous_status, new_status, changed_by_user_id, changed_by_name, note, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, history_records)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
