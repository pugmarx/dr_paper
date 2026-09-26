import os
from pathlib import Path

# Load .env file from project root
env_path = Path(__file__).resolve().parent.parent / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=env_path)
except ImportError:
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    if k not in os.environ:
                        os.environ[k] = v


class Config:
    # LLM Settings
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()
    
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    
    # Supabase Settings
    SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY", "") or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    SUPABASE_SCHEMA = os.getenv("SUPABASE_SCHEMA", "dr_paper")
    
    # Fetch Settings
    FETCH_DAYS_BACK = int(os.getenv("FETCH_DAYS_BACK", "14"))
    MAX_PAPERS_PER_RUN = int(os.getenv("MAX_PAPERS_PER_RUN", "10"))
    MIN_SCORE_THRESHOLD = float(os.getenv("MIN_SCORE_THRESHOLD", "2.0"))

    # Telegram Bot Settings
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
    MODERATION_TOKEN = os.getenv("MODERATION_TOKEN", "")

config = Config()
