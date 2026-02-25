import os
import sys

try:
    import eventlet
    eventlet.monkey_patch()
except ImportError:
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from app import create_app

# create_app غالبًا بيرجع app بس
app = create_app()
application = app
_socketio = None

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
