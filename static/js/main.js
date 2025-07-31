document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('scanForm');
  const targetInput = document.getElementById('target');
  const portsInput = document.getElementById('ports');
  const consoleArea = document.getElementById('consoleArea');
  const progressBar = document.getElementById('progress');
  form.addEventListener('submit', async e => {
    e.preventDefault();
    consoleArea.innerHTML = '';
    progressBar.value = 0;
    progressBar.style.display = 'block';
    const target = targetInput.value.trim();
    const ports = portsInput.value.trim();
    // TODO: validate target & ports here before sending
    const res = await fetch('/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target, ports })
    });
    const data = await res.json();
    if (!res.ok) {
      consoleArea.innerHTML = `<span class="text-danger">Error: ${data.error}</span>`;
      progressBar.style.display = 'none';
      return;
    }
    const socket = io();
    socket.emit('join', { scan_id: data.scan_id });
    socket.on('scan_update', msg => {
      consoleArea.innerHTML += `<div>${msg.message}</div>`;
    });
    socket.on('scan_progress', pct => {
      progressBar.value = pct;
    });
    socket.on('scan_complete', () => {
      consoleArea.innerHTML += `<div>-- Scan completed --</div>`;
      progressBar.value = 100;
    });
  });
});
// --- Validation helpers ---
function isValidIPorCIDR(str) {
  const ipv4 = /^(?:\d{1,3}\.){3}\d{1,3}(?:\/\d{1,2})?$/;
  const ipv6 = /^[0-9A-Fa-f:]+$/;
  return ipv4.test(str.trim()) || ipv6.test(str.trim());
}

function isValidPorts(str) {
  if (!str) return true;
  if (!/^[\d,\-\s]+$/.test(str)) return false;
  return str.split(/\s*,\s*/).every(part => {
    if (part.includes('-')) {
      const [a,b] = part.split('-',2).map(x=>parseInt(x,10));
      return Number.isInteger(a) && Number.isInteger(b)
          && a>0 && b>=a && b<=65535;
    } else {
      const p = parseInt(part,10);
      return Number.isInteger(p) && p>=1 && p<=65535;
    }
  });
}
// Schedule Scan
document.getElementById('schedule-form').addEventListener('submit', async e => {
  e.preventDefault();
  let form = e.target, data = new FormData(form);
  let obj = {};
  data.forEach((v,k)=>obj[k]=v);
  let res = await fetch('/schedule/submit', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify(obj)
  });
  let json = await res.json();
  let div = document.getElementById('schedule-result');
  if (json.error) {
    div.innerHTML = '<span class="text-danger">'+json.error+'</span>';
  } else {
    div.innerHTML = '<span class="text-success">Scheduled (job: '+json.job_id+')</span>';
  }
});
// static/js/main.js

// Establish WebSocket connection using Socket.IO
const socket = io();

// DOM references
const targetInput      = document.getElementById("target");
const portsInput       = document.getElementById("ports");
const modeElems        = document.getElementsByName("mode");
const threadsInput     = document.getElementById("threads");
const presetSelect     = document.getElementById("presetSelect");
const customFlagsInput = document.getElementById("customFlags");
const cmdInput         = document.getElementById("nmapCmd");
const scanBtn          = document.getElementById("scanBtn");
const progressBar      = document.getElementById("progress");
const outputEl         = document.getElementById("output");

// Determine default threads from the page
const defaultThreads = parseInt(threadsInput.value, 10) || 100;

// Build and update the live Nmap command string
function updateCmd() {
  const target = targetInput.value.trim() || "<target>";
  const ports  = portsInput.value.trim();
  const preset = presetSelect.value;
  const flags  = (preset === "custom")
    ? customFlagsInput.value.trim()
    : preset;

  let cmd = "nmap -Pn";
  if (ports) cmd += ` -p ${ports}`;
  if (flags) cmd += ` ${flags}`;
  cmd += ` ${target}`;

  cmdInput.value = cmd;
}

// Show/hide custom flags field and update command on preset change
presetSelect.addEventListener("change", () => {
  if (presetSelect.value === "custom") {
    customFlagsInput.style.display = "inline-block";
  } else {
    customFlagsInput.style.display = "none";
    customFlagsInput.value = "";
  }
  updateCmd();
});

// Rebuild command when inputs change
[targetInput, portsInput, customFlagsInput].forEach(el =>
  el.addEventListener("input", updateCmd)
);

// Initialize the command box on page load
updateCmd();

// Handle form submission for starting a scan
scanBtn.addEventListener("click", () => {
  const target = targetInput.value.trim();
  const ports = portsInput.value.trim();
  if (!isValidIPorCIDR(target)) {
    alert("Enter a valid IPv4/IPv6 or CIDR");
    return;
  }
  if (!isValidPorts(ports)) {
    alert("Ports must be comma/range list within 1–65535");
    return;
  }
  let mode = "Basic";
  modeElems.forEach(el => {
    if (el.checked) mode = el.value;
  });
  const threads = parseInt(threadsInput.value, 10) || defaultThreads;
  const preset = presetSelect.value;
  const custom_flags = customFlagsInput.value.trim();
  // Disable UI while scan is running
  scanBtn.disabled = true;
  outputEl.textContent = "";
  if (progressBar) {
    progressBar.value = 0;
    progressBar.style.display = "block";
  }
  fetch("/scan", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ target, ports, mode, threads, preset, custom_flags })
  })
  .then(res => res.json())
  .then(data => {
    if (data.error) {
      alert("Failed to start scan: " + data.error);
      scanBtn.disabled = false;
      if (progressBar) progressBar.style.display = "none";
    }
  })
  .catch(() => {
    alert("Failed to start scan.");
    scanBtn.disabled = false;
    if (progressBar) progressBar.style.display = "none";
  });
});

// WebSocket events for real-time updates
socket.on("scan_update", data => {
  outputEl.textContent += data.message + "\n";
  outputEl.scrollTop = outputEl.scrollHeight;
});

socket.on("scan_progress", data => {
  if (data.percent !== undefined && progressBar) {
    progressBar.style.display = "block";
    progressBar.value = data.percent;
  }
});

socket.on("scan_error", data => {
  outputEl.textContent += "ERROR: " + (data.error || "Scan error") + "\n";
  scanBtn.disabled = false;
  if (progressBar) progressBar.style.display = "none";
});

socket.on("scan_complete", () => {
  outputEl.textContent += "-- Scan completed --\n";
  scanBtn.disabled = false;
  if (progressBar) {
    progressBar.style.display = "none";
    progressBar.value = 0;
  }
});