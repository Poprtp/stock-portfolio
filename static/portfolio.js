// portfolio.js — trades, holdings, analysis
$('topbar').innerHTML = topbar('pf');
applyTheme(localStorage.getItem('theme') || 'dark');
$('date').value = new Date().toISOString().slice(0, 10);

async function loadTx() {
  const d = await (await fetch('/api/transactions')).json();
  let h = '';
  d.slice().reverse().forEach(t => {
    const cls = t.type === 'BUY' ? 'buy' : 'sellp';
    h += `<tr><td>${t.date}</td><td>${t.ticker}</td>
      <td><span class="pill ${cls}">${t.type}</span></td>
      <td>${fmt(t.shares)}</td><td>${fmt(t.price)}</td>
      <td><button class="del" onclick="rmTx(${t.id})">×</button></td></tr>`;
  });
  $('txtab').querySelector('tbody').innerHTML = h || '<tr><td colspan="6" style="color:var(--muted)">No trades yet</td></tr>';
}
async function loadPositions() {
  const d = await (await fetch('/api/positions')).json();
  let h = '';
  d.positions.forEach(p => {
    const c = p.realized >= 0 ? 'green' : 'red', s = p.realized > 0 ? '+' : '';
    h += `<tr><td>${p.ticker}</td><td>${fmt(p.shares)}</td><td>${fmt(p.cost_basis)}</td>
      <td class="${c}">${p.realized ? s + '$' + fmt(p.realized) : '-'}</td></tr>`;
  });
  $('postab').querySelector('tbody').innerHTML = h || '<tr><td colspan="4" style="color:var(--muted)">No holdings</td></tr>';
  const rt = d.realized_total || 0, c = rt >= 0 ? 'green' : 'red', s = rt >= 0 ? '+' : '';
  $('realized').innerHTML = `Total realized P/L: <span class="${c}">${s}$${fmt(rt)}</span>`;
}
async function addTx() {
  const body = {
    date: $('date').value, ticker: $('ticker').value.trim(),
    type: $('type').value, shares: $('shares').value, price: $('price').value
  };
  if (!body.ticker || !body.shares || !body.price) { alert('Please fill ticker, shares and price.'); return; }
  const r = await fetch('/api/transactions/add', { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const d = await r.json();
  if (d.error) { alert(d.error); return; }
  $('ticker').value = $('shares').value = $('price').value = '';
  loadTx(); loadPositions();
}
async function rmTx(id) {
  await fetch('/api/transactions/remove', { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }) });
  loadTx(); loadPositions();
}
function pill(s) {
  const c = s.includes('Bull') ? 'bull' : s.includes('Bear') ? 'bear' : 'neut';
  return `<span class="pill ${c}">${s}</span>`;
}
async function analyze() {
  $('spin').style.display = 'inline';
  const d = await (await fetch('/api/analyze')).json();
  $('spin').style.display = 'none';
  if (d.error) { alert(d.error); return; }
  setUpdated(d.updated_at);
  $('analysis').style.display = 'block';
  let h = '';
  d.trend.forEach(p => { h += `<tr><td>${p.ticker}</td><td>${fmt(p.price)}</td><td>${fmt(p.SMA20)}</td>
    <td>${fmt(p.SMA50)}</td><td>${fmt(p.RSI14)}</td><td>${pill(sig(p.signal))}</td></tr>`; });
  $('trtab').querySelector('tbody').innerHTML = h;
  h = '';
  d.risk.forEach(p => { const c = p['ann_return_%'] >= 0 ? 'green' : 'red';
    h += `<tr><td>${p.ticker}</td><td class="${c}">${fmt(p['ann_return_%'])}%</td>
    <td>${fmt(p['volatility_%'])}%</td><td class="red">${fmt(p['max_drawdown_%'])}%</td>
    <td>${fmt(p.sharpe)}</td></tr>`; });
  $('rktab').querySelector('tbody').innerHTML = h;
}
// map Thai signal text from backend to English label
function sig(s) {
  if (!s) return 'Neutral';
  if (s.includes('ขึ้น') || s.toLowerCase().includes('bull')) return 'Bullish';
  if (s.includes('ลง') || s.toLowerCase().includes('bear')) return 'Bearish';
  return 'Neutral';
}
window._reload = () => { loadTx(); loadPositions(); };
loadTx(); loadPositions();
startAutoRefresh(() => { loadPositions(); });
