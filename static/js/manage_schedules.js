// static/js/manage_schedules.js

document.addEventListener('DOMContentLoaded', async () => {
  const table = document.getElementById('schedules-table').querySelector('tbody');
  const banner = document.getElementById('banner');

  function showBanner(msg, color) {
    banner.textContent = msg;
    banner.style.display = 'block';
    banner.style.background = color;
    setTimeout(() => { banner.style.display = 'none'; }, 2000);
  }

  async function fetchSchedules() {
    const res = await fetch('/schedule/api');
    return await res.json();
  }

  function renderRow(s) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><input class="form-control" value="${s.target}" data-field="target"></td>
      <td><input class="form-control" value="${s.ports}" data-field="ports"></td>
      <td><input class="form-control" value="${s.flags}" data-field="flags"></td>
      <td><input class="form-control" type="datetime-local" value="${s.run_at.replace(' ', 'T').slice(0,16)}" data-field="run_at"></td>
      <td>
        ${['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map((d,i)=>`<label><input type="checkbox" data-field="days_of_week" value="${i}" ${s.days_of_week?.includes(i.toString())?'checked':''}>${d}</label>`).join(' ')}
      </td>
      <td><input type="checkbox" data-field="active" ${s.active ? 'checked' : ''}></td>
      <td>${s.next_run_time||''}</td>
      <td>
        <button class="btn btn-success save-btn">Save</button>
        <button class="btn btn-danger cancel-btn">Cancel</button>
        <button class="btn run-btn">Run Now</button>
      </td>
    `;
    // Save
    tr.querySelector('.save-btn').onclick = async () => {
      const payload = {};
      tr.querySelectorAll('[data-field]').forEach(input => {
        if (input.type === 'checkbox' && input.getAttribute('data-field') === 'days_of_week') {
          payload.days_of_week = payload.days_of_week || [];
          if (input.checked) payload.days_of_week.push(input.value);
        } else if (input.type === 'checkbox') {
          payload[input.getAttribute('data-field')] = input.checked;
        } else {
          payload[input.getAttribute('data-field')] = input.value;
        }
      });
      const res = await fetch(`/schedule/${s.job_id}/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) showBanner('Schedule updated!', '#cfc');
      else showBanner('Update failed', '#fcc');
      loadTable();
    };
    // Cancel
    tr.querySelector('.cancel-btn').onclick = async () => {
      await fetch(`/schedule/${s.job_id}/cancel`, { method: 'POST' });
      showBanner('Schedule cancelled', '#fcc');
      loadTable();
    };
    // Run Now
    tr.querySelector('.run-btn').onclick = async () => {
      await fetch(`/schedule/${s.job_id}/run`, { method: 'POST' });
      showBanner('Triggered', '#ccf');
    };
    return tr;
  }

  async function loadTable() {
    table.innerHTML = '';
    const schedules = await fetchSchedules();
    schedules.forEach(s => table.appendChild(renderRow(s)));
  }

  loadTable();
});
