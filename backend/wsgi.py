"""
WSGI Entry Point — QMS Enterprise
Railway / Gunicorn: gunicorn wsgi:application

IMPORTANT: eventlet monkey-patching MUST happen before any other import.
"""
import os
import sys

# ── Eventlet monkey-patch (must be ABSOLUTE FIRST) ──────────────
try:
    import eventlet
    eventlet.monkey_patch()
except ImportError:
    pass  # falls back to sync workers gracefully

# ── Path setup ──────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# ── Create application ──────────────────────────────────────────
from app import create_app

_app, _socketio = create_app()

# Gunicorn looks for `application`; some tools look for `app`
application = _app
app = _app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    if _socketio:
        _socketio.run(_app, host='0.0.0.0', port=port, debug=False)
    else:
        _app.run(host='0.0.0.0', port=port, debug=False)
