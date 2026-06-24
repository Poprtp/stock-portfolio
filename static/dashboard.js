// dashboard.js — home dashboard with rollercoaster P/L chart
$('topbar').innerHTML = topbar('dash');
applyTheme(localStorage.getItem('theme') || 'light');
let pieC, barC, curRange = localStorage.getItem('range') || '30d', targetVal = 0;
let lastProfits = null, lastUp = true;
const COLORS = ['#f0866f', '#2f7d92', '#27a567', '#e5544b', '#e0a44a', '#7a5cc0', '#46b3a3', '#d96fa0'];
const css = v => getComputedStyle(document.body).getPropertyValue(v).trim() || '#888';

[...$('seg').children].forEach(b => b.classList.toggle('on', b.dataset.r === curRange));

async function loadTarget() {
  const d = await (await fetch('/api/target')).json();
  targetVal = d.target || 0;
  if (targetVal > 0) $('target').value = targetVal;
}
async function saveTarget() {
  const v = parseFloat($('target').value) || 0;
  await fetch('/api/target', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target: v }) });
  targetVal = v; load();
}
function updateProgress(value) {
  if (targetVal <= 0) {
    $('prog').style.width = '0%'; $('prog').textContent = 'no target';
    $('targetnote').textContent = 'Enter a target value and press Save.'; return;
  }
  const pct = Math.min(100, value / targetVal * 100);
  $('prog').style.width = pct.toFixed(1) + '%';
  $('prog').textContent = pct.toFixed(0) + '%';
  const left = targetVal - value;
  $('targetnote').textContent = left > 0
    ? `$${fmt(left)} to reach your target of $${fmt(targetVal)}`
    : `🎉 Target reached! $${fmt(-left)} above goal`;
}
function statCard(l, v, c) { return `<div class="stat"><div class="l">${l}</div><div class="v ${c || ''}">${v}</div></div>`; }

async function load() {
  $('spin').style.display = 'inline';
  const [d, pj] = await Promise.all([
    (await fetch('/api/history?range=' + curRange)).json(),
    (await fetch('/api/positions')).json()
  ]);
  $('spin').style.display = 'none';
  if (d.error) { $('stats').innerHTML = `<div class="stat"><div class="l">${d.error}</div></div>`; return; }
  setUpdated(d.updated_at);
  const con = pj.contributions || { invested: 0, proceeds: 0 };
  const rt = pj.realized_total || 0;
  const up = d.current_profit >= 0, sg = d.current_profit >= 0 ? '+' : '';
  $('stats').innerHTML =
    statCard('Portfolio Value', '$' + fmt(d.current_value)) +
    statCard('Money In (Buys)', '$' + fmt(con.invested)) +
    statCard('Money Out (Sells)', '$' + fmt(con.proceeds)) +
    statCard('Realized P/L', (rt >= 0 ? '+' : '') + '$' + fmt(rt), rt >= 0 ? 'green' : 'red') +
    statCard('Unrealized P/L', `${sg}$${fmt(d.current_profit)} (${sg}${d.profit_pct}%)`, up ? 'green' : 'red');
  if (d.target != null) { targetVal = d.target; if (targetVal > 0 && !$('target').value) $('target').value = targetVal; }
  updateProgress(d.current_value);

  let h = '';
  d.holdings.forEach(p => { const c = p.pnl >= 0 ? 'green' : 'red', s = p.pnl >= 0 ? '+' : '';
    h += `<tr><td>${p.ticker}</td><td>${fmt(p.shares)}</td><td>${fmt(p.avg_cost)}</td>
      <td>${fmt(p.price)}</td><td>${fmt(p.market_value)}</td>
      <td class="${c}">${s}${fmt(p.pnl)}</td><td class="${c}">${s}${fmt(p.pnl_pct)}%</td></tr>`; });
  $('htab').querySelector('tbody').innerHTML = h;

  // rollercoaster
  lastProfits = d.profit; lastUp = up;
  drawCoaster();

  // allocation + p/l
  const labels = d.holdings.map(p => p.ticker);
  if (pieC) pieC.destroy(); if (barC) barC.destroy();
  pieC = new Chart($('pie'), { type: 'doughnut',
    data: { labels, datasets: [{ data: d.holdings.map(p => p.market_value), backgroundColor: COLORS,
      borderColor: css('--ink'), borderWidth: 2 }] },
    options: { plugins: { legend: { labels: { color: css('--text') } } } } });
  barC = new Chart($('bar'), { type: 'bar',
    data: { labels, datasets: [{ data: d.holdings.map(p => p.pnl),
      backgroundColor: d.holdings.map(p => p.pnl >= 0 ? css('--green') : css('--red')),
      borderColor: css('--ink'), borderWidth: 2 }] },
    options: { plugins: { legend: { display: false } },
      scales: { x: { ticks: { color: css('--muted') } }, y: { ticks: { color: css('--muted') } } } } });
}

// ---- draw a rollercoaster-style track of the profit line ----
function drawCoaster() {
  const cv = $('hist'); if (!cv || !lastProfits) return;
  const profits = lastProfits;
  const dpr = window.devicePixelRatio || 1;
  const cssW = cv.clientWidth || cv.parentElement.clientWidth || 600;
  const cssH = 240;
  cv.width = cssW * dpr; cv.height = cssH * dpr;
  const ctx = cv.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssW, cssH);
  if (profits.length < 2) return;

  const padL = 46, padR = 18, padT = 24, padB = 40;
  const w = cssW - padL - padR, h = cssH - padT - padB;
  const mn = Math.min(...profits), mx = Math.max(...profits), span = (mx - mn) || 1;
  const X = i => padL + (i / (profits.length - 1)) * w;
  const Y = v => padT + (1 - (v - mn) / span) * h;
  const baseY = padT + h + 20;
  const ink = css('--ink'), coral = css('--accent'), teal = css('--accent2');
  const railCol = lastUp ? css('--green') : coral;
  const pts = profits.map((v, i) => ({ x: X(i), y: Y(v) }));

  // ground line
  ctx.strokeStyle = ink; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(padL - 12, baseY); ctx.lineTo(cssW - padR, baseY); ctx.stroke();

  // zero reference (dashed) if 0 within range
  if (mn < 0 && mx > 0) {
    ctx.save(); ctx.setLineDash([5, 5]); ctx.strokeStyle = css('--muted'); ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(padL, Y(0)); ctx.lineTo(cssW - padR, Y(0)); ctx.stroke();
    ctx.restore();
    ctx.fillStyle = css('--muted'); ctx.font = "12px Quicksand, sans-serif";
    ctx.fillText('$0', 6, Y(0) + 4);
  }

  // support posts (teal) at intervals
  const step = Math.max(1, Math.floor(pts.length / 16));
  ctx.strokeStyle = teal; ctx.lineWidth = 3;
  for (let i = 0; i < pts.length; i += step) {
    ctx.beginPath(); ctx.moveTo(pts[i].x, pts[i].y + 6); ctx.lineTo(pts[i].x, baseY); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(pts[i].x - 5, baseY); ctx.lineTo(pts[i].x + 5, baseY); ctx.stroke();
  }

  // ladder track: two rails (offset vertically) + rungs
  const g = 5;
  const railPath = off => { ctx.beginPath(); pts.forEach((p, i) => i ? ctx.lineTo(p.x, p.y + off) : ctx.moveTo(p.x, p.y + off)); ctx.stroke(); };
  ctx.strokeStyle = railCol; ctx.lineJoin = 'round'; ctx.lineCap = 'round';
  ctx.lineWidth = 3; railPath(-g); railPath(g);
  ctx.lineWidth = 2;
  for (let i = 0; i < pts.length; i += 1) {
    ctx.beginPath(); ctx.moveTo(pts[i].x, pts[i].y - g); ctx.lineTo(pts[i].x, pts[i].y + g); ctx.stroke();
  }

  // cart at the end
  const last = pts[pts.length - 1];
  ctx.fillStyle = '#f4c64a'; ctx.strokeStyle = ink; ctx.lineWidth = 2;
  const cw = 26, ch = 15;
  roundRect(ctx, last.x - cw / 2, last.y - g - ch - 2, cw, ch, 4); ctx.fill(); ctx.stroke();
  ctx.fillStyle = ink;
  for (let k = -1; k <= 1; k++) { ctx.beginPath(); ctx.arc(last.x + k * 7, last.y - g - ch - 4, 2.4, 0, 7); ctx.fill(); }

  // last value label
  ctx.fillStyle = railCol; ctx.font = "14px Knewave, cursive";
  ctx.fillText((profits[profits.length - 1] >= 0 ? '+$' : '-$') + fmt(Math.abs(profits[profits.length - 1])), padL, padT - 8);
}
function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath(); ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}

$('seg').addEventListener('click', e => {
  if (e.target.dataset.r) {
    curRange = e.target.dataset.r;
    localStorage.setItem('range', curRange);
    [...$('seg').children].forEach(b => b.classList.toggle('on', b === e.target));
    load();
  }
});
window.addEventListener('resize', () => drawCoaster());
window._reload = load;
(async () => { await loadTarget(); load(); startAutoRefresh(() => load()); })();
