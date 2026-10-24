import sqlite3
import json
import uuid
import hashlib
import secrets
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from backend.config import SQLITE_PATH, ALLOWED_CATEGORIES

def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """Generates PBKDF2-HMAC-SHA256 hash with random 16-byte hex salt."""
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100_000
    )
    return hashed.hex(), salt

def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Verifies a password against stored PBKDF2 hash using constant-time comparison."""
    new_hash, _ = hash_password(password, salt)
    import hmac
    return hmac.compare_digest(new_hash, stored_hash)

def get_db():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def run_migrations(cursor):
    """Safely adds missing columns and migrates category names to the authoritative 10 categories."""
    # Check users columns
    cursor.execute("PRAGMA table_info(users)")
    user_cols = [r[1] for r in cursor.fetchall()]
    if "password_hash" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
    if "salt" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN salt TEXT")
    if "floor" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN floor TEXT")
    if "phone" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN phone TEXT")

    # Check complaints columns
    cursor.execute("PRAGMA table_info(complaints)")
    complaint_cols = [r[1] for r in cursor.fetchall()]
    if "image_url" not in complaint_cols:
        cursor.execute("ALTER TABLE complaints ADD COLUMN image_url TEXT")
    if "floor" not in complaint_cols:
        cursor.execute("ALTER TABLE complaints ADD COLUMN floor TEXT")
    if "warden_confirmed" not in complaint_cols:
        cursor.execute("ALTER TABLE complaints ADD COLUMN warden_confirmed INTEGER DEFAULT 0")
    if "warden_confirmed_at" not in complaint_cols:
        cursor.execute("ALTER TABLE complaints ADD COLUMN warden_confirmed_at TEXT")
    if "warden_note" not in complaint_cols:
        cursor.execute("ALTER TABLE complaints ADD COLUMN warden_note TEXT")
    if "student_confirmed" not in complaint_cols:
        cursor.execute("ALTER TABLE complaints ADD COLUMN student_confirmed INTEGER DEFAULT 0")
    if "student_confirmed_at" not in complaint_cols:
        cursor.execute("ALTER TABLE complaints ADD COLUMN student_confirmed_at TEXT")
    if "student_rating" not in complaint_cols:
        cursor.execute("ALTER TABLE complaints ADD COLUMN student_rating INTEGER")
    if "student_feedback" not in complaint_cols:
        cursor.execute("ALTER TABLE complaints ADD COLUMN student_feedback TEXT")
    if "reopened_count" not in complaint_cols:
        cursor.execute("ALTER TABLE complaints ADD COLUMN reopened_count INTEGER DEFAULT 0")

    # Migrate legacy category names in existing records
    cat_mapping = {
        "Wi-Fi and Internet": "Internet & Networking",
        "Electricity": "Electricity & Lighting",
        "Water Supply": "Plumbing & Water Supply",
        "Cleanliness": "Cleaning & Hygiene",
        "Maintenance": "Civil & Structural Damage",
        "Food Quality": "Mess & Food",
        "Safety": "Safety & Security",
        "Other": "Other / Unclear"
    }
    for old_cat, new_cat in cat_mapping.items():
        cursor.execute("UPDATE complaints SET category = ? WHERE category = ?", (new_cat, old_cat))

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
        floor TEXT,
        room TEXT,
        phone TEXT,
        password_hash TEXT,
        salt TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        role TEXT NOT NULL,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS complaints (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        category TEXT NOT NULL,
        hostel_block TEXT NOT NULL,
        floor TEXT,
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
        image_url TEXT,
        warden_confirmed INTEGER DEFAULT 0,
        warden_confirmed_at TEXT,
        warden_note TEXT,
        student_confirmed INTEGER DEFAULT 0,
        student_confirmed_at TEXT,
        student_rating INTEGER,
        student_feedback TEXT,
        reopened_count INTEGER DEFAULT 0,
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

    CREATE TABLE IF NOT EXISTS mess_menu (
        day_of_week TEXT PRIMARY KEY,
        breakfast TEXT NOT NULL,
        lunch TEXT NOT NULL,
        snacks TEXT NOT NULL,
        dinner TEXT NOT NULL,
        special_note TEXT
    );

    CREATE TABLE IF NOT EXISTS announcements (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        category TEXT NOT NULL, -- 'Curfew', 'Maintenance', 'Mess', 'General'
        created_at TEXT NOT NULL,
        active INTEGER DEFAULT 1
    );

    CREATE INDEX IF NOT EXISTS idx_complaints_user ON complaints (created_by_user_id);
    CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints (status);
    CREATE INDEX IF NOT EXISTS idx_complaints_category ON complaints (category);
    CREATE INDEX IF NOT EXISTS idx_complaints_block ON complaints (hostel_block);
    CREATE INDEX IF NOT EXISTS idx_complaints_created_at ON complaints (created_at);
    """)

    # Run column and data migrations
    run_migrations(cursor)

    # Seed Default Demo Users with secure passwords if needed
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        now = datetime.now(timezone.utc).isoformat()
        student_hash, student_salt = hash_password("student123")
        warden_hash, warden_salt = hash_password("warden123")

        demo_users = [
            ("student-aarav", "Aarav Sharma", "aarav@campus.edu", "student", "Block B (Boys)", "3rd Floor", "B-302", "+91-98765-11001", student_hash, student_salt, now),
            ("student-priya", "Priya Patel", "priya@campus.edu", "student", "Block C (Girls)", "2nd Floor", "C-204", "+91-98765-11002", student_hash, student_salt, now),
            ("warden-sharma", "Dr. R. K. Sharma", "warden.sharma@campus.edu", "warden", "All Blocks", "Admin Wing", "Warden Office", "+91-98765-43210", warden_hash, warden_salt, now)
        ]
        cursor.executemany(
            "INSERT INTO users (id, name, email, role, hostel_block, floor, room, phone, password_hash, salt, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            demo_users
        )
    else:
        # Ensure existing demo users have valid hashes
        cursor.execute("SELECT id, password_hash FROM users")
        for u in cursor.fetchall():
            if not u["password_hash"]:
                p_hash, p_salt = hash_password("warden123" if "warden" in u["id"] else "student123")
                cursor.execute("UPDATE users SET password_hash = ?, salt = ?, floor = COALESCE(floor, '3rd Floor'), phone = COALESCE(phone, '+91-98765-00000') WHERE id = ?", (p_hash, p_salt, u["id"]))

    # Seed initial realistic complaints if complaints table empty
    cursor.execute("SELECT COUNT(*) FROM complaints")
    if cursor.fetchone()[0] == 0:
        demo_complaints = [
            (
                "CMP-2026-101",
                "Wi-Fi disconnects repeatedly on 3rd floor corridor",
                "The Wi-Fi access point near Room 302 keeps dropping connection every 10 minutes since yesterday evening. Students cannot complete their online submissions.",
                "Internet & Networking",
                "Block B (Boys)",
                "3rd Floor",
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
                None,
                0, None, None,
                0, None, None, None,
                0,
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
                "Electricity & Lighting",
                "Block B (Boys)",
                "2nd Floor",
                "2nd Floor Common Bathroom #2",
                "Discovered 30 mins ago",
                "Urgent",
                "Urgent",
                "Pending Student Confirmation",
                "Electrical sparking caused by water leak dripping into power outlet in bathroom.",
                json.dumps([]),
                1,
                "Exposed sparking near electrical power socket with water leak present.",
                1,
                None,
                1, "2026-10-24T12:05:00Z", "Emergency electrician isolated circuit and replaced geyser inlet pipe. Ready for verification.",
                0, None, None, None,
                0,
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
                "Plumbing & Water Supply",
                "Block C (Girls)",
                "4th Floor",
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
                None,
                0, None, None,
                0, None, None, None,
                0,
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
                "Civil & Structural Damage",
                "Block C (Girls)",
                "2nd Floor",
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
                None,
                1, "2026-10-23T15:30:00Z", "Carpenter replaced latch assembly.",
                1, "2026-10-23T16:00:00Z", 5, "Latch works smoothly now! Thank you.",
                0,
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
            id, title, description, category, hostel_block, floor, location, duration,
            suggested_priority, confirmed_priority, status, summary,
            missing_information, is_hazard, hazard_reason, ai_analyzed,
            image_url, warden_confirmed, warden_confirmed_at, warden_note,
            student_confirmed, student_confirmed_at, student_rating, student_feedback,
            reopened_count, created_by_user_id, created_by_name, created_by_room,
            supporters_count, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, demo_complaints)

    # Seed 7-Day Mess Menu if empty
    cursor.execute("SELECT COUNT(*) FROM mess_menu")
    if cursor.fetchone()[0] == 0:
        weekly_menu = [
            ("Monday", "Poha with Sev, Boiled Eggs / Banana, Tea & Coffee", "Rajma Masala, Steamed Basmati Rice, Jeera Aloo, Roti, Salad & Curd", "Vegetable Cutlets, Green Chutney, Masala Chai", "Paneer Butter Masala, Dal Tadka, Phulka, Pulao, Gulab Jamun", "Special North Indian Thali"),
            ("Tuesday", "Idli Sambar, Medu Vada, Coconut Chutney, Fresh Fruits", "Chole Bhature, Boondi Raita, Onion Salad, Lemon Pickle", "Crispy Samosa with Mint Dip, Tea & Coffee", "Kadai Chicken / Kadai Mushroom, Dal Makhani, Tawa Paratha, Jeera Rice, Kheer", "Feast Night"),
            ("Wednesday", "Aloo Paratha with White Butter, Curd, Pickle, Tea", "Mix Vegetable Curry, Yellow Dal Fry, Rice, Chapati, Papad", "Pav Bhaji, Chopped Onions, Hot Chai", "Egg Curry / Malai Kofta, Dal Fry, Steamed Rice, Phulka, Moong Dal Halwa", "Chef's Special"),
            ("Thursday", "Masala Dosa, Sambhar, Tomato Chutney, Boiled Sprouts", "Kadhi Pakoda, Khichdi / Steamed Rice, Aloo Bhindi, Chapati", "Onion Pakoda, Ginger Chai, Marie Biscuits", "Soya Chaap Curry, Dal Tadka, Ghee Rice, Roti, Fruit Custard", "Nutritious & Light"),
            ("Friday", "Uttapam, Coconut Chutney, Vegetable Sambhar, Milk & Tea", "Dum Aloo Kashmiri, Dal Makhani, Veg Pulao, Missi Roti, Curd", "Bhel Puri / Sev Puri, Tea & Coffee", "Butter Chicken / Shahi Paneer, Garlic Naan / Tandoori Roti, Biryani Rice, Ice Cream", "Friday Night Special"),
            ("Saturday", "Puri Bhaji (Aloo Tamatar), Sooji Halwa, Tea & Coffee", "South Indian Meals: Sambhar, Rasam, Poriyal, Curd Rice, Appalam", "Bun Maska / Veg Puff, Filter Coffee", "Veg / Egg / Chicken Hakka Noodles, Manchurian Gravy, Fried Rice, Sweet Corn Soup", "Indo-Chinese Special"),
            ("Sunday", "Chole Kulche, Pickled Chilies, Fresh Orange Juice / Tea", "Special Hyderabadi Dum Biryani (Chicken & Veg), Mirchi Ka Salan, Raita", "Sweet Corn Chaat, Cookies, Masala Chai", "Dal Palak, Aloo Gobhi Matar, Phulka, Jeera Rice, Rasgulla", "Sunday Grand Buffet")
        ]
        cursor.executemany("""
        INSERT INTO mess_menu (day_of_week, breakfast, lunch, snacks, dinner, special_note)
        VALUES (?, ?, ?, ?, ?, ?)
        """, weekly_menu)

    # Seed Announcements & Curfew Notice if empty
    cursor.execute("SELECT COUNT(*) FROM announcements")
    if cursor.fetchone()[0] == 0:
        now = datetime.now(timezone.utc).isoformat()
        demo_announcements = [
            ("ANN-001", "Campus Curfew & Gate Timing Reminder", "Strict reminder: Weekday curfew is 10:00 PM and Weekend curfew is 11:00 PM. Gate registers will be inspected by the Chief Warden.", "Curfew", now, 1),
            ("ANN-002", "Overhead Water Tank Cleaning This Sunday", "Block B & C overhead tanks will be sanitized on Sunday 10:00 AM – 01:00 PM. Water supply will resume normally by 01:30 PM.", "Maintenance", now, 1),
            ("ANN-003", "Hostel Mess Feedback Committee Meeting", "Student mess committee meeting will be held on Wednesday 05:30 PM in the Central Dining Hall. Suggestions welcome.", "Mess", now, 1)
        ]
        cursor.executemany("""
        INSERT INTO announcements (id, title, content, category, created_at, active)
        VALUES (?, ?, ?, ?, ?, ?)
        """, demo_announcements)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Upgraded database schema and seeded new features successfully.")
