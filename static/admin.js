let currentState = null;
let socket = null;
let reconnectTimer = null;
const $ = (id) => document.getElementById(id);

function setConnection(ok) {
  const el = $('adminConnection');
  el.textContent = ok ? '实时连接正常' : '正在重连';
  el.classList.toggle('online', ok);
}

function connectWs() {
  clearTimeout(reconnectTimer);
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  socket = new WebSocket(`${proto}://${location.host}/ws/admin`);
  socket.onopen = () => setConnection(true);
  socket.onclose = () => {
    setConnection(false);
    reconnectTimer = setTimeout(connectWs, 1200);
  };
  socket.onerror = () => socket.close();
  socket.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === 'state') {
      currentState = msg.data;
      renderState();
    }
  };
}

async function action(name) {
  if (name === 'reset' && !confirm('确定清空本次所有终端记录和选择吗？')) return;
  const r = await fetch(`/api/admin/${name}`, {method: 'POST'});
  if (!r.ok) return;
  const data = await r.json();
  currentState = data.state;
  renderState();
  if (name === 'reset') loadDevices();
}

function renderState() {
  if (!currentState) return;
  $('onlineCount').textContent = currentState.online;
  $('registeredCount').textContent = currentState.registered_devices;
  $('answeredCount').textContent = currentState.answered;
  $('questionNo').textContent = currentState.status === 'waiting'
    ? '-'
    : `${currentState.current_question + 1}/${currentState.total_questions}`;

  const q = currentState.question;
  $('adminQuestionTitle').textContent = q ? q.title : '等待开始';
  $('adminQuestionSubtitle').textContent = q?.subtitle || '';
  const revealBtn = $('revealBtn');
  revealBtn.textContent = currentState.revealed ? '隐藏结果' : '公布结果';
  revealBtn.dataset.action = currentState.revealed ? 'hide' : 'reveal';
  renderBars();
}

function renderBars() {
  const wrap = $('adminBars');
  wrap.innerHTML = '';
  const q = currentState?.question;
  if (!q) return;
  const total = currentState.counts.reduce((a,b) => a+b, 0);
  q.options.forEach((label, i) => {
    const count = currentState.counts[i] || 0;
    const pct = total ? Math.round(count * 100 / total) : 0;
    const row = document.createElement('div');
    row.className = 'bar-row';
    row.innerHTML = `<div class="bar-label">${escapeHtml(label)}</div><div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div><div class="bar-value">${count} · ${pct}%</div>`;
    wrap.appendChild(row);
  });
}

async function loadDevices() {
  const rows = await fetch('/api/admin/devices').then(r => r.json());
  const body = $('devicesBody');
  body.innerHTML = '';
  rows.forEach((row, i) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${i + 1}</td><td title="${escapeHtml(row.device_id)}">${escapeHtml(row.device_id)}</td><td>${escapeHtml(row.ip || '')}</td><td>${escapeHtml(row.first_seen || '')}</td><td>${escapeHtml(row.last_seen || '')}</td>`;
    body.appendChild(tr);
  });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
}

document.querySelectorAll('[data-action]').forEach(btn => {
  btn.addEventListener('click', () => action(btn.dataset.action));
});
$('refreshDevices').addEventListener('click', loadDevices);

(async function init(){
  currentState = await fetch('/api/state').then(r => r.json());
  renderState();
  await loadDevices();
  connectWs();
  setInterval(loadDevices, 10000);
})();
