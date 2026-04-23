from flask import Blueprint, render_template
from core.models import VALID_CATEGORIES

views_bp = Blueprint("views", __name__)


@views_bp.route("/")
def index():
    """Serve the main SPA shell."""
    return render_template("index.html", categories=VALID_CATEGORIES)