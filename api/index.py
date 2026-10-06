"""Vercel serverless entry point for the Django WSGI application."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.wsgi import application as app  # noqa: E402
