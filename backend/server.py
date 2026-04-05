"""Compatibility entrypoint for running the refactored FastAPI backend."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.api.main import app
from src.config.settings import get_settings

settings = get_settings()
reload_enabled = os.getenv("UVICORN_RELOAD", "false").strip().lower() in {"1", "true", "yes"}


if __name__ == "__main__":
    uvicorn.run(
        "src.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=reload_enabled,
    )
