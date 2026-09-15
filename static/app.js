const deviceId = (() => {
  let id = localStorage.getItem('agro_device_id');
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem('agro_device_id', id);
  }
  return id;
})();

let currentState = null;
let currentVote = null;
let socket = null;
let reconnectTimer = null;

const $ = (id) => document.getElementById(id);
const waitingView = $('waitingView');
const questionView = $('questionView');
const finishedView = $('finishedView');
const connection = $('connection');

async function registerDevice() {
  await fetch('/api/register', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({device_id: deviceId})
  });
}

async function loadMyVote() {
  const r = await fetch(`/api/my-vote/${encodeURIComponent(deviceId)}`);
  const data = await r.json();
  currentVote = data.answer_index;
}

function setConnection(ok) {
  connection.textContent = ok ? '已连接' : '连接中';
  connection.classList.toggle('online', ok);
}

function connectWs() {
  clearTimeout(reconnectTimer);
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  socket = new WebSocket(`${proto}://${location.host}/ws/participant/${encodeURIComponent(deviceId)}`);
  socket.onopen = () => setConnection(true);
  socket.onclose = () => {
    setConnection(false);
    reconnectTimer = setTimeout(connectWs, 1200);
  };
  socket.onerror = () => socket.close();
  socket.onmessage = async (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === 'state') {
      const oldQ = currentState?.question?.id;
      currentState = msg.data;
      const newQ = currentState?.question?.id;
      if (oldQ !== newQ) await loadMyVote();
      render();
    }
  };
}

function showOnly(view) {
  [waitingView, questionView, finishedView].forEach(v => v.classList.add('hidden'));
  view.classList.remove('hidden');
}

function render() {
  if (!currentState || currentState.status === 'waiting') {
    showOnly(waitingView);
    return;
  }
  if (currentState.status === 'finished') {
    showOnly(finishedView);
    return;
  }
  const q = currentState.question;
  if (!q) {
    showOnly(waitingView);
    return;
  }
  showOnly(questionView);
  $('progress').textContent = `第 ${currentState.current_question + 1} / ${currentState.total_questions} 题`;
  $('questionTitle').textContent = q.title;
  $('questionSubtitle').textContent = q.subtitle || '';

  const options = $('options');
  options.innerHTML = '';
  q.options.forEach((label, i) => {
    const btn = document.createElement('button');
    btn.className = 'option-btn' + (currentVote === i ? ' selected' : '');
    btn.innerHTML = `<span class="option-prefix">${String.fromCharCode(65 + i)}</span>${escapeHtml(label)}`;
    btn.onclick = () => submitVote(i);
    options.appendChild(btn);
  });

  $('saveState').textContent = currentVote === null ? '选择会自动保存' : '已保存，可修改';
  const panel = $('resultPanel');
  panel.classList.toggle('hidden', !currentState.revealed);
  if (currentState.revealed) renderResults();
}

async function submitVote(index) {
  currentVote = index;
  render();
  $('saveState').textContent = '保存中…';
  try {
    const r = await fetch('/api/vote', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({device_id: deviceId, answer_index: index})
    });
    if (!r.ok) throw new Error('vote failed');
    $('saveState').textContent = '已保存，可修改';
  } catch (e) {
    $('saveState').textContent = '保存失败，请再点一次';
  }
}

function renderResults() {
  const q = currentState.question;
  const total = currentState.counts.reduce((a,b) => a+b, 0);
  const bars = $('bars');
  bars.innerHTML = '';
  q.options.forEach((label, i) => {
    const count = currentState.counts[i] || 0;
    const pct = total ? Math.round(count * 100 / total) : 0;
    const row = document.createElement('div');
    row.className = 'bar-row';
    row.innerHTML = `<div class="bar-label">${escapeHtml(label)}</div><div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div><div class="bar-value">${count} · ${pct}%</div>`;
    bars.appendChild(row);
  });
  const ai = $('aiPanel');
  const hasAI = q.ai_label || q.ai_reason;
  ai.classList.toggle('hidden', !hasAI);
  $('aiLabel').textContent = q.ai_label || '';
  $('aiReason').textContent = q.ai_reason || '';
}

function escapeHtml(s) {
  return String(s).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
}

(async function init(){
  await registerDevice();
  const state = await fetch('/api/state').then(r => r.json());
  currentState = state;
  await loadMyVote();
  render();
  connectWs();
})();
