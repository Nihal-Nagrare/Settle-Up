"""
Vercel Serverless Function Entrypoint for Settle Up Backend.
Exposes the Flask `app` WSGI instance for Vercel's Python runtime (@vercel/python).
"""

import sys
from pathlib import Path

# Ensure project root directory is in python path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from wsgi import app

# Alias for Vercel serverless function handler compatibility
handler = app
