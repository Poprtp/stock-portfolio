// dashboard.js — home dashboard with an animated rollercoaster P/L chart
$('topbar').innerHTML = topbar('dash');
applyTheme(localStorage.getItem('theme') || 'light');
let pieC, barC, curRange = localStorage.getItem('range') || '30d', targetVal = 0;
let lastProfits = null, lastUp = true, geo = null, animId = null, cartU = 0, lastTs = 0;
const COLORS = ['#f0866f', '#2f7d92', '#27a567', '#e5544b', '#e0a44a', '#7a5cc0', '#46b3a3', '#d96fa0'];
const css = v => getComputedStyle(document.body).getPropertyValue(v).trim() || '#888';

[...$('seg').children].forEach(b => b.classList.toggle('on', b.dataset.r === curRange));

async function loadTarget() {
  targetVal = ((await (await fetch(api('/api/target'))).json()).target) || 0;
  if (targetVal > 0) $('target').value = targetVal;
}
async function saveTarget() {
  const v = parseFloat($('target').value) || 0;
  await fetch('/api/target', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target: v, pf: getPF() }) });
  targetVal = v; load();
}
function updateProgress(value) {
  if (targetVal <= 0) {
    $('prog').style.width = '0%'; $('prog').textContent = 'no target';
    $('targetnote').textContent = 'Enter a target value and press Save.'; return;
  }
  const pct = Math.min(100, value / targetVal * 100);
  $('prog').style.width = pct.toFixed(1) + '%'; $('prog').textContent = pct.toFixed(0) + '%';
  const left = targetVal - value;
  $('targetnote').textContent = left > 0
    ? `$${fmt(left)} to reach your target of $${fmt(targetVal)}`
    : `🎉 Target reached! $${fmt(-left)} above goal`;
}
function statCard(l, v, c) { return `<div class="stat"><div class="l">${l}</div><div class="v ${c || ''}">${v}</div></div>`; }

async function load() {
  $('spin').style.display = 'inline';
  const [d, pj] = await Promise.all([
    (await fetch(api('/api/history?range=' + curRange))).json(),
    (await fetch(api('/api/positions'))).json()
  ]);
  $('spin').style.display = 'none';
  if (d.error) {
    $('stats').innerHTML = `<div class="stat"><div class="l">${d.error}</div></div>`;
    lastProfits = null; if (animId) cancelAnimationFrame(animId), animId = null;
    const cv = $('hist'); cv.getContext('2d').clearRect(0, 0, cv.width, cv.height);
    $('htab').querySelector('tbody').innerHTML = ''; return;
  }
  setUpdated(d.updated_at);
  const con = pj.contributions || { invested: 0, proceeds: 0 }, rt = pj.realized_total || 0;
  const up = d.current_profit >= 0, sg = up ? '+' : '';
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

  lastProfits = d.profit; lastUp = up;
  startCoaster();

  const labels = d.holdings.map(p => p.ticker);
  if (pieC) pieC.destroy(); if (barC) barC.destroy();
  pieC = new Chart($('pie'), { type: 'doughnut',
    data: { labels, datasets: [{ data: d.holdings.map(p => p.market_value), backgroundColor: COLORS, borderColor: css('--ink'), borderWidth: 2 }] },
    options: { plugins: { legend: { labels: { color: css('--text') } } } } });
  barC = new Chart($('bar'), { type: 'bar',
    data: { labels, datasets: [{ data: d.holdings.map(p => p.pnl), backgroundColor: d.holdings.map(p => p.pnl >= 0 ? css('--green') : css('--red')), borderColor: css('--ink'), borderWidth: 2 }] },
    options: { plugins: { legend: { display: false } }, scales: { x: { ticks: { color: css('--muted') } }, y: { ticks: { color: css('--muted') } } } } });
}

// ---------- build track geometry ----------
function buildGeo() {
  const cv = $('hist'); if (!cv || !lastProfits || lastProfits.length < 2) { geo = null; return; }
  const dpr = window.devicePixelRatio || 1;
  const cssW = cv.clientWidth || cv.parentElement.clientWidth || 600, cssH = 240;
  cv.width = cssW * dpr; cv.height = cssH * dpr;
  const ctx = cv.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const padL = 46, padR = 18, padT = 26, padB = 40, w = cssW - padL - padR, h = cssH - padT - padB;
  const p = lastProfits, mn = Math.min(...p), mx = Math.max(...p), span = (mx - mn) || 1;
  const pts = p.map((v, i) => ({ x: padL + (i / (p.length - 1)) * w, y: padT + (1 - (v - mn) / span) * h }));
  let total = 0; const cum = [0];
  for (let i = 1; i < pts.length; i++) { total += Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y); cum.push(total); }
  geo = { ctx, cssW, cssH, padL, padR, padT, baseY: padT + h + 20, pts, cum, total, mn, mx,
          railCol: lastUp ? css('--green') : css('--accent') };
}
function posAt(u) {
  const { pts, cum, total } = geo, dist = u * total;
  let i = 1; while (i < cum.length && cum[i] < dist) i++;
  if (i >= pts.length) i = pts.length - 1;
  const a = pts[i - 1], b = pts[i], seg = (cum[i] - cum[i - 1]) || 1, t = (dist - cum[i - 1]) / seg;
  return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t, ang: Math.atan2(b.y - a.y, b.x - a.x) };
}
function drawStatic() {
  const g = geo, ctx = g.ctx; ctx.clearRect(0, 0, g.cssW, g.cssH);
  const ink = css('--ink'), teal = css('--accent2');
  ctx.strokeStyle = ink; ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(g.padL - 12, g.baseY); ctx.lineTo(g.cssW - g.padR, g.baseY); ctx.stroke();
  // posts
  const step = Math.max(1, Math.floor(g.pts.length / 16));
  ctx.strokeStyle = teal; ctx.lineWidth = 3;
  for (let i = 0; i < g.pts.length; i += step) {
    ctx.beginPath(); ctx.moveTo(g.pts[i].x, g.pts[i].y + 6); ctx.lineTo(g.pts[i].x, g.baseY); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(g.pts[i].x - 5, g.baseY); ctx.lineTo(g.pts[i].x + 5, g.baseY); ctx.stroke();
  }
  // rails + rungs
  const gap = 5;
  ctx.strokeStyle = g.railCol; ctx.lineJoin = 'round'; ctx.lineCap = 'round';
  const rail = off => { ctx.beginPath(); g.pts.forEach((q, i) => i ? ctx.lineTo(q.x, q.y + off) : ctx.moveTo(q.x, q.y + off)); ctx.stroke(); };
  ctx.lineWidth = 3; rail(-gap); rail(gap);
  ctx.lineWidth = 2;
  for (let i = 0; i < g.pts.length; i++) { ctx.beginPath(); ctx.moveTo(g.pts[i].x, g.pts[i].y - gap); ctx.lineTo(g.pts[i].x, g.pts[i].y + gap); ctx.stroke(); }
  // label
  ctx.fillStyle = g.railCol; ctx.font = '14px Knewave, cursive';
  const lastV = lastProfits[lastProfits.length - 1];
  ctx.fillText((lastV >= 0 ? '+$' : '-$') + fmt(Math.abs(lastV)), g.padL, g.padT - 8);
}
function drawCart(u) {
  const g = geo, ctx = g.ctx, pos = posAt(u), ink = css('--ink');
  ctx.save(); ctx.translate(pos.x, pos.y - 7); ctx.rotate(pos.ang);
  const cw = 26, ch = 15;
  ctx.fillStyle = '#f4c64a'; ctx.strokeStyle = ink; ctx.lineWidth = 2;
  rr(ctx, -cw / 2, -ch, cw, ch, 4); ctx.fill(); ctx.stroke();
  ctx.fillStyle = ink;
  for (let k = -1; k <= 1; k++) { ctx.beginPath(); ctx.arc(k * 7, -ch - 2, 2.4, 0, 7); ctx.fill(); }
  // wheels
  ctx.fillStyle = ink; ctx.beginPath(); ctx.arc(-7, 1, 2.6, 0, 7); ctx.fill();
  ctx.beginPath(); ctx.arc(7, 1, 2.6, 0, 7); ctx.fill();
  ctx.restore();
}
function rr(ctx, x, y, w, h, r) { ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }
function frame(ts) {
  if (!geo) return;
  const dt = lastTs ? ts - lastTs : 16; lastTs = ts;
  cartU += dt / 9000; if (cartU > 1) cartU -= 1;        // ~9s per lap
  drawStatic(); drawCart(cartU);
  animId = requestAnimationFrame(frame);
}
function startCoaster() {
  if (animId) cancelAnimationFrame(animId);
  buildGeo(); if (!geo) return;
  lastTs = 0; animId = requestAnimationFrame(frame);
}

$('seg').addEventListener('click', e => {
  if (e.target.dataset.r) {
    curRange = e.target.dataset.r; localStorage.setItem('range', curRange);
    [...$('seg').children].forEach(b => b.classList.toggle('on', b === e.target)); load();
  }
});
window.addEventListener('resize', () => { if (lastProfits) startCoaster(); });
window._reload = load;
(async () => { await loadPortfolioSelector(load); await loadTarget(); load(); startAutoRefresh(() => load()); })();
