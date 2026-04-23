import os
from flask import Flask
from flask_cors import CORS

from config import config_map
from core.database import init_db
from routes.views import views_bp
from routes.expenses import expenses_bp


def create_app(env: str = None) -> Flask:
    """
    Application factory.
    Usage:
        app = create_app("development")
        app = create_app("production")
    """
    env = env or os.environ.get("FLASK_ENV", "default")
    cfg = config_map.get(env, config_map["default"])

    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config.from_object(cfg)

    # ── Extensions ────────────────────────────────────────────────────────────
    CORS(app)

    # ── Ensure DB directory exists ────────────────────────────────────────────
    os.makedirs(app.config["DB_DIR"], exist_ok=True)

    # ── Initialise database ───────────────────────────────────────────────────
    init_db(app.config["DB_PATH"])

    # ── Register blueprints ───────────────────────────────────────────────────
    app.register_blueprint(views_bp)
    app.register_blueprint(expenses_bp, url_prefix="/expenses")

    return app


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    application = create_app("development")
    application.run(host="0.0.0.0", port=5000, debug=True)