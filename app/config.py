"""Configuration from environment variables (and an optional local .env file)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv():
    f = ROOT / ".env"
    if not f.exists():
        return
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()

ENV = os.environ.get("ML_ENV", "development")  # development | test | production
IS_PROD = ENV == "production"


def database_url() -> str:
    if os.environ.get("ML_ENV") == "test" or os.environ.get("ML_TEST") == "1":
        return os.environ.get("TEST_DATABASE_URL", "postgresql://ml_app:ml_app_dev@localhost:5432/motionlife_test")
    return os.environ.get("DATABASE_URL", "postgresql://ml_app:ml_app_dev@localhost:5432/motionlife")


DB_POOL_SIZE = int(os.environ.get("DB_POOL_SIZE", "8"))
SECRET_KEY = os.environ.get("SECRET_KEY", "")
if IS_PROD and len(SECRET_KEY) < 32:
    raise RuntimeError("SECRET_KEY must be set (>=32 chars) in production")
if not SECRET_KEY:
    SECRET_KEY = "dev-only-insecure-secret-change-me-0123456789"

SESSION_TTL_HOURS = int(os.environ.get("SESSION_TTL_HOURS", "12"))
SESSION_IDLE_MINUTES = int(os.environ.get("SESSION_IDLE_MINUTES", "60"))
LOGIN_MAX_ATTEMPTS = int(os.environ.get("LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_LOCK_MINUTES = int(os.environ.get("LOGIN_LOCK_MINUTES", "15"))
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "1" if IS_PROD else "0") == "1"
PUBLIC_ORIGIN = os.environ.get("PUBLIC_ORIGIN", "")  # e.g. https://clinic.example.com
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", str(ROOT / "var" / "uploads")))
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "10"))
CENTER_PHONE = os.environ.get("CENTER_PHONE", "")
CENTER_ADDRESS = os.environ.get("CENTER_ADDRESS", "دمشق - الميدان")
PDF_ENGINE = os.environ.get("PDF_ENGINE", "chromium")  # chromium | none
TRUST_PROXY = os.environ.get("TRUST_PROXY", "0") == "1"  # behind Render/Nginx: honour X-Forwarded-Proto/For
ALLOW_DEMO = os.environ.get("ALLOW_DEMO", "0") == "1"  # trial deployments only: demo accounts + synthetic patients
CHROMIUM_NO_SANDBOX = os.environ.get("CHROMIUM_NO_SANDBOX", "0") == "1"
