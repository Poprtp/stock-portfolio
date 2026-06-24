// portfolio.js — trades, holdings, money in/out, analysis (per portfolio)
$('topbar').innerHTML = topbar('pf');
applyTheme(localStorage.getItem('theme') || 'light');
$('date').value = new Date().toISOString().slice(0, 10);

function statCard(l, v, c) { return `<div class="stat"><div class="l">${l}</div><div class="v ${c || ''}">${v}</div></div>`; }
const reload = () => { loadTx(); loadPositions(); };

async function loadTx() {
  const d = await (await fetch(api('/api/transactions'))).json();
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
  const d = await (await fetch(api('/api/positions'))).json();
  let h = '';
  d.positions.forEach(p => {
    const c = p.realized >= 0 ? 'green' : 'red', s = p.realized > 0 ? '+' : '';
    h += `<tr><td>${p.ticker}</td><td>${fmt(p.shares)}</td><td>${fmt(p.cost_basis)}</td>
      <td class="${c}">${p.realized ? s + '$' + fmt(p.realized) : '-'}</td></tr>`;
  });
  $('postab').querySelector('tbody').innerHTML = h || '<tr><td colspan="4" style="color:var(--muted)">No holdings</td></tr>';
  const con = d.contributions || { invested: 0, proceeds: 0, net_invested: 0 }, rt = d.realized_total || 0;
  $('summary').innerHTML =
    statCard('Money In (Buys)', '$' + fmt(con.invested)) +
    statCard('Money Out (Sells)', '$' + fmt(con.proceeds)) +
    statCard('Net Invested', '$' + fmt(con.net_invested)) +
    statCard('Realized P/L', (rt >= 0 ? '+' : '') + '$' + fmt(rt), rt >= 0 ? 'green' : 'red');
}
async function addTx() {
  const body = { pf: getPF(), date: $('date').value, ticker: $('ticker').value.trim(),
    type: $('type').value, shares: $('shares').value, price: $('price').value };
  if (!body.ticker || !body.shares || !body.price) { alert('Please fill ticker, shares and price.'); return; }
  const d = await (await fetch('/api/transactions/add', { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })).json();
  if (d.error) { alert(d.error); return; }
  $('ticker').value = $('shares').value = $('price').value = '';
  reload();
}
async function rmTx(id) {
  await fetch('/api/transactions/remove', { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }) });
  reload();
}
async function delPortfolio() {
  const cur = getPF();
  if (!confirm(`Delete portfolio "${cur}" and all its trades? This cannot be undone.`)) return;
  const r = await (await fetch('/api/portfolios/remove', { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: cur }) })).json();
  localStorage.setItem('pf', (r.names && r.names[0]) || 'Main');
  await loadPortfolioSelector(reload); reload();
}
function pill(s) { const c = s === 'Bullish' ? 'bull' : s === 'Bearish' ? 'bear' : 'neut'; return `<span class="pill ${c}">${s}</span>`; }
function sig(s) {
  if (!s) return 'Neutral';
  if (s.includes('ขึ้น') || s.toLowerCase().includes('bull')) return 'Bullish';
  if (s.includes('ลง') || s.toLowerCase().includes('bear')) return 'Bearish';
  return 'Neutral';
}
async function analyze() {
  $('spin').style.display = 'inline';
  const d = await (await fetch(api('/api/analyze'))).json();
  $('spin').style.display = 'none';
  if (d.error) { alert(d.error); return; }
  setUpdated(d.updated_at); $('analysis').style.display = 'block';
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
window._reload = reload;
(async () => { await loadPortfolioSelector(reload); reload(); startAutoRefresh(() => loadPositions()); })();
