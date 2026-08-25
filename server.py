"""
Settle Up - Local Development & Production Server Runner
Starts the Python Flask backend and serves the frontend application.
"""

import sys
import argparse
from backend import create_app
from backend.config import get_config

# Ensure proper UTF-8 output on Windows consoles
if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure') and sys.stderr.encoding != 'utf-8':
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass


def main():
    config = get_config()

    parser = argparse.ArgumentParser(description='Settle Up Web Application & Backend Server')
    parser.add_argument('--host', default=config.HOST, help=f'Host to bind to (default: {config.HOST})')
    parser.add_argument('--port', type=int, default=config.PORT, help=f'Port to bind to (default: {config.PORT})')
    parser.add_argument('--debug', action='store_true', default=config.DEBUG, help='Enable Flask debug mode')
    parser.add_argument('--init-db', action='store_true', help='Initialize database tables & migrations and exit')
    parser.add_argument('--waitress', action='store_true', help='Serve using production Waitress WSGI server')
    args = parser.parse_args()

    app = create_app()

    if args.init_db:
        print(" [✓] Database tables and schema migrations verified.")
        return

    print("\n" + "=" * 62)
    print(" ⚡ SETTLE UP - SMART EXPENSE & DEBT SIMPLIFIER (FLASK BACKEND)")
    print("=" * 62)
    print(f" [*] Web Application:   http://{args.host}:{args.port}")
    print(f" [*] Health Check:      http://{args.host}:{args.port}/api/health")
    print(f" [*] API Rooms:         http://{args.host}:{args.port}/api/rooms")
    print(f" [*] Sample Room URL:   http://{args.host}:{args.port}/?room=GOA2026")
    print(f" [*] Debug Mode:        {args.debug}")
    print("=" * 62 + "\n")

    if args.waitress:
        try:
            from waitress import serve
            print(f" [*] Serving with Waitress WSGI server on {args.host}:{args.port}...")
            serve(app, host=args.host, port=args.port)
            return
        except ImportError:
            print(" [!] Waitress not installed. Falling back to default Flask server.")

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
