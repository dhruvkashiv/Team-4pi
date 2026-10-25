"""
Vercel Serverless Entrypoint for Hostlur FastAPI Backend
Exposes ASGI 'app' for @vercel/python runtime with path restoration & self-healing DB.
"""
import sys
import os
import urllib.parse
from pathlib import Path

# Add project root to sys.path so 'backend.*' imports resolve cleanly
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Mark environment as Vercel
os.environ["VERCEL"] = "1"

from backend.main import app as fastapi_app
from backend.database import init_db

# Self-healing database initialization on serverless cold start
try:
    init_db()
except Exception as e:
    print(f"[Hostlur Vercel] Database initialization warning: {e}")

class VercelASGIAdapter:
    """
    ASGI middleware ensuring that requests rewritten to /api/index.py,
    or paths with /api stripped by Vercel edge proxy, correctly resolve
    to the target FastAPI route.
    """
    def __init__(self, inner_app):
        self.inner_app = inner_app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            path = scope.get("path", "")
            raw_headers = dict(scope.get("headers", []))
            headers = {
                k.decode("latin1").lower(): v.decode("latin1")
                for k, v in raw_headers.items()
            }

            # Check headers injected by Vercel / edge proxies for original requested path
            orig_candidate = (
                headers.get("x-matched-path")
                or headers.get("x-forwarded-uri")
                or headers.get("x-original-url")
                or headers.get("x-rewrite-url")
            )

            # Check if query string contains explicit __path__ passed by rewrite rule
            query_str = scope.get("query_string", b"").decode("latin1")
            if "__path__=" in query_str:
                parsed_qs = urllib.parse.parse_qs(query_str, keep_blank_values=True)
                custom_path = parsed_qs.pop("__path__", [None])[0]
                if custom_path:
                    orig_candidate = f"/api/{custom_path.lstrip('/')}"
                    # Reconstruct clean query string without __path__
                    reconstructed = urllib.parse.urlencode(
                        [(k, v) for k, vs in parsed_qs.items() for v in vs]
                    )
                    scope["query_string"] = reconstructed.encode("latin1")

            # If path was rewritten to entrypoint file (e.g. /api/index.py, /api/index, /index.py)
            if path in ("/api/index.py", "/api/index", "/index.py", "/index", "/api", "/api/"):
                if orig_candidate:
                    path = orig_candidate.split("?")[0]
                else:
                    path = "/api/health"

            # Keep frontend paths available when Vercel routes them through this function.
            is_frontend_path = (
                path == "/"
                or path.startswith(("/static/", "/css/", "/js/", "/uploads/"))
            )
            if path.startswith("/uploads/"):
                path = path.replace("/uploads/", "/static/uploads/", 1)

            # If path lacks /api prefix and is not a frontend path, normalize to /api/...
            if not path.startswith("/api") and not is_frontend_path:
                path = f"/api{path}" if path.startswith("/") else f"/api/{path}"

            scope["path"] = path
            scope["raw_path"] = path.encode("latin1")

        await self.inner_app(scope, receive, send)

# Export 'app' for @vercel/python
app = VercelASGIAdapter(fastapi_app)
