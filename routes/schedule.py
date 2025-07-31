from flask import jsonify, request, render_template, current_app
from extensions import scheduler
from scanner import run_scan
from models import ScanResult
import uuid
from datetime import datetime


from flask import Blueprint
schedule_bp = Blueprint('schedule', __name__)

# ensure a module‐level list lives across requests
scheduled_scans = []
scan_id_counter = 1

def schedule_scan_job(scan):
    # Remove existing job
    try:
        scheduler.remove_job(scan['job_id'])
    except Exception:
        pass
    if scan.get('active'):
        # For demo: only support one-off jobs
        scheduler.add_job(
            func=_scheduled_scan,
            trigger='date',
            run_date=scan['run_at'],
            args=[current_app._get_current_object(), scan['target'], scan['ports'], scan['flags'], scan['mode'], scan['threads']],
            id=scan['job_id'],
            replace_existing=True,
        )




@schedule_bp.route('/<job_id>/update', methods=['POST'])
def update_schedule(job_id):
    data = request.get_json() or {}
    for scan in scheduled_scans:
        if scan['job_id'] == job_id:
            scan.update(data)
            # Fix: parse run_at if present and convert to correct format
            if 'run_at' in scan:
                try:
                    # Accept both 'YYYY-MM-DDTHH:MM' and 'YYYY-MM-DD HH:MM:SS'
                    run_at = scan['run_at']
                    if 'T' in run_at:
                        run_at = run_at.replace('T', ' ')
                    if len(run_at) == 16:
                        run_at += ':00'
                    scan['run_at'] = run_at
                except Exception:
                    return jsonify(error='Invalid run_at format'), 400
            schedule_scan_job(scan)
            return jsonify(success=True)
    return jsonify(error='Not found'), 404

@schedule_bp.route('/<job_id>/cancel', methods=['POST'])
def cancel_schedule(job_id):
    for scan in scheduled_scans:
        if scan['job_id'] == job_id:
            scan['active'] = False
            try:
                scheduler.remove_job(scan['job_id'])
            except Exception:
                pass
            return jsonify(success=True)
    return jsonify(error='Not found'), 404



import threading
from flask import current_app, jsonify
from scanner import run_scan

@schedule_bp.route('/<job_id>/run', methods=['POST'])
def schedule_run_now(job_id):
    job = next((j for j in scheduled_scans if j['job_id'] == job_id), None)
    if not job:
        return jsonify({'success': False, 'error': 'Job not found'}), 404

    app = current_app._get_current_object()
    target  = job['target']
    ports   = job.get('ports', '')
    flags   = job.get('flags', '')
    mode    = job.get('mode', 'Basic')
    threads = job.get('threads', app.config['DEFAULT_THREADS'])

    def background_runner():
        from extensions import db
        from models import ScanResult
        with app.app_context():
            # 1) create and persist the new ScanResult
            scan = ScanResult(
                target=target,
                ports=ports,
                flags=flags,
                mode=mode,
                status='Running'
            )
            db.session.add(scan)
            db.session.commit()  # ensure scan.id is populated
            scan_id = scan.id
            # 2) hand off to your normal run_scan()
            run_scan(app, scan_id, target, ports, flags, mode, threads)

    t = threading.Thread(target=background_runner, daemon=True)
    t.start()

    return jsonify({'success': True, 'message': 'Rescan started'}), 200

@schedule_bp.route('/manage', methods=['GET'])
def manage_schedules():
    return render_template('manage_schedules.html')


@schedule_bp.route('/submit', methods=['POST'])
def schedule_submit():
    data = request.get_json() or {}
    target = data.get('target','').strip()
    ports  = data.get('ports','').strip()
    flags  = data.get('flags','').strip()
    mode   = data.get('mode','Basic')
    threads= int(data.get('threads') or current_app.config['DEFAULT_THREADS'])
    run_at = data.get('run_at')  # ISO datetime string

    if not target or not run_at:
        return jsonify(error="Target and run time required"), 400

    # Fix: ensure run_at is a valid datetime string with seconds
    from datetime import datetime
    try:
        # If seconds are missing, add ':00'
        if len(run_at) == 16:
            run_at += ':00'
        run_at_dt = datetime.fromisoformat(run_at)
    except Exception:
        return jsonify(error="Invalid run time format"), 400

    from flask import current_app
    app = current_app._get_current_object()
    job_id = f"scan-{uuid.uuid4().hex}"
    # append to the module‐level list, not reassign it
    global scheduled_scans, scan_id_counter
    scan_entry = {
        'id': scan_id_counter,
        'job_id': job_id,
        'target': target,
        'ports': ports,
        'flags': flags,
        'mode': mode,
        'threads': threads,
        'run_at': run_at_dt.isoformat(sep=' '),
        'days_of_week': [],
        'active': True,
        'next_run_time': run_at_dt.isoformat(sep=' ')
    }
    scheduled_scans.append(scan_entry)
    scan_id_counter += 1
    scheduler.add_job(
        func=_scheduled_scan,
        trigger='date',
        run_date=run_at_dt,
        args=[app, target, ports, flags, mode, threads],
        id=job_id,
        replace_existing=False,
    )
    return jsonify(job_id=job_id, status="scheduled")

@schedule_bp.route('/api', methods=['GET'])
def schedule_api():
    return jsonify(scheduled_scans)

def _scheduled_scan(app, target, ports, flags, mode, threads):
    # mirror start_scan logic
    from extensions import db, socketio
    with app.app_context():
        scan = ScanResult(
            target=target,
            ports=ports,
            flags=flags,
            mode="Threaded" if mode=="Threaded" else "Basic",
            status="Running"
        )
        db.session.add(scan)
        db.session.commit()
        scan_id = scan.id

        socketio.start_background_task(
            run_scan,
            app,
            scan_id, target, ports, flags, scan.mode, threads
        )
