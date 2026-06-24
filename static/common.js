// common.js — shared helpers: theme, formatting, portfolios, auto-refresh

const $ = id => document.getElementById(id);
const fmt = n => (n == null ? '-' : Number(n).toLocaleString('en-US', { maximumFractionDigits: 2 }));

// ---------- theme ----------
function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  const b = $('themeBtn'); if (b) b.textContent = t === 'light' ? '🌙' : '☀️';
}
function toggleTheme() {
  const next = (document.documentElement.dataset.theme === 'light') ? 'dark' : 'light';
  localStorage.setItem('theme', next); applyTheme(next);
}
applyTheme(localStorage.getItem('theme') || 'light');

// ---------- current portfolio + pf-aware fetch ----------
function getPF() { return localStorage.getItem('pf') || ''; }
function api(path) {
  const sep = path.includes('?') ? '&' : '?';
  return path + sep + 'pf=' + encodeURIComponent(getPF());
}
async function loadPortfolioSelector(onChange) {
  window._onPFChange = onChange;
  const sel = $('pfSel'); if (!sel) return;
  const d = await (await fetch('/api/portfolios')).json();
  let cur = getPF();
  if (!d.names.includes(cur)) { cur = d.names[0]; localStorage.setItem('pf', cur); }
  sel.innerHTML = d.names.map(n => `<option ${n === cur ? 'selected' : ''}>${n}</option>`).join('');
  sel.onchange = () => { localStorage.setItem('pf', sel.value); onChange && onChange(); };
}
async function newPortfolio() {
  const name = (prompt('New portfolio name:') || '').trim();
  if (!name) return;
  await fetch('/api/portfolios/add', { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) });
  localStorage.setItem('pf', name);
  await loadPortfolioSelector(window._onPFChange);
  window._onPFChange && window._onPFChange();
}

// ---------- "x ago" + auto refresh ----------
function timeAgo(iso) {
  if (!iso) return 'not updated yet';
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}
let _lastUpdated = null;
function startAutoRefresh(onNewData) {
  async function poll() {
    try {
      const s = await (await fetch(api('/api/status'))).json();
      if (s.updated_at && s.updated_at !== _lastUpdated) { _lastUpdated = s.updated_at; onNewData(s); }
      renderUpdated();
    } catch (e) {}
  }
  poll(); setInterval(poll, 60000); setInterval(renderUpdated, 20000);
}
function renderUpdated() { const el = $('updated'); if (el) el.innerHTML = `<span class="dot"></span> updated ${timeAgo(_lastUpdated)}`; }
function setUpdated(iso) { if (iso) { _lastUpdated = iso; renderUpdated(); } }

async function manualRefresh(after) {
  const btn = $('refreshBtn'); if (btn) { btn.disabled = true; btn.textContent = '...'; }
  try {
    const r = await (await fetch(api('/api/refresh'), { method: 'POST' })).json();
    setUpdated(r.updated_at); if (after) await after();
  } finally { if (btn) { btn.disabled = false; btn.textContent = '↻'; } }
}

// ---------- top bar ----------
function topbar(active) {
  return `<div class="top">
    <span class="brand">📈 ROLLERCOASTER</span>
    <div class="links">
      <a href="/" ${active === 'dash' ? 'class="active"' : ''}>Dashboard</a>
      <a href="/portfolio" ${active === 'pf' ? 'class="active"' : ''}>Portfolio</a>
    </div>
    <div class="spacer"></div>
    <div class="pfpick">
      <select id="pfSel" title="Choose portfolio"></select>
      <button class="iconbtn" title="New portfolio" onclick="newPortfolio()">＋</button>
    </div>
    <div class="updated" id="updated"></div>
    <button class="iconbtn" id="refreshBtn" title="Refresh now" onclick="manualRefresh(window._reload)">↻</button>
    <button class="iconbtn" id="themeBtn" title="Toggle theme" onclick="toggleTheme()">☀️</button>
  </div>`;
}
