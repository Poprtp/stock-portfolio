// dashboard.js — home dashboard
$('topbar').innerHTML = topbar('dash');
applyTheme(localStorage.getItem('theme') || 'dark');
let histC, pieC, barC, curRange = localStorage.getItem('range') || '30d', targetVal = 0;
const COLORS = ['#8b7bff', '#34d399', '#f59e0b', '#fb7185', '#38bdf8', '#a855f7', '#2dd4bf', '#f472b6'];

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
    $('prog').style.width = '0%'; $('prog').textContent = 'no target set';
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
async function load() {
  $('spin').style.display = 'inline';
  const d = await (await fetch('/api/history?range=' + curRange)).json();
  $('spin').style.display = 'none';
  if (d.error) { $('stats').innerHTML = `<div class="stat"><div class="l">${d.error}</div></div>`; return; }
  setUpdated(d.updated_at);
  const cls = d.current_profit >= 0 ? 'green' : 'red', sg = d.current_profit >= 0 ? '+' : '';
  $('stats').innerHTML = `
    <div class="stat"><div class="l">Portfolio Value</div><div class="v">$${fmt(d.current_value)}</div></div>
    <div class="stat"><div class="l">Total Cost</div><div class="v">$${fmt(d.total_cost)}</div></div>
    <div class="stat"><div class="l">Unrealized P/L</div><div class="v ${cls}">${sg}$${fmt(d.current_profit)} (${sg}${d.profit_pct}%)</div></div>`;
  if (d.target != null) { targetVal = d.target; if (targetVal > 0 && !$('target').value) $('target').value = targetVal; }
  updateProgress(d.current_value);

  let h = '';
  d.holdings.forEach(p => { const c = p.pnl >= 0 ? 'green' : 'red', s = p.pnl >= 0 ? '+' : '';
    h += `<tr><td>${p.ticker}</td><td>${fmt(p.shares)}</td><td>${fmt(p.avg_cost)}</td>
      <td>${fmt(p.price)}</td><td>${fmt(p.market_value)}</td>
      <td class="${c}">${s}${fmt(p.pnl)}</td><td class="${c}">${s}${fmt(p.pnl_pct)}%</td></tr>`; });
  $('htab').querySelector('tbody').innerHTML = h;

  // history line
  const up = d.current_profit >= 0;
  if (histC) histC.destroy();
  histC = new Chart($('hist'), { type: 'line',
    data: { labels: d.labels, datasets: [{ label: 'Profit / Loss ($)', data: d.profit,
      borderColor: up ? '#34d399' : '#fb7185',
      backgroundColor: up ? 'rgba(52,211,153,.15)' : 'rgba(251,113,133,.15)',
      fill: true, tension: .25, pointRadius: 0, borderWidth: 2 }] },
    options: { plugins: { legend: { labels: { color: getComputedStyle(document.body).color } } },
      scales: { x: { ticks: { color: '#93a0c2', maxTicksLimit: 8 } },
        y: { ticks: { color: '#93a0c2', callback: v => '$' + v } } } } });

  // allocation + p/l charts
  const labels = d.holdings.map(p => p.ticker);
  if (pieC) pieC.destroy(); if (barC) barC.destroy();
  pieC = new Chart($('pie'), { type: 'doughnut',
    data: { labels, datasets: [{ data: d.holdings.map(p => p.market_value), backgroundColor: COLORS }] },
    options: { plugins: { legend: { labels: { color: getComputedStyle(document.body).color } } } } });
  barC = new Chart($('bar'), { type: 'bar',
    data: { labels, datasets: [{ data: d.holdings.map(p => p.pnl),
      backgroundColor: d.holdings.map(p => p.pnl >= 0 ? '#34d399' : '#fb7185') }] },
    options: { plugins: { legend: { display: false } },
      scales: { x: { ticks: { color: '#93a0c2' } }, y: { ticks: { color: '#93a0c2' } } } } });
}
$('seg').addEventListener('click', e => {
  if (e.target.dataset.r) {
    curRange = e.target.dataset.r;
    localStorage.setItem('range', curRange);
    [...$('seg').children].forEach(b => b.classList.toggle('on', b === e.target));
    load();
  }
});
window._reload = load;
(async () => { await loadTarget(); load(); startAutoRefresh(() => load()); })();
