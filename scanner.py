import os
import uuid
import time
import shlex
import json
import ipaddress
import math
import xmltodict
import subprocess
import concurrent.futures

from extensions import db, socketio
from models import ScanResult, ChangeLog


def run_scan(app, scan_id, target, ports, flags, mode, concurrency=None):
    """Background task that executes an nmap scan and updates the DB + emits events."""
    with app.app_context():
        scan_record = ScanResult.query.get(scan_id)
        if not scan_record:
            return

        # default concurrency
        if not isinstance(concurrency, int) or concurrency < 1:
            concurrency = app.config.get('DEFAULT_THREADS', 100)

        start_time = time.time()
        error_flag = False
        results_data = None

        def execute_nmap(target_spec, port_spec, extra_flags):
            """Run nmap, stream progress via socketio, parse XML to dict."""
            cmd = ["nmap", "-Pn"]
            if port_spec:
                cmd += ["-p", str(port_spec)]
            if extra_flags:
                try:
                    cmd += shlex.split(extra_flags)
                except ValueError:
                    cmd.append(extra_flags)

            xml_file = f"/tmp/nmap_{scan_id}_{uuid.uuid4().hex}.xml"
            cmd += ["-oX", xml_file]
            if "-v" not in extra_flags and "-d" not in extra_flags:
                cmd.append("-v")
            cmd.append(target_spec)

            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
                )
            except FileNotFoundError:
                socketio.emit('scan_error', {
                    'error': 'Nmap command not found. Install nmap and try again.',
                    'scan_id': scan_id
                })
                return None

            for line in proc.stdout:
                text = line.strip()
                if not text:
                    continue
                # progress events
                if "Discovered open port" in text:
                    socketio.emit('scan_update', {'message': text, 'scan_id': scan_id})
                elif "% done" in text:
                    try:
                        percent = float(text.split("%")[0].split()[-1])
                        socketio.emit('scan_progress', {
                            'percent': int(percent), 'scan_id': scan_id
                        })
                    except Exception:
                        pass
                    socketio.emit('scan_update', {'message': text, 'scan_id': scan_id})
                else:
                    socketio.emit('scan_update', {'message': text, 'scan_id': scan_id})

            proc.wait()
            if proc.returncode != 0:
                socketio.emit('scan_error', {
                    'error': f"nmap exited with code {proc.returncode}", 'scan_id': scan_id
                })
                return None

            try:
                with open(xml_file) as xf:
                    xml_content = xf.read()
            except Exception as e:
                socketio.emit('scan_error', {
                    'error': f"Failed to read XML output: {e}", 'scan_id': scan_id
                })
                return None
            finally:
                try: os.remove(xml_file)
                except OSError: pass

            try:
                return xmltodict.parse(xml_content)
            except Exception as e:
                socketio.emit('scan_error', {
                    'error': f"Failed to parse XML: {e}", 'scan_id': scan_id
                })
                return None

        mode = (mode or "Basic").capitalize()

        if mode == "Basic":
            # one-shot scan
            spec = ports.strip() or None
            res = execute_nmap(target, spec, flags or "")
            if res:
                results_data = res.get('nmaprun', res)
            else:
                error_flag = True

        else:
            # Threaded: either multiple hosts or per-port splitting
            try:
                if '/' in target or '-' in target:
                    net = ipaddress.ip_network(target, strict=False)
                    hosts_list = [str(h) for h in net.hosts()]
                else:
                    hosts_list = [target]
            except Exception:
                hosts_list = [target]

            # Many hosts -> parallel host scans
            if len(hosts_list) > 1:
                host_entries = []
                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=min(concurrency, len(hosts_list))
                ) as executor:
                    futures = {
                        executor.submit(execute_nmap, h, ports or None, flags or ""): h
                        for h in hosts_list
                    }
                    for future in concurrent.futures.as_completed(futures):
                        res = future.result()
                        if res:
                            host_data = res.get('nmaprun', {}).get('host')
                            if host_data:
                                host_entries.append(host_data)
                        else:
                            error_flag = True

                combined = {'nmaprun': {
                    'host': host_entries if len(host_entries)>1 else host_entries[0]
                }}
                total = len(hosts_list)
                up = len(host_entries)
                down = total - up
                elapsed = time.time() - start_time
                ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

                combined['nmaprun']['runstats'] = {
                    'finished': {
                        '@time': str(int(time.time())),
                        '@timestr': ts,
                        '@elapsed': f"{elapsed:.2f}",
                        '@summary': f"Nmap done at {ts}; {total} IP address(es) ({up} host(s) up) scanned in {elapsed:.2f} seconds",
                        '@exit': 'success'
                    },
                    'hosts': {'@up': str(up), '@down': str(down), '@total': str(total)}
                }
                results_data = combined

            else:
                # single host, split ports
                if ports.strip():
                    # build full port list
                    parts = ports.replace(' ','').split(',')
                    port_nums = []
                    for p in parts:
                        if '-' in p:
                            a,b = p.split('-',1)
                            try:
                                port_nums += list(range(int(a), int(b)+1))
                            except: pass
                        else:
                            try: port_nums.append(int(p))
                            except: pass
                    port_nums = sorted(set(port_nums))

                    if port_nums:
                        num_threads = min(concurrency, len(port_nums))
                        chunk = math.ceil(len(port_nums)/num_threads)
                        partial = []
                        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
                            futures = []
                            for i in range(num_threads):
                                subset = port_nums[i*chunk:(i+1)*chunk]
                                if not subset: continue
                                spec = ",".join(map(str, subset))
                                futures.append(
                                    executor.submit(execute_nmap, target, spec, flags or "")
                                )
                            for fut in concurrent.futures.as_completed(futures):
                                res = fut.result()
                                if res:
                                    hd = res.get('nmaprun', {}).get('host')
                                    if hd:
                                        partial.append(hd)
                                else:
                                    error_flag = True

                        if partial:
                            base = partial[0]
                            merged_ports = []
                            for h in partial:
                                ports_block = h.get('ports',{}).get('port')
                                if ports_block:
                                    merged_ports += (ports_block if isinstance(ports_block,list) else [ports_block])
                            try:
                                merged_ports.sort(key=lambda x: int(x.get('@portid',0)))
                            except:
                                pass
                            ps = base.setdefault('ports',{})
                            ps['port'] = merged_ports
                            combined = {'nmaprun': {'host': base}}
                            elapsed = time.time()-start_time
                            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                            combined['nmaprun']['runstats'] = {
                                'finished': {
                                    '@time': str(int(time.time())),
                                    '@timestr': ts,
                                    '@elapsed': f"{elapsed:.2f}",
                                    '@summary': f"Nmap done at {ts}; 1 IP address (1 host up) scanned in {elapsed:.2f} seconds",
                                    '@exit': 'success'
                                },
                                'hosts': {'@up':'1','@down':'0','@total':'1'}
                            }
                            results_data = combined
                        else:
                            error_flag = True
                    else:
                        # no ports after parse, fallback
                        res = execute_nmap(target, None, flags or "")
                        if res:
                            results_data = res.get('nmaprun', res)
                        else:
                            error_flag = True
                else:
                    # no ports specified => single call
                    res = execute_nmap(target, None, flags or "")
                    if res:
                        results_data = res.get('nmaprun', res)
                    else:
                        error_flag = True

        # finalize DB record
        if error_flag or not results_data:
            scan_record.status = "Failed"
            scan_record.results_json = None
        else:
            scan_record.status = "Completed"
            try:
                scan_record.results_json = json.dumps(results_data)
            except TypeError:
                scan_record.results_json = json.dumps(results_data, default=str)

        db.session.commit()
        socketio.emit('scan_complete', {'scan_id': scan_id})

        # record service changes if any
        if scan_record.status == "Completed":
            record_changes(scan_record)


def record_changes(scan):
    """Compare to previous completed scan on same target and log added/removed ports."""
    prev = (
        ScanResult.query
        .filter(ScanResult.target == scan.target,
                ScanResult.id < scan.id,
                ScanResult.status == 'Completed')
        .order_by(ScanResult.id.desc())
        .first()
    )
    if not prev:
        return

    def extract_services(json_root):
        hosts = json_root.get('host') or []
        if not isinstance(hosts, list):
            hosts = [hosts]
        services = set()
        for h in hosts:
            ports = h.get('ports', {}).get('port') or []
            if isinstance(ports, dict):
                ports = [ports]
            for p in ports:
                if p.get('state', {}).get('@state') == 'open':
                    svc = p.get('service', {})
                    services.add((p.get('@portid'), svc.get('@name')))
        return services

    old_json = json.loads(prev.results_json)
    new_json = json.loads(scan.results_json)
    old_set = extract_services(old_json.get('nmaprun', old_json))
    new_set = extract_services(new_json.get('nmaprun', new_json))

    added   = list(new_set - old_set)
    removed = list(old_set - new_set)

    if added or removed:
        change = ChangeLog(
            scan_id=scan.id,
            changes={'added': added, 'removed': removed}
        )
        db.session.add(change)
        db.session.commit()