"""
Settle Up - Production WSGI Application Entrypoint
Suitable for Gunicorn, uWSGI, Waitress, AWS Elastic Beanstalk, Render, Railway, Fly.io, etc.

Usage:
    # Gunicorn (Linux / Container / PaaS):
    gunicorn --workers 4 --threads 2 --bind 0.0.0.0:5000 "wsgi:app"

    # Waitress (Windows / Cross-platform):
    waitress-serve --port=5000 wsgi:app
"""

import os
from backend import create_app
from backend.config import get_config

# Initialize application instance with active configuration
config = get_config()
app = create_app(config)

if __name__ == "__main__":
    # Fallback runner when executed directly
    port = int(os.getenv("PORT", config.PORT or 5000))
    host = os.getenv("HOST", config.HOST or "0.0.0.0")
    app.run(host=host, port=port, debug=config.DEBUG)
