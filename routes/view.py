import json
import difflib
from flask import Blueprint, request, render_template, current_app, jsonify, abort
from flask_login import login_required
from extensions import db, socketio
from models import ScanResult, ChangeLog
from scanner import run_scan

view_bp = Blueprint('view', __name__, url_prefix='/view')


@view_bp.route('/<int:scan_id>')
@login_required
def view_scan(scan_id):
    scan = ScanResult.query.get(scan_id)
    if not scan or scan.status != "Completed" or not scan.results_json:
        return render_template('scan_not_found.html', scan_id=scan_id), 404

    # parse XML→dict
    data = json.loads(scan.results_json)
    cmd  = data.get('@args')

    # normalize hosts
    hosts = data.get('host') or []
    if not isinstance(hosts, list):
        hosts = [hosts]

    summary = []
    for h in hosts:
        # addresses
        addrs = h.get('address') or []
        if isinstance(addrs, dict):
            addrs = [addrs]
        ip = mac = None
        for a in addrs:
            if a.get('@addrtype') in ('ipv4','ipv6'):
                ip = a.get('@addr')
            if a.get('@addrtype') == 'mac':
                mac = a.get('@addr')

        # hostname
        hn = h.get('hostnames') or {}
        hn_entry = hn.get('hostname')
        if isinstance(hn_entry, dict):
            hostname = hn_entry.get('@name')
        elif isinstance(hn_entry, list) and hn_entry:
            hostname = hn_entry[0].get('@name')
        else:
            hostname = None

        # os
        osmatch = h.get('os',{}).get('osmatch')
        if osmatch:
            first = osmatch[0] if isinstance(osmatch,list) else osmatch
            os_name = first.get('@name')
            os_acc  = first.get('@accuracy')
        else:
            os_name = os_acc = None

        # ports + scripts
        ports_raw = h.get('ports',{}).get('port') or []
        if isinstance(ports_raw, dict):
            ports_raw = [ports_raw]
        open_ports = []
        for p in ports_raw:
            if p.get('state',{}).get('@state') == 'open':
                svc = p.get('service') or {}
                version = " ".join(filter(None,[svc.get('@product'),svc.get('@version')]))
                scr = p.get('script') or []
                if isinstance(scr,dict):
                    scr = [scr]
                port_scripts = [{'id':s.get('@id'),'output':s.get('@output','')} for s in scr]
                open_ports.append({
                    'port':     p.get('@portid'),
                    'protocol': p.get('@protocol'),
                    'service':  svc.get('@name'),
                    'version':  version,
                    'scripts':  port_scripts
                })

        # host‐level scripts
        scr = h.get('script') or []
        if isinstance(scr, dict):
            scr = [scr]
        host_scripts=[]
        ssl_cert=None; http_title=None
        for s in scr:
            sid = s.get('@id'); out = s.get('@output','')
            host_scripts.append({'id':sid,'output':out})
            if sid=='ssl-cert' and not ssl_cert:
                ssl_cert=out.split('\n',1)[0]
            if sid=='http-title' and not http_title:
                http_title=out.strip()

        summary.append({
            'ip':           ip,
            'mac':          mac,
            'hostname':     hostname,
            'os':           {'name':os_name,'accuracy':os_acc},
            'open_ports':   open_ports,
            'host_scripts': host_scripts,
            'ssl':          ssl_cert,
            'http_title':   http_title
        })

    # find latest ChangeLog for _this_ scan
    changelog = ChangeLog.query.filter_by(scan_id=scan.id).order_by(ChangeLog.timestamp.desc()).first()

    return render_template('view.html',
                           scan=scan, cmd=cmd,
                           summary=summary,
                           changelog=changelog)


@view_bp.route('/rescan/<int:scan_id>', methods=['POST'])
@login_required
def rescan(scan_id):
    """Kick off a brand-new scan with the same flags, record in ChangeLog"""
    old = ScanResult.query.get_or_404(scan_id)

    # create new scan row
    new = ScanResult(
        target=old.target,
        ports=old.ports,
        flags=old.flags,
        mode=old.mode,
        status='Running'
    )
    db.session.add(new)
    db.session.commit()

    # start the background job
    threads = current_app.config.get('DEFAULT_THREADS', 100)
    socketio.start_background_task(
        run_scan,
        current_app._get_current_object(),
        new.id,
        new.target,
        new.ports,
        new.flags,
        new.mode,
        threads
    )

    # store the linkage in ChangeLog immediately (diff will be filled in later)
    cl = ChangeLog(
      scan_id=new.id,
      previous_scan_id=old.id,
      diff='(pending...)'
    )
    db.session.add(cl)
    db.session.commit()

    return jsonify(scan_id=new.id)