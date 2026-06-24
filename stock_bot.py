#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stock_bot.py — บอทพอร์ตหุ้นส่วนตัว (ฟรี ไม่ต้องเสียค่า API)
=============================================================
ดึงราคาหุ้นจากตลาดด้วย yfinance (ใช้ข้อมูล Yahoo Finance ฟรี ไม่ต้องมี API key)
แล้วคำนวณ:
  1) ผลตอบแทน / กำไรขาดทุน ของพอร์ต (P&L)
  2) แนวโน้มราคา (Trend): SMA20/50/200, RSI14, MACD พร้อมสัญญาณ
  3) ความเสี่ยง (Risk): ความผันผวน, Max Drawdown, Sharpe ratio,
     correlation ระหว่างหุ้น และความเสี่ยงระดับพอร์ต

วิธีใช้:
  1) ติดตั้งไลบรารี:  pip install yfinance pandas numpy openpyxl
  2) แก้ไฟล์ portfolio.csv ให้เป็นหุ้นของคุณ (ticker, shares, cost_basis)
  3) รัน:  python stock_bot.py
     - จะพิมพ์รายงานในหน้าจอ และบันทึกไฟล์ report.xlsx + report.html

ออปชัน:
  python stock_bot.py --portfolio myport.csv --period 1y --rf 0.045 --no-excel
"""

import argparse
import sys
from datetime import datetime

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    sys.exit("ยังไม่ได้ติดตั้ง yfinance — รัน:  pip install yfinance pandas numpy openpyxl")

TRADING_DAYS = 252  # จำนวนวันทำการต่อปี ใช้ปรับค่าความเสี่ยง/ผลตอบแทนเป็นรายปี


# ---------------------------------------------------------------------------
# 1) โหลดพอร์ต
# ---------------------------------------------------------------------------
def load_portfolio(path):
    """อ่าน portfolio.csv -> DataFrame คอลัมน์: ticker, shares, cost_basis"""
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    required = {"ticker", "shares", "cost_basis"}
    if not required.issubset(df.columns):
        sys.exit(f"portfolio.csv ต้องมีคอลัมน์: {required}")
    df["ticker"] = df["ticker"].str.strip().str.upper()
    df = df[df["shares"] > 0].reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# 2) ดึงราคาจากตลาด
# ---------------------------------------------------------------------------
def fetch_prices(tickers, period="1y"):
    """ดึงราคาปิด (Adj Close) ย้อนหลัง -> DataFrame (index=วันที่, คอลัมน์=ticker)"""
    raw = yf.download(tickers, period=period, auto_adjust=True,
                      progress=False, group_by="ticker")
    closes = {}
    for t in tickers:
        try:
            if len(tickers) == 1:
                closes[t] = raw["Close"]
            else:
                closes[t] = raw[t]["Close"]
        except (KeyError, TypeError):
            print(f"  [คำเตือน] ดึงข้อมูล {t} ไม่ได้ — ข้ามไป")
    prices = pd.DataFrame(closes).dropna(how="all")
    return prices


# ---------------------------------------------------------------------------
# 3) ตัวชี้วัดแนวโน้ม (Trend indicators)
# ---------------------------------------------------------------------------
def rsi(series, window=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = (-delta.clip(upper=0)).rolling(window).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line


def trend_analysis(prices):
    """คำนวณ SMA/RSI/MACD ของแต่ละหุ้น และสรุปสัญญาณแนวโน้ม"""
    rows = []
    for t in prices.columns:
        s = prices[t].dropna()
        if len(s) < 30:
            continue
        last = s.iloc[-1]
        sma20 = s.rolling(20).mean().iloc[-1]
        sma50 = s.rolling(50).mean().iloc[-1] if len(s) >= 50 else np.nan
        sma200 = s.rolling(200).mean().iloc[-1] if len(s) >= 200 else np.nan
        rsi14 = rsi(s).iloc[-1]
        macd_line, signal_line = macd(s)
        macd_hist = (macd_line - signal_line).iloc[-1]

        # ให้คะแนนแนวโน้มจากหลายสัญญาณ
        score = 0
        if last > sma20:
            score += 1
        if not np.isnan(sma50) and last > sma50:
            score += 1
        if not np.isnan(sma200) and last > sma200:
            score += 1
        if macd_hist > 0:
            score += 1
        if rsi14 > 55:
            score += 1
        elif rsi14 < 45:
            score -= 1

        if score >= 3:
            signal = "ขาขึ้น (Bullish)"
        elif score <= 1:
            signal = "ขาลง (Bearish)"
        else:
            signal = "ออกข้าง (Neutral)"

        rsi_note = "overbought" if rsi14 > 70 else "oversold" if rsi14 < 30 else ""
        rows.append({
            "ticker": t,
            "price": round(last, 2),
            "SMA20": round(sma20, 2),
            "SMA50": round(sma50, 2) if not np.isnan(sma50) else None,
            "SMA200": round(sma200, 2) if not np.isnan(sma200) else None,
            "RSI14": round(rsi14, 1),
            "RSI_note": rsi_note,
            "MACD_hist": round(macd_hist, 3),
            "signal": signal,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 4) ความเสี่ยง (Risk metrics)
# ---------------------------------------------------------------------------
def max_drawdown(cum):
    """Max Drawdown จากชุดมูลค่าสะสม (cumulative)"""
    peak = cum.cummax()
    dd = (cum - peak) / peak
    return dd.min()


def risk_per_stock(prices, rf=0.04):
    """ความผันผวนรายปี, Max Drawdown, Sharpe ของแต่ละหุ้น"""
    rows = []
    rets = prices.pct_change().dropna(how="all")
    for t in prices.columns:
        r = rets[t].dropna()
        if len(r) < 20:
            continue
        vol = r.std() * np.sqrt(TRADING_DAYS)
        ann_ret = (1 + r.mean()) ** TRADING_DAYS - 1
        sharpe = (ann_ret - rf) / vol if vol > 0 else np.nan
        cum = (1 + r).cumprod()
        mdd = max_drawdown(cum)
        rows.append({
            "ticker": t,
            "ann_return_%": round(ann_ret * 100, 1),
            "volatility_%": round(vol * 100, 1),
            "max_drawdown_%": round(mdd * 100, 1),
            "sharpe": round(sharpe, 2) if not np.isnan(sharpe) else None,
        })
    return pd.DataFrame(rows)


def portfolio_risk(prices, weights, rf=0.04):
    """ความเสี่ยง/ผลตอบแทนระดับพอร์ตจากน้ำหนักการลงทุนจริง"""
    rets = prices.pct_change().dropna()
    w = np.array([weights.get(t, 0) for t in prices.columns])
    if w.sum() == 0:
        return {}
    w = w / w.sum()
    port_ret = rets.values @ w
    port_ret = pd.Series(port_ret, index=rets.index)
    vol = port_ret.std() * np.sqrt(TRADING_DAYS)
    ann_ret = (1 + port_ret.mean()) ** TRADING_DAYS - 1
    sharpe = (ann_ret - rf) / vol if vol > 0 else np.nan
    cum = (1 + port_ret).cumprod()
    mdd = max_drawdown(cum)
    return {
        "ผลตอบแทนรายปี (คาดการณ์) %": round(ann_ret * 100, 1),
        "ความผันผวนรายปี %": round(vol * 100, 1),
        "Max Drawdown %": round(mdd * 100, 1),
        "Sharpe ratio": round(sharpe, 2) if not np.isnan(sharpe) else None,
    }


# ---------------------------------------------------------------------------
# 5) ผลตอบแทน / กำไรขาดทุน (P&L)
# ---------------------------------------------------------------------------
def compute_pnl(port, prices):
    """คำนวณมูลค่าตลาด, ต้นทุน, กำไร/ขาดทุน ของแต่ละหุ้นและรวมพอร์ต"""
    last_prices = prices.iloc[-1]
    rows = []
    for _, p in port.iterrows():
        t = p["ticker"]
        if t not in last_prices or pd.isna(last_prices[t]):
            continue
        price = last_prices[t]
        shares = p["shares"]
        cost = p["cost_basis"]
        mkt_val = price * shares
        cost_val = cost * shares
        pnl = mkt_val - cost_val
        pnl_pct = (price / cost - 1) * 100 if cost else np.nan
        rows.append({
            "ticker": t,
            "shares": shares,
            "cost_basis": round(cost, 2),
            "price": round(price, 2),
            "market_value": round(mkt_val, 2),
            "cost_value": round(cost_val, 2),
            "pnl": round(pnl, 2),
            "pnl_%": round(pnl_pct, 1),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["weight_%"] = (df["market_value"] / df["market_value"].sum() * 100).round(1)
    return df


# ---------------------------------------------------------------------------
# รายงาน
# ---------------------------------------------------------------------------
def print_report(pnl, trend, risk, port_summary):
    line = "=" * 64
    print(f"\n{line}\n  รายงานพอร์ตหุ้น  ({datetime.now():%Y-%m-%d %H:%M})\n{line}")

    if not pnl.empty:
        total_mv = pnl["market_value"].sum()
        total_cost = pnl["cost_value"].sum()
        total_pnl = total_mv - total_cost
        total_pct = (total_mv / total_cost - 1) * 100 if total_cost else 0
        print("\n[ 1 ] ผลตอบแทน / กำไรขาดทุน")
        print(pnl.to_string(index=False))
        print(f"\n  มูลค่าพอร์ตรวม : {total_mv:,.2f}")
        print(f"  ต้นทุนรวม      : {total_cost:,.2f}")
        emoji = "กำไร" if total_pnl >= 0 else "ขาดทุน"
        print(f"  {emoji}รวม      : {total_pnl:,.2f} ({total_pct:+.1f}%)")

    print("\n[ 2 ] แนวโน้มราคา (Trend)")
    print(trend.to_string(index=False) if not trend.empty else "  ไม่มีข้อมูลพอ")

    print("\n[ 3 ] ความเสี่ยงรายตัว")
    print(risk.to_string(index=False) if not risk.empty else "  ไม่มีข้อมูลพอ")

    print("\n[ 4 ] ความเสี่ยงระดับพอร์ต")
    for k, v in port_summary.items():
        print(f"  {k:32s}: {v}")
    print(f"\n{line}")


def save_excel(path, pnl, trend, risk, port_summary, corr):
    with pd.ExcelWriter(path, engine="openpyxl") as xl:
        pnl.to_excel(xl, sheet_name="PnL", index=False)
        trend.to_excel(xl, sheet_name="Trend", index=False)
        risk.to_excel(xl, sheet_name="Risk", index=False)
        pd.DataFrame(list(port_summary.items()),
                     columns=["metric", "value"]).to_excel(
            xl, sheet_name="Portfolio", index=False)
        if corr is not None:
            corr.round(2).to_excel(xl, sheet_name="Correlation")
    print(f"  บันทึก Excel : {path}")


def save_html(path, pnl, trend, risk, port_summary):
    css = "<style>body{font-family:sans-serif;margin:24px}table{border-collapse:collapse;margin:8px 0}td,th{border:1px solid #ccc;padding:4px 8px;font-size:13px}th{background:#f0f0f0}</style>"
    summ = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in port_summary.items())
    html = f"""<html><head><meta charset='utf-8'>{css}</head><body>
<h2>รายงานพอร์ตหุ้น — {datetime.now():%Y-%m-%d %H:%M}</h2>
<h3>1) กำไรขาดทุน (P&L)</h3>{pnl.to_html(index=False)}
<h3>2) แนวโน้มราคา</h3>{trend.to_html(index=False)}
<h3>3) ความเสี่ยงรายตัว</h3>{risk.to_html(index=False)}
<h3>4) ความเสี่ยงระดับพอร์ต</h3><table>{summ}</table>
</body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  บันทึก HTML  : {path}")


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="บอทพอร์ตหุ้น (yfinance ฟรี)")
    ap.add_argument("--portfolio", default="portfolio.csv")
    ap.add_argument("--period", default="1y",
                    help="ช่วงเวลา: 6mo, 1y, 2y, 5y, max")
    ap.add_argument("--rf", type=float, default=0.04,
                    help="อัตราผลตอบแทนปลอดความเสี่ยงต่อปี (เช่น 0.04 = 4%)")
    ap.add_argument("--no-excel", action="store_true")
    ap.add_argument("--no-html", action="store_true")
    args = ap.parse_args()

    port = load_portfolio(args.portfolio)
    tickers = port["ticker"].tolist()
    print(f"ดึงราคา {len(tickers)} ตัว: {', '.join(tickers)} (ช่วง {args.period}) ...")
    prices = fetch_prices(tickers, args.period)
    if prices.empty:
        sys.exit("ดึงราคาไม่สำเร็จ — ตรวจสอบอินเทอร์เน็ตหรือชื่อ ticker")

    pnl = compute_pnl(port, prices)
    trend = trend_analysis(prices)
    risk = risk_per_stock(prices, args.rf)
    weights = dict(zip(pnl["ticker"], pnl["market_value"])) if not pnl.empty else {}
    port_summary = portfolio_risk(prices, weights, args.rf)
    corr = prices.pct_change().corr() if prices.shape[1] > 1 else None

    print_report(pnl, trend, risk, port_summary)

    if not args.no_excel:
        try:
            save_excel("report.xlsx", pnl, trend, risk, port_summary, corr)
        except Exception as e:
            print(f"  [ข้าม Excel] {e}")
    if not args.no_html:
        save_html("report.html", pnl, trend, risk, port_summary)


if __name__ == "__main__":
    main()
