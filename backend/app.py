"""
QMS Enterprise — Main Flask Application v3.1
Industrial Quality Management Platform — Quality 4.0
"""
import os
import logging
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from config import config
from models import db, bcrypt

logger = logging.getLogger(__name__)


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__, static_folder='frontend', static_url_path='/')
    app.config.from_object(config[config_name])

    # ── Core extensions ────────────────────────────────────────
    db.init_app(app)
    bcrypt.init_app(app)
    JWTManager(app)
    CORS(app, origins=app.config.get('CORS_ORIGINS', ['*']), supports_credentials=True)

    # ── WebSocket (SocketIO) optional ──────────────────────────
    socketio = None
    try:
        from flask_socketio import SocketIO
        socketio = SocketIO(
            app,
            cors_allowed_origins="*",
            async_mode="eventlet",
            logger=False,
            engineio_logger=False,
        )
        app.extensions["socketio"] = socketio

        @socketio.on("connect")
        def handle_connect():
            logger.info("WebSocket client connected")

        @socketio.on("disconnect")
        def handle_disconnect():
            logger.info("WebSocket client disconnected")

        @socketio.on("subscribe_kpi")
        def handle_subscribe(data):
            from flask_socketio import join_room
            factory_id = data.get("factory_id")
            if factory_id:
                join_room(f"factory_{factory_id}")

    except ImportError:
        logger.warning("flask-socketio not installed. Real-time push disabled.")

    # ── Import models so SQLAlchemy registers them ─────────────
    with app.app_context():
        from models.user_model import User, PasswordReset, RefreshToken, AuditLog
        from models.factory_model import Factory
        from models.role_model import Role, Permission

    # ── Blueprints ─────────────────────────────────────────────
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
    app.register_blueprint(ai_bp, url_prefix='/api/ai')
    app.register_blueprint(reports_bp, url_prefix='/api/reports')
    app.register_blueprint(q40_bp, url_prefix='/api/q40')

    # ── الصفحة الرئيسية ─────────────────────────────
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        return app.send_static_file('index.html')

    # ── Health endpoint ─────────────────────────────
    @app.route('/api/health')
    def health():
        return {
            "status": "ok",
            "version": "3.1.0",
            "platform": "QMS Enterprise — Quality 4.0",
            "websocket": socketio is not None,
            "modules": [
                "auth", "quality", "forms", "ai", "reports", "library",
                "iot", "spc", "maintenance", "chatbot", "rca",
                "traceability", "digital-twin"
            ]
        }

    # ── Background Scheduler ───────────────────────────────────
    if not app.config.get('TESTING'):
        try:
            from ai.scheduler import start_scheduler
            start_scheduler(app)
        except Exception as e:
            logger.warning(f"Scheduler not started: {e}")

    # ── KPI broadcast helper ───────────────────────────────────
    if socketio:
        def broadcast_kpi(factory_id: int, data: dict):
            socketio.emit("kpi_update", data, room=f"factory_{factory_id}")
        app.broadcast_kpi = broadcast_kpi

    return app, socketio


if __name__ == '__main__':
    app, socketio = create_app()
    if socketio:
        socketio.run(app, host='0.0.0.0', port=5000, debug=True)
    else:
        app.run(host='0.0.0.0', port=5000, debug=True)
