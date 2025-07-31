import re
import ipaddress

from flask import Blueprint, request, jsonify, current_app
from sqlalchemy.exc import SQLAlchemyError

from extensions import db, socketio
from models import ScanResult
from scanner import run_scan

scan_bp = Blueprint('scan', __name__, url_prefix='/scan')

@scan_bp.route('', methods=['POST'])
def start_scan():
    data    = request.get_json() or {}
    target  = data.get('target', '').strip()
    ports   = data.get('ports', '').strip()
    mode    = data.get('mode', 'Basic')
    threads = data.get('threads')
    preset  = data.get('preset', '')
    custom  = data.get('custom_flags', '').strip()

    # 1) Validate target is a proper IPv4, IPv6 or CIDR network
    if not target:
        return jsonify(error="Target is required"), 400
    try:
        if '/' in target:
            ipaddress.ip_network(target, strict=False)
        else:
            ipaddress.ip_address(target)
    except ValueError:
        return jsonify(error="Invalid IPv4/IPv6 address or network"), 400

    # 2) Validate ports string:  e.g. "80", "1-100,443"
    if ports and not re.fullmatch(r'\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*', ports):
        return jsonify(error="Invalid port specification"), 400

    # 3) Determine flags:  use custom if 'custom' preset selected
    flags = custom if preset == 'custom' else (preset or "")

    # 4) Create DB record
    scan = ScanResult(
        target=target,
        ports=ports,
        flags=flags,
        mode="Threaded" if mode == "Threaded" else "Basic",
        status="Running"
    )
    try:
        db.session.add(scan)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify(error="Database error"), 500

    scan_id = scan.id

    # 5) Build the client-visible Nmap command string
    parts = ["nmap", "-Pn"]
    if ports:
        parts += ["-p", ports]
    if flags:
        parts += flags.split()
    parts.append(target)
    cmd_str = " ".join(parts)

    # 6) Launch the actual scan in a background thread
    socketio.start_background_task(
        run_scan,
        current_app._get_current_object(),
        scan_id,
        target,
        ports,
        flags,
        scan.mode,
        threads
    )

    return jsonify(scan_id=scan_id, status="started", cmd=cmd_str), 200