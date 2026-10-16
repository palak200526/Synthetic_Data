import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing from .env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Local Ollama (never send datasets to cloud LLM APIs)
OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434",
).rstrip("/")

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


LLM_TEXT_BATCH_SIZE = _env_int("LLM_TEXT_BATCH_SIZE", 20)
LLM_TEXT_TIMEOUT = _env_int("LLM_TEXT_TIMEOUT", 300)
LLM_TEXT_MAX_RETRIES = _env_int("LLM_TEXT_MAX_RETRIES", 3)
LLM_TEXT_SIMILARITY_THRESHOLD = _env_float(
    "LLM_TEXT_SIMILARITY_THRESHOLD",
    0.92,
)

REDIS_BROKER_URL = os.getenv(
    "REDIS_BROKER_URL",
    "redis://localhost:6379/0",
)


# ---------------------------------------------------------------------------
# Auth / session
# ---------------------------------------------------------------------------
# How long a login stays valid. Default 24 h (was a fixed 60 min). A token that
# is past half of its life is silently renewed on the next API call, so anyone
# who keeps using the app is never signed out mid-work.
ACCESS_TOKEN_EXPIRE_MINUTES = _env_int("ACCESS_TOKEN_EXPIRE_MINUTES", 24 * 60)
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-secret-key")

# ---------------------------------------------------------------------------
# Generation safety
# ---------------------------------------------------------------------------
# If no signed-in browser has checked on a running generation for this long
# (tab closed, signed out, token expired, laptop asleep, network lost), the
# worker pauses itself at the next batch boundary. Every finished batch is
# already checkpointed, so Resume continues from the saved rows.
# 0 disables the automatic pause.
GENERATION_IDLE_PAUSE_SECONDS = _env_int("GENERATION_IDLE_PAUSE_SECONDS", 180)
