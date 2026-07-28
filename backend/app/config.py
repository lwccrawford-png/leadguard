import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "app.db"
INDEX_PATH = DATA_DIR / "index.pkl"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")

# Origins allowed to embed the widget (comma-separated), or "*" for any.
WIDGET_ALLOWED_ORIGINS = os.getenv("WIDGET_ALLOWED_ORIGINS", "*")
