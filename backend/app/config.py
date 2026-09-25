import os
from dotenv import load_dotenv

# Load backend/.env by absolute path so it works no matter which folder the
# server is started from. utf-8-sig handles files saved with a BOM (Notepad).
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ENV_PATH = os.path.join(_BACKEND_DIR, ".env")

print(f"[config] looking for .env at: {_ENV_PATH}")
if os.path.exists(_ENV_PATH):
    load_dotenv(_ENV_PATH, override=True, encoding="utf-8-sig")
    print("[config] .env found and loaded")
else:
    print("[config] WARNING: .env NOT FOUND at that path "
          "(check the file is named exactly '.env', not '.env.txt')")


# ============================================================
# MONGODB
# ============================================================

MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb://127.0.0.1:27017"
)

MONGO_DB_NAME = os.getenv(
    "MONGO_DB_NAME",
    "squat_check"
)


# ============================================================
# GROQ / MODEL 2
# ============================================================

GROQ_API_KEY = (
    os.getenv("GROQ_API_KEY", "")
    .strip()
    .strip('"')
    .strip("'")
)

if not GROQ_API_KEY or "your_groq_api_key" in GROQ_API_KEY:
    print("[config] WARNING: GROQ_API_KEY is empty or still the placeholder")
    GROQ_API_KEY = ""
else:
    print(f"[config] GROQ_API_KEY loaded (starts with {GROQ_API_KEY[:4]}...)")

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "auto"
)


# ============================================================
# FILE DIRECTORIES
# ============================================================

UPLOAD_DIR = os.getenv(
    "UPLOAD_DIR",
    "data/uploads"
)

OUTPUT_DIR = os.getenv(
    "OUTPUT_DIR",
    "data/outputs"
)


# ============================================================
# VIDEO SETTINGS
# ============================================================

MAX_VIDEO_SECONDS = int(
    os.getenv(
        "MAX_VIDEO_SECONDS",
        "60"
    )
)

# Safety net only (not a format restriction) -- protects the disk from a
# runaway upload. Raise via .env if you need to accept bigger files.
MAX_UPLOAD_MB = int(
    os.getenv(
        "MAX_UPLOAD_MB",
        "1024"
    )
)

MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

VIDEO_LOOKBACK_SECONDS = int(
    os.getenv(
        "VIDEO_LOOKBACK_SECONDS",
        "60"
    )
)

# No content-type / extension whitelist: any video file is accepted at
# upload time. Whatever format/codec it arrives in gets normalized to a
# standard H.264 MP4 by ffmpeg (see pipeline/orchestrator.py) before the
# model reads it, so the model never has to care what came in.

# ============================================================
# FRONTEND CORS
# ============================================================

FRONTEND_ORIGINS = os.getenv(
    "FRONTEND_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173"
).split(",")