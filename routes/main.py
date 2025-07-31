from flask import Blueprint, render_template, current_app
from flask_login import login_required

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def index():
    default_threads = current_app.config.get('DEFAULT_THREADS', 100)
    default_mode    = current_app.config.get('DEFAULT_MODE', 'Basic')
    return render_template(
        'index.html',
        default_threads=default_threads,
        default_mode=default_mode
    )