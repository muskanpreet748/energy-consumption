"""Vercel serverless entry point.

Vercel's Python runtime imports this module and expects an ASGI ``app``.
The real application lives in ``backend/main.py`` so that it stays runnable
locally (``uvicorn main:app --app-dir backend``) and inside Docker without
any platform-specific code.

The only job of this file is to put ``backend/`` on ``sys.path`` and re-export
the application. Keeping the platform shim separate means the domain code has
no knowledge of Vercel.
"""

from __future__ import annotations

import sys
from pathlib import Path

# /var/task is the serverless bundle root; /var/task/backend holds the app.
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from main import app  # noqa: E402  - import must follow the sys.path fix

__all__ = ["app"]
