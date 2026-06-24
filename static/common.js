// common.js — shared helpers: theme, formatting, "last updated", auto-refresh

const $ = id => document.getElementById(id);
const fmt = n => (n == null ? '-' : Number(n).toLocaleString('en-US', { maximumFractionDigits: 2 }));

// ---------- light / dark theme ----------
function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  const b = $('themeBtn');
  if (b) b.textContent = t === 'light' ? '🌙' : '☀️';
}
function toggleTheme() {
  const cur = document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
  const next = cur === 'light' ? 'dark' : 'light';
  localStorage.setItem('theme', next);
  applyTheme(next);
}
applyTheme(localStorage.getItem('theme') || 'light');

// ---------- "x minutes ago" ----------
function timeAgo(iso) {
  if (!iso) return 'not updated yet';
  const sec = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (sec < 60) return 'just now';
  if (sec < 3600) return `${Math.floor(sec / 60)} min ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)} h ago`;
  return `${Math.floor(sec / 86400)} d ago`;
}

// ---------- auto refresh ----------
let _lastUpdated = null;
function startAutoRefresh(onNewData) {
  async function poll() {
    try {
      const s = await (await fetch('/api/status')).json();
      if (s.updated_at && s.updated_at !== _lastUpdated) {
        _lastUpdated = s.updated_at;
        onNewData(s);
      }
      renderUpdated();
    } catch (e) {}
  }
  poll();
  setInterval(poll, 60000);
  setInterval(renderUpdated, 20000);
}
function renderUpdated() {
  const el = $('updated');
  if (el) el.innerHTML = `<span class="dot"></span> updated ${timeAgo(_lastUpdated)}`;
}
function setUpdated(iso) { if (iso) { _lastUpdated = iso; renderUpdated(); } }

// ---------- manual refresh ----------
async function manualRefresh(after) {
  const btn = $('refreshBtn');
  if (btn) { btn.disabled = true; btn.textContent = '...'; }
  try {
    const r = await (await fetch('/api/refresh', { method: 'POST' })).json();
    setUpdated(r.updated_at);
    if (after) await after();
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '↻'; }
  }
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
    <div class="updated" id="updated"></div>
    <button class="iconbtn" id="refreshBtn" title="Refresh now" onclick="manualRefresh(window._reload)">↻</button>
    <button class="iconbtn" id="themeBtn" title="Toggle theme" onclick="toggleTheme()">☀️</button>
  </div>`;
}
