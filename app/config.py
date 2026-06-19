import os
from dotenv import load_dotenv

load_dotenv()

def require(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return val

SUPABASE_URL        = require("SUPABASE_URL")
SUPABASE_SERVICE_KEY = require("SUPABASE_SERVICE_KEY")
OPENAI_API_KEY      = require("OPENAI_API_KEY")
ANTHROPIC_API_KEY   = require("ANTHROPIC_API_KEY")
KAPSO_API_BASE_URL  = require("KAPSO_API_BASE_URL")
KAPSO_API_KEY       = require("KAPSO_API_KEY")
KAPSO_WEBHOOK_SECRET = require("KAPSO_WEBHOOK_SECRET")

TELEGRAM_BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN")
