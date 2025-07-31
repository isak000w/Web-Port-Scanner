# routes/history.py

import json
import re
from datetime import datetime, timedelta

from flask import (
    Blueprint, request, render_template,
    redirect, url_for, current_app
)
from sqlalchemy.exc import SQLAlchemyError

from extensions import db, socketio
from models import ScanResult

history_bp = Blueprint('history', __name__, url_prefix='/history')


@history_bp.route('', methods=['GET'])
def history():
    query = ScanResult.query.order_by(ScanResult.timestamp.desc())

    # 1) Strictly sanitize the 'target' filter:
    tflt = request.args.get('target', '').strip()
    if tflt and not re.fullmatch(r'[\w\.\-\/]+', tflt):
        # contains illegal chars → drop filter entirely
        tflt = ''
    if tflt:
        query = query.filter(ScanResult.target.ilike(f"%{tflt}%"))

    mflt = request.args.get('mode', '')
    if mflt:
        query = query.filter(ScanResult.mode == mflt)

    start = request.args.get('start_date', '')
    if start:
        try:
            dt = datetime.fromisoformat(start)
            query = query.filter(ScanResult.timestamp >= dt)
        except ValueError:
            pass

    end = request.args.get('end_date', '')
    if end:
        try:
            dt_end = datetime.fromisoformat(end) + timedelta(days=1)
            query = query.filter(ScanResult.timestamp < dt_end)
        except ValueError:
            pass

    scans = query.all()
    return render_template(
        'history.html',
        scans=scans,
        target_q=tflt,
        mode_q=mflt,
        start_q=start,
        end_q=end
    )


@history_bp.route('/rescan/<int:scan_id>', methods=['POST'])
def rescan(scan_id):
    """Kick off a new scan using the same parameters as an existing one."""
    old = ScanResult.query.get_or_404(scan_id)

    new = ScanResult(
        target=old.target,
        ports=old.ports,
        flags=old.flags,
        mode=old.mode,
        status="Running"
    )
    try:
        db.session.add(new)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return redirect(url_for('history.history'))

    # Start background task exactly like /scan
    from scanner import run_scan
    socketio.start_background_task(
        run_scan,
        current_app._get_current_object(),
        new.id,
        new.target,
        new.ports,
        new.flags,
        new.mode,
        current_app.config.get('DEFAULT_THREADS', 100)
    )

    # Redirect to the new report page, carrying the old scan as base
    return redirect(
        url_for('view.view_scan', scan_id=new.id, base=old.id)
    )