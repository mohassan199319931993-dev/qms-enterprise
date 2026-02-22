"""
WSGI Entry Point — QMS Enterprise
Used by Gunicorn: gunicorn wsgi:application
"""
from app import create_app

_app, _socketio = create_app()

# Gunicorn needs `application` callable
application = _app

if __name__ == '__main__':
    _app.run()
