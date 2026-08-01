import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

_data_dir_override = os.getenv("LEADGUARD_DATA_DIR", "")
DATA_DIR = Path(_data_dir_override) if _data_dir_override else BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "app.db"
INDEX_PATH = DATA_DIR / "index.pkl"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")

# Product/agency name shown in the dashboard and support page — override via env so a
# rebrand is a one-line config change, not a find-and-replace across the codebase.
PRODUCT_NAME = os.getenv("PRODUCT_NAME", "LeadGuard")

# Agency-level (your own) contact info for the /support page — identical across every
# deployed client instance, so it lives in env config, not the per-client `business` table.
AGENCY_NOTIFY_WEBHOOK_URL = os.getenv("AGENCY_NOTIFY_WEBHOOK_URL", "")
AGENCY_NOTIFY_EMAIL = os.getenv("AGENCY_NOTIFY_EMAIL", "")

# Origins allowed to embed the widget (comma-separated), or "*" for any.
WIDGET_ALLOWED_ORIGINS = os.getenv("WIDGET_ALLOWED_ORIGINS", "*")
