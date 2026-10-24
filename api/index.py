"""
Vercel Serverless Entrypoint for Hostlur FastAPI Backend
Exposes ASGI 'app' for @vercel/python runtime.
"""
import sys
import os
from pathlib import Path

# Add project root to sys.path so 'backend.*' imports resolve cleanly
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Mark environment as Vercel
os.environ["VERCEL"] = "1"

from backend.main import app
