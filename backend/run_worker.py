"""
run_worker.py -- Loads backend/.env, then runs model.py's --watch loop.

model.py itself is untouched and reads plain os.environ values (no dotenv
loading inside it, by design). This script exists purely so the worker
picks up the same MONGO_URI / GROQ_API_KEY / GRIDFS_BUCKET / BACKEND_BASE_URL
settings as the FastAPI server (app/), from the same .env file, without
editing model.py.

Usage:
    python run_worker.py            # equivalent to: python model.py --watch
    python run_worker.py --job-id X # equivalent to: python model.py --job-id X
"""

import os
import runpy
import sys

from dotenv import load_dotenv

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_ENV_PATH = os.path.join(_BACKEND_DIR, ".env")

if os.path.exists(_ENV_PATH):
    load_dotenv(_ENV_PATH, override=False)
    print(f"[run_worker] loaded env from {_ENV_PATH}")
else:
    print(f"[run_worker] WARNING: no .env found at {_ENV_PATH} -- "
          f"copy .env.example to .env first")

# Default to --watch if the user passed no arguments, same as model.py's own CLI.
if len(sys.argv) == 1:
    sys.argv.append("--watch")

_MODEL_PATH = os.path.join(_BACKEND_DIR, "model.py")
runpy.run_path(_MODEL_PATH, run_name="__main__")
