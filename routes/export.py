import io, csv, json
from flask import Blueprint, abort
from flask_login import login_required
from models import ScanResult

export_bp = Blueprint('export', __name__, url_prefix='/export')

@export_bp.route('/<int:scan_id>/<fmt>')
@login_required
def export_result(scan_id, fmt):
    scan = ScanResult.query.get_or_404(scan_id)
    if scan.status != "Completed" or not scan.results_json:
        abort(404)

    data = json.loads(scan.results_json)
    fmt  = fmt.lower()

    if fmt == 'json':
        return (
            scan.results_json, 200,
            {
                "Content-Type": "application/json",
                "Content-Disposition": f"attachment; filename=scan_{scan_id}.json"
            }
        )

    if fmt == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["IP","Port","Protocol","State","Service","Version"])
        hosts = data.get('host') or []
        if not isinstance(hosts, list):
            hosts = [hosts]

        for h in hosts:
            ip = scan.target
            addrs = h.get('address')
            if isinstance(addrs, list):
                for a in addrs:
                    if a.get('@addrtype') in ('ipv4','ipv6'):
                        ip = a.get('@addr')
            elif isinstance(addrs, dict):
                if addrs.get('@addrtype') in ('ipv4','ipv6'):
                    ip = addrs.get('@addr')

            ports_list = h.get('ports',{}).get('port') or []
            if isinstance(ports_list, dict):
                ports_list = [ports_list]

            for p in ports_list:
                if p.get('state',{}).get('@state')=='open':
                    svc = p.get('service',{})
                    version = " ".join(filter(None,[svc.get('@product'), svc.get('@version')]))
                    writer.writerow([
                        ip,
                        p.get('@portid'),
                        p.get('@protocol'),
                        'open',
                        svc.get('@name'),
                        version
                    ])
        csv_data = output.getvalue()
        output.close()
        return (
            csv_data, 200,
            {
                "Content-Type": "text/csv",
                "Content-Disposition": f"attachment; filename=scan_{scan_id}.csv"
            }
        )

    if fmt in ('txt','text'):
        txt = json.dumps(data, indent=2)
        return (
            txt, 200,
            {
                "Content-Type": "text/plain; charset=utf-8",
                "Content-Disposition": f"attachment; filename=scan_{scan_id}.txt"
            }
        )

    abort(404)