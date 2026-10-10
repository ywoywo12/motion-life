"""Local development server: python run.py  (production: see README — use a WSGI server behind HTTPS)."""
import os

from app import create_app, config

app = create_app()

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    if config.IS_PROD:
        raise SystemExit("لا تستخدم خادم التطوير في الإنتاج. راجع README (gunicorn/waitress خلف HTTPS).")
    app.run(host=host, port=port, threaded=True, debug=False)
