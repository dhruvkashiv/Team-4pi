import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file from project root
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "true").lower() in ("true", "1", "yes")

# Google AI Studio API Configuration
GOOGLE_AI_API_KEY = os.getenv("GOOGLE_AI_API_KEY", "").strip()
GEMMA_MODEL = os.getenv("GEMMA_MODEL", "gemma-4-26b-a4b-it").strip()

# Database
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/hostlur.db")
SQLITE_PATH = str(BASE_DIR / "hostlur.db")

# Static & Uploads Directory
UPLOADS_DIR = BASE_DIR / "frontend" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Authoritative 10 Standardized Categories
ALLOWED_CATEGORIES = [
    "Electricity & Lighting",
    "Plumbing & Water Supply",
    "Washroom & Sanitation",
    "Cleaning & Hygiene",
    "Furniture & Fixtures",
    "Civil & Structural Damage",
    "Internet & Networking",
    "Mess & Food",
    "Safety & Security",
    "Other / Unclear"
]

ALLOWED_PRIORITIES = [
    "Low",
    "Medium",
    "High",
    "Urgent"
]

ALLOWED_STATUSES = [
    "Submitted",
    "Under Review",
    "In Progress",
    "Pending Student Confirmation",
    "Resolved",
    "Reopened"
]

HOSTEL_BLOCKS = [
    "Block A (Boys)",
    "Block B (Boys)",
    "Block C (Girls)",
    "Block D (Girls)",
    "PG Block"
]

# Configurable Hostel Contact Details
HOSTEL_CONTACTS = {
    "chief_warden": {
        "name": os.getenv("WARDEN_NAME", "Dr. R. K. Sharma"),
        "role": "Chief Hostel Warden",
        "email": os.getenv("WARDEN_EMAIL", "warden.sharma@campus.edu"),
        "phone": os.getenv("WARDEN_PHONE", "+91-98765-43210"),
        "office": "Central Administration Block, Room 102",
        "office_hours": "04:00 PM – 06:30 PM (Mon–Fri)"
    },
    "caretaker_block_b": {
        "name": os.getenv("CARETAKER_B_NAME", "Mr. Suresh Kumar"),
        "role": "Hostel Caretaker (Boys Wing)",
        "email": os.getenv("CARETAKER_B_EMAIL", "caretaker.boys@campus.edu"),
        "phone": os.getenv("CARETAKER_B_PHONE", "+91-98765-43211"),
        "office": "Block B Ground Floor Helpdesk",
        "office_hours": "08:00 AM – 08:00 PM (Daily)"
    },
    "caretaker_block_c": {
        "name": os.getenv("CARETAKER_C_NAME", "Mrs. Sunita Verma"),
        "role": "Hostel Caretaker (Girls Wing)",
        "email": os.getenv("CARETAKER_C_EMAIL", "caretaker.girls@campus.edu"),
        "phone": os.getenv("CARETAKER_C_PHONE", "+91-98765-43212"),
        "office": "Block C Ground Floor Helpdesk",
        "office_hours": "08:00 AM – 08:00 PM (Daily)"
    },
    "emergency": {
        "helpline": os.getenv("EMERGENCY_HELPLINE", "+91-112-HOSTEL (Toll Free)"),
        "campus_ambulance": os.getenv("CAMPUS_AMBULANCE", "+91-98765-43299"),
        "campus_security": os.getenv("CAMPUS_SECURITY", "+91-98765-43200")
    }
}

# Configurable Mess Timings
MESS_TIMINGS = {
    "breakfast": {"title": "Breakfast", "time": os.getenv("MESS_BREAKFAST", "07:30 AM – 09:30 AM")},
    "lunch": {"title": "Lunch", "time": os.getenv("MESS_LUNCH", "12:30 PM – 02:30 PM")},
    "snacks": {"title": "Evening Snacks", "time": os.getenv("MESS_SNACKS", "05:00 PM – 06:30 PM")},
    "dinner": {"title": "Dinner", "time": os.getenv("MESS_DINNER", "07:45 PM – 09:45 PM")}
}

# Configurable Curfew & Hostel Rules
CURFEW_RULES = {
    "weekday": os.getenv("CURFEW_WEEKDAY", "10:00 PM (Sunday – Thursday)"),
    "weekend": os.getenv("CURFEW_WEEKEND", "11:00 PM (Friday & Saturday)"),
    "late_entry_policy": "Late entry allowed only with signed Warden Night-Pass or pre-approved digital slip.",
    "gate_closing": "Main campus gates lock promptly at 11:15 PM.",
    "visitor_hours": "04:30 PM – 07:30 PM in Common Ground Floor Lobby only."
}

# Deterministic Hazard Keywords for Emergency Safety Checking
HAZARD_KEYWORDS = [
    "fire",
    "smoke",
    "spark",
    "sparking",
    "burning",
    "short circuit",
    "live wire",
    "exposed wire",
    "electric shock",
    "gas leak",
    "smell gas",
    "ceiling collapse",
    "falling concrete",
    "structural damage",
    "explosion",
    "flooding into electrical"
]
