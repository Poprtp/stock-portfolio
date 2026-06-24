# -*- coding: utf-8 -*-
"""
core.py — Backend logic: transactions, positions, analytics, cache
Positions (current holdings) are DERIVED from a real buy/sell transaction log,
using weighted-average cost basis. Realized P&L is tracked on sells.
"""
import os
import json
import math
from datetime import datetime, timezone, date

import pandas as pd
import yfinance as yf
import stock_bot as sb

BASE = os.path.dirname(os.path.abspath(__file__))
TX_FILE = os.path.join(BASE, "transactions.csv")
PORT_FILE = os.path.join(BASE, "portfolio.csv")   # legacy (used only to migrate)
TARGET_FILE = os.path.join(BASE, "target.json")
CACHE_FILE = os.path.join(BASE, "cache.json")

RANGES = {"1d": ("1d", "5m"), "7d": ("7d", "60m"),
          "30d": ("1mo", "1d"), "90d": ("3mo", "1d")}
TX_COLS = ["date", "ticker", "type", "shares", "price"]


def clean(o):
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    return o


# ---------------- transactions ----------------
def _migrate_from_portfolio():
    """ครั้งแรก: ถ้ายังไม่มี transactions.csv แต่มี portfolio.csv เดิม
    ให้สร้างรายการซื้อ (BUY) จากหุ้นที่ถืออยู่ เพื่อไม่ให้ข้อมูลหาย"""
    if os.path.exists(TX_FILE) or not os.path.exists(PORT_FILE):
        return
    try:
        df = pd.read_csv(PORT_FILE)
        df.columns = [c.strip().lower() for c in df.columns]
        rows = []
        today = date.today().isoformat()
        for _, r in df.iterrows():
            if float(r.get("shares", 0)) > 0:
                rows.append({"date": today, "ticker": str(r["ticker"]).strip().upper(),
                             "type": "BUY", "shares": float(r["shares"]),
                             "price": float(r["cost_basis"])})
        if rows:
            pd.DataFrame(rows, columns=TX_COLS).to_csv(TX_FILE, index=False)
    except Exception as e:
        print("[migrate] skip:", e)


def read_tx():
    _migrate_from_portfolio()
    if not os.path.exists(TX_FILE):
        return pd.DataFrame(columns=TX_COLS)
    try:
        df = pd.read_csv(TX_FILE)
    except Exception:
        return pd.DataFrame(columns=TX_COLS)
    if df.empty:
        return pd.DataFrame(columns=TX_COLS)
    df.columns = [c.strip().lower() for c in df.columns]
    for c in TX_COLS:
        if c not in df.columns:
            df[c] = None
    df["ticker"] = df["ticker"].astype(str).str.strip().str.upper()
    df["type"] = df["type"].astype(str).str.strip().str.upper()
    df["shares"] = pd.to_numeric(df["shares"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df.dropna(subset=["ticker", "shares", "price"])
    return df[TX_COLS].reset_index(drop=True)


def write_tx(df):
    tmp = TX_FILE + ".tmp"
    df.to_csv(tmp, index=False)
    os.replace(tmp, TX_FILE)


def add_tx(tx_date, ticker, ttype, shares, price):
    ticker = str(ticker).strip().upper()
    ttype = str(ttype).strip().upper()
    if ttype not in ("BUY", "SELL"):
        raise ValueError("type must be BUY or SELL")
    shares = float(shares); price = float(price)
    if shares <= 0 or price < 0:
        raise ValueError("shares/price invalid")
    if not tx_date:
        tx_date = date.today().isoformat()
    df = read_tx()
    nr = pd.DataFrame([{"date": tx_date, "ticker": ticker, "type": ttype,
                        "shares": shares, "price": price}])
    df = nr if df.empty else pd.concat([df, nr], ignore_index=True)
    df = df.sort_values("date", kind="stable").reset_index(drop=True)
    write_tx(df)


def remove_tx(idx):
    df = read_tx()
    if 0 <= idx < len(df):
        df = df.drop(index=idx).reset_index(drop=True)
        write_tx(df)


# ---------------- positions (derived) ----------------
def compute_positions(df=None):
    """คืน (positions_df[ticker,shares,cost_basis], realized_pnl_dict)
    ใช้ต้นทุนเฉลี่ยถ่วงน้ำหนัก (weighted-average cost)"""
    if df is None:
        df = read_tx()
    pos, realized = {}, {}
    if not df.empty:
        df = df.sort_values("date", kind="stable")
        for _, r in df.iterrows():
            t = r["ticker"]; q = float(r["shares"]); p = float(r["price"])
            d = pos.setdefault(t, {"shares": 0.0, "cost": 0.0})
            if r["type"] == "BUY":
                d["shares"] += q; d["cost"] += q * p
            else:  # SELL
                if d["shares"] > 1e-9:
                    avg = d["cost"] / d["shares"]
                    sold = min(q, d["shares"])
                    realized[t] = realized.get(t, 0.0) + (p - avg) * sold
                    d["shares"] -= sold; d["cost"] -= avg * sold
    rows = []
    for t, d in pos.items():
        if d["shares"] > 1e-6:
            rows.append({"ticker": t, "shares": round(d["shares"], 6),
                         "cost_basis": round(d["cost"] / d["shares"], 4)})
    return pd.DataFrame(rows, columns=["ticker", "shares", "cost_basis"]), realized


def read_positions():
    """หุ้นที่ถืออยู่ตอนนี้ (ใช้แทน portfolio เดิม)"""
    return compute_positions()[0]


def realized_total():
    return round(sum(compute_positions()[1].values()), 2)


def contributions(df=None):
    """แยกเงินที่ใส่เข้าพอร์ต (ซื้อ) กับเงินที่ถอนออก (ขาย)"""
    if df is None:
        df = read_tx()
    inv = pro = 0.0
    if not df.empty:
        for _, r in df.iterrows():
            amt = float(r["shares"]) * float(r["price"])
            if r["type"] == "BUY":
                inv += amt
            else:
                pro += amt
    return {"invested": round(inv, 2), "proceeds": round(pro, 2),
            "net_invested": round(inv - pro, 2)}


# ---------------- target / cache ----------------
def read_target():
    if os.path.exists(TARGET_FILE):
        try:
            return float(json.load(open(TARGET_FILE)).get("target", 0))
        except Exception:
            return 0.0
    return 0.0


def write_target(v):
    json.dump({"target": float(v)}, open(TARGET_FILE, "w"))


def read_cache():
    if os.path.exists(CACHE_FILE):
        try:
            return json.load(open(CACHE_FILE, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def write_cache(data):
    tmp = CACHE_FILE + ".tmp"
    json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, CACHE_FILE)


# ---------------- price fetch ----------------
def fetch_history_prices(tickers, period, interval):
    raw = yf.download(tickers, period=period, interval=interval,
                      auto_adjust=True, progress=False, group_by="ticker")
    closes = {}
    for t in tickers:
        try:
            closes[t] = raw["Close"] if len(tickers) == 1 else raw[t]["Close"]
        except (KeyError, TypeError):
            pass
    return pd.DataFrame(closes).ffill().dropna(how="any")


# ---------------- analytics ----------------
def compute_analyze(port, rf=0.04):
    prices = sb.fetch_prices(port["ticker"].tolist(), "1y")
    if prices is None or prices.empty:
        return None
    pnl = sb.compute_pnl(port, prices)
    trend = sb.trend_analysis(prices)
    risk = sb.risk_per_stock(prices, rf)
    weights = dict(zip(pnl["ticker"], pnl["market_value"])) if not pnl.empty else {}
    summary = sb.portfolio_risk(prices, weights, rf)
    tmv = float(pnl["market_value"].sum()) if not pnl.empty else 0
    tc = float(pnl["cost_value"].sum()) if not pnl.empty else 0
    realized = realized_total()
    contrib = contributions()
    total = {"market_value": round(tmv, 2), "cost_value": round(tc, 2),
             "pnl": round(tmv - tc, 2),
             "pnl_pct": round((tmv / tc - 1) * 100, 1) if tc else 0,
             "realized": realized,
             "invested": contrib["invested"], "proceeds": contrib["proceeds"],
             "net_invested": contrib["net_invested"]}

    def recs(df):
        return [{k: clean(v) for k, v in r.items()} for r in df.to_dict(orient="records")]

    return {"pnl": recs(pnl), "trend": recs(trend), "risk": recs(risk),
            "summary": {k: clean(v) for k, v in summary.items()}, "total": total}


def compute_history(port, rng):
    period, interval = RANGES.get(rng, RANGES["30d"])
    tickers = port["ticker"].tolist()
    shares = dict(zip(port["ticker"], port["shares"]))
    cost = dict(zip(port["ticker"], port["cost_basis"]))
    total_cost = float(sum(shares[t] * cost[t] for t in tickers))
    prices = fetch_history_prices(tickers, period, interval)
    if prices is None or prices.empty:
        return None
    value = sum(prices[t] * shares[t] for t in prices.columns if t in shares)
    profit = value - total_cost
    labels = [d.strftime("%m-%d %H:%M" if rng in ("1d", "7d") else "%Y-%m-%d")
              for d in value.index]
    values = [round(float(v), 2) for v in value.values]
    profits = [round(float(p), 2) for p in profit.values]
    last = prices.iloc[-1]
    holdings = []
    for t in tickers:
        if t not in last:
            continue
        price = float(last[t]); mv = price * shares[t]; cv = cost[t] * shares[t]
        holdings.append({"ticker": t, "shares": shares[t], "avg_cost": round(cost[t], 2),
                         "price": round(price, 2), "market_value": round(mv, 2),
                         "pnl": round(mv - cv, 2),
                         "pnl_pct": round((price / cost[t] - 1) * 100, 1) if cost[t] else 0})
    cur_v = values[-1] if values else 0
    cur_p = profits[-1] if profits else 0
    return {"range": rng, "labels": labels, "values": values, "profit": profits,
            "total_cost": round(total_cost, 2), "current_value": round(cur_v, 2),
            "current_profit": round(cur_p, 2),
            "profit_pct": round(cur_p / total_cost * 100, 1) if total_cost else 0,
            "holdings": holdings}


def refresh_cache():
    port = read_positions()
    if port.empty:
        write_cache({"updated_at": datetime.now(timezone.utc).isoformat(), "empty": True})
        return
    try:
        analyze = compute_analyze(port)
        history = {}
        for rng in RANGES:
            try:
                history[rng] = compute_history(port, rng)
            except Exception:
                history[rng] = None
        write_cache({"updated_at": datetime.now(timezone.utc).isoformat(),
                     "empty": False, "analyze": analyze, "history": history})
    except Exception as e:
        print("[refresh_cache] error:", e)
