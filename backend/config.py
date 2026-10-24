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

# Allowed Business Values
ALLOWED_CATEGORIES = [
    "Wi-Fi and Internet",
    "Water Supply",
    "Electricity",
    "Food Quality",
    "Cleanliness",
    "Maintenance",
    "Safety",
    "Other"
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
    "Resolved"
]

HOSTEL_BLOCKS = [
    "Block A (Boys)",
    "Block B (Boys)",
    "Block C (Girls)",
    "Block D (Girls)",
    "PG Block"
]

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
