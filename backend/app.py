"""
QMS Enterprise — Main Flask Application v3.2
Railway-compatible: single container, Flask serves API + static files
"""
import os
import logging
from flask import Flask, send_from_directory, jsonify, abort
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from config import config
from models import db, bcrypt

logger = logging.getLogger(__name__)

# ── Resolve paths ─────────────────────────────────────────────────
_BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
_FRONT_DIR = os.path.abspath(os.path.join(_BASE_DIR, '..', 'frontend'))


def create_app(config_name=None):
    if config_name is None:
        env = os.environ.get('FLASK_ENV', 'production')
        if env not in ('development', 'production', 'testing'):
            env = 'production'
        config_name = env

    app = Flask(
        __name__,
        static_folder=_FRONT_DIR,
        static_url_path='',
    )
    app.config.from_object(config[config_name])

    # ── Extensions ────────────────────────────────────────────────
    db.init_app(app)
    bcrypt.init_app(app)
    JWTManager(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

    # ── WebSocket (optional, degrades gracefully) ─────────────────
    socketio = None
    try:
        from flask_socketio import SocketIO
        socketio = SocketIO(
            app,
            cors_allowed_origins="*",
            async_mode="eventlet",
            logger=False,
            engineio_logger=False,
            path='/socket.io',
        )
        app.extensions["socketio"] = socketio

        @socketio.on("connect")
        def _on_connect():
            logger.info("WS client connected")

        @socketio.on("disconnect")
        def _on_disconnect():
            logger.info("WS client disconnected")

        @socketio.on("subscribe_kpi")
        def _on_subscribe(data):
            from flask_socketio import join_room
            fid = data.get("factory_id")
            if fid:
                join_room(f"factory_{fid}")

    except ImportError:
        logger.warning("flask-socketio not installed — real-time push disabled")

    # ── Register models ────────────────────────────────────────────
    with app.app_context():
        try:
            from models.user_model    import User, PasswordReset, RefreshToken, AuditLog  # noqa
            from models.factory_model import Factory   # noqa
            from models.role_model    import Role, Permission  # noqa
        except Exception as e:
            logger.warning(f"Model import warning: {e}")

    # ── Blueprints ────────────────────────────────────────────────
    try:
        from routes.auth_routes    import auth_bp
        from routes.role_routes    import role_bp
        from routes.factory_routes import factory_bp
        from routes.user_routes    import user_bp
        from routes.library_routes import library_bp
        from routes.forms_routes   import forms_bp
        from routes.quality_routes import quality_bp
        from routes.ai_routes      import ai_bp
        from routes.reports_routes import reports_bp
        from routes.q40_routes     import q40_bp

        app.register_blueprint(auth_bp,     url_prefix='/api/auth')
        app.register_blueprint(role_bp,     url_prefix='/api/roles')
        app.register_blueprint(factory_bp,  url_prefix='/api/factories')
        app.register_blueprint(user_bp,     url_prefix='/api/users')
        app.register_blueprint(library_bp,  url_prefix='/api/library')
        app.register_blueprint(forms_bp,    url_prefix='/api/forms')
        app.register_blueprint(quality_bp,  url_prefix='/api/quality')
        app.register_blueprint(ai_bp,       url_prefix='/api/ai')
        app.register_blueprint(reports_bp,  url_prefix='/api/reports')
        app.register_blueprint(q40_bp,      url_prefix='/api/q40')
    except Exception as e:
        logger.error(f"Blueprint registration error: {e}")

    # ── Health check ───────────────────────────────────────────────
    @app.route('/api/health')
    def health():
        return jsonify({
            "status":    "ok",
            "version":   "3.2.0",
            "platform":  "QMS Enterprise — Quality 4.0",
            "websocket": socketio is not None,
            "frontend":  os.path.isdir(_FRONT_DIR),
        })

    # ── Root → index.html ──────────────────────────────────────────
    @app.route('/')
    def root():
        index_path = os.path.join(_FRONT_DIR, 'index.html')
        if os.path.isfile(index_path):
            return send_from_directory(_FRONT_DIR, 'index.html')
        return jsonify({"status": "ok", "message": "QMS Enterprise API running", "docs": "/api/health"})

    # ── SPA catch-all ──────────────────────────────────────────────
    @app.route('/<path:path>')
    def spa(path):
        # Let /api/* and /socket.io/ pass through — they're handled above
        if path.startswith('api/') or path.startswith('socket.io'):
            abort(404)

        # Serve static file if it exists
        target = os.path.join(_FRONT_DIR, path)
        if os.path.isfile(target):
            return send_from_directory(_FRONT_DIR, path)

        # HTML pages — try .html suffix
        if not path.endswith('.html'):
            html_target = os.path.join(_FRONT_DIR, path + '.html')
            if os.path.isfile(html_target):
                return send_from_directory(_FRONT_DIR, path + '.html')

        # SPA fallback
        index_path = os.path.join(_FRONT_DIR, 'index.html')
        if os.path.isfile(index_path):
            return send_from_directory(_FRONT_DIR, 'index.html')
        return jsonify({"status": "ok", "message": "QMS Enterprise API"}), 200

    # ── Background Scheduler ───────────────────────────────────────
# Disable scheduler for production start
# if not app.config.get('TESTING'):
#     from ai.scheduler import start_scheduler
#     start_scheduler(app)
         try:
         ...
          except Exception as e:
         logger.error(...)

    # ── KPI broadcast helper ───────────────────────────────────────
    if socketio:
        def broadcast_kpi(factory_id: int, data: dict):
            socketio.emit("kpi_update", data, room=f"factory_{factory_id}")
        app.broadcast_kpi = broadcast_kpi

    logger.info(f"QMS Enterprise started | frontend={_FRONT_DIR} | exists={os.path.isdir(_FRONT_DIR)}")
    return app, socketio


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    _app, _socketio = create_app()
    if _socketio:
        _socketio.run(_app, host='0.0.0.0', port=port, debug=False)
    else:
        _app.run(host='0.0.0.0', port=port, debug=False)
