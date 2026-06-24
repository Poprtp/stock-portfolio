# -*- coding: utf-8 -*-
"""
core.py — Backend logic: multi-portfolio transactions, positions, analytics, cache.
Each transaction belongs to a named portfolio. Positions are DERIVED from the
buy/sell log using weighted-average cost. Realized P&L is tracked on sells.
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
PORT_FILE = os.path.join(BASE, "portfolio.csv")        # legacy (migrate once)
PORTFOLIOS_FILE = os.path.join(BASE, "portfolios.json")
TARGET_FILE = os.path.join(BASE, "target.json")
CACHE_FILE = os.path.join(BASE, "cache.json")

RANGES = {"1d": ("1d", "5m"), "7d": ("7d", "60m"),
          "30d": ("1mo", "1d"), "90d": ("3mo", "1d")}
TX_COLS = ["date", "ticker", "type", "shares", "price", "portfolio"]
DEFAULT_PF = "Main"


def clean(o):
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    return o


# ---------------- portfolios registry ----------------
def _read_names():
    if os.path.exists(PORTFOLIOS_FILE):
        try:
            n = json.load(open(PORTFOLIOS_FILE, encoding="utf-8")).get("names", [])
            return [str(x) for x in n if str(x).strip()]
        except Exception:
            return []
    return []


def _write_names(names):
    json.dump({"names": names}, open(PORTFOLIOS_FILE, "w", encoding="utf-8"), ensure_ascii=False)


def list_portfolios():
    names = _read_names()
    df = _read_all_tx()
    if not df.empty:
        for n in df["portfolio"].dropna().unique():
            if n not in names:
                names.append(str(n))
    if not names:
        names = [DEFAULT_PF]
    return names


def add_portfolio(name):
    name = str(name).strip()
    if not name:
        raise ValueError("empty name")
    names = list_portfolios()
    if name not in names:
        names.append(name)
        _write_names(names)
    return names


def remove_portfolio(name):
    name = str(name).strip()
    df = _read_all_tx()
    if not df.empty:
        df = df[df["portfolio"] != name]
        _write_all_tx(df)
    names = [n for n in list_portfolios() if n != name]
    if not names:
        names = [DEFAULT_PF]
    _write_names(names)
    return names


def resolve_pf(pf):
    names = list_portfolios()
    pf = (pf or "").strip()
    return pf if pf in names else names[0]


# ---------------- transactions ----------------
def _migrate():
    """Add portfolio column / import legacy portfolio.csv once."""
    if not os.path.exists(TX_FILE) and os.path.exists(PORT_FILE):
        try:
            df = pd.read_csv(PORT_FILE)
            df.columns = [c.strip().lower() for c in df.columns]
            rows = []
            today = date.today().isoformat()
            for _, r in df.iterrows():
                if float(r.get("shares", 0)) > 0:
                    rows.append({"date": today, "ticker": str(r["ticker"]).strip().upper(),
                                 "type": "BUY", "shares": float(r["shares"]),
                                 "price": float(r["cost_basis"]), "portfolio": DEFAULT_PF})
            if rows:
                pd.DataFrame(rows, columns=TX_COLS).to_csv(TX_FILE, index=False)
        except Exception as e:
            print("[migrate] skip:", e)


def _read_all_tx():
    _migrate()
    if not os.path.exists(TX_FILE):
        return pd.DataFrame(columns=TX_COLS)
    try:
        df = pd.read_csv(TX_FILE)
    except Exception:
        return pd.DataFrame(columns=TX_COLS)
    if df.empty:
        return pd.DataFrame(columns=TX_COLS)
    df.columns = [c.strip().lower() for c in df.columns]
    if "portfolio" not in df.columns:
        df["portfolio"] = DEFAULT_PF
    for c in TX_COLS:
        if c not in df.columns:
            df[c] = None
    df["portfolio"] = df["portfolio"].fillna(DEFAULT_PF).astype(str).str.strip().replace("", DEFAULT_PF)
    df["ticker"] = df["ticker"].astype(str).str.strip().str.upper()
    df["type"] = df["type"].astype(str).str.strip().str.upper()
    df["shares"] = pd.to_numeric(df["shares"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df.dropna(subset=["ticker", "shares", "price"])
    return df[TX_COLS]


def _write_all_tx(df):
    tmp = TX_FILE + ".tmp"
    df.to_csv(tmp, index=False)
    os.replace(tmp, TX_FILE)


def read_tx(pf):
    """Transactions for one portfolio (index = global id for delete)."""
    df = _read_all_tx()
    if df.empty:
        return df
    return df[df["portfolio"] == pf]


def add_tx(pf, tx_date, ticker, ttype, shares, price):
    pf = str(pf).strip() or DEFAULT_PF
    ticker = str(ticker).strip().upper()
    ttype = str(ttype).strip().upper()
    if ttype not in ("BUY", "SELL"):
        raise ValueError("type must be BUY or SELL")
    shares = float(shares); price = float(price)
    if shares <= 0 or price < 0:
        raise ValueError("invalid")
    if not tx_date:
        tx_date = date.today().isoformat()
    add_portfolio(pf)
    df = _read_all_tx()
    nr = pd.DataFrame([{"date": tx_date, "ticker": ticker, "type": ttype,
                        "shares": shares, "price": price, "portfolio": pf}])
    df = nr if df.empty else pd.concat([df, nr], ignore_index=True)
    df = df.sort_values("date", kind="stable").reset_index(drop=True)
    _write_all_tx(df)


def remove_tx(gid):
    df = _read_all_tx()
    if 0 <= gid < len(df):
        _write_all_tx(df.drop(index=gid).reset_index(drop=True))


# ---------------- positions ----------------
def compute_positions(pf):
    df = read_tx(pf)
    pos, realized = {}, {}
    if not df.empty:
        df = df.sort_values("date", kind="stable")
        for _, r in df.iterrows():
            t = r["ticker"]; q = float(r["shares"]); p = float(r["price"])
            d = pos.setdefault(t, {"shares": 0.0, "cost": 0.0})
            if r["type"] == "BUY":
                d["shares"] += q; d["cost"] += q * p
            else:
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


def read_positions(pf):
    return compute_positions(pf)[0]


def realized_total(pf):
    return round(sum(compute_positions(pf)[1].values()), 2)


def contributions(pf):
    df = read_tx(pf)
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


# ---------------- target / cache (per portfolio) ----------------
def _read_json(path, default):
    if os.path.exists(path):
        try:
            return json.load(open(path, encoding="utf-8"))
        except Exception:
            return default
    return default


def read_target(pf):
    return float(_read_json(TARGET_FILE, {}).get(pf, 0) or 0)


def write_target(pf, v):
    d = _read_json(TARGET_FILE, {})
    if not isinstance(d, dict):
        d = {}
    d[pf] = float(v)
    json.dump(d, open(TARGET_FILE, "w", encoding="utf-8"))


def read_cache():
    c = _read_json(CACHE_FILE, {})
    return c if isinstance(c, dict) else {}


def write_cache(data):
    tmp = CACHE_FILE + ".tmp"
    json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, CACHE_FILE)


def get_cache(pf):
    return read_cache().get("portfolios", {}).get(pf, {})


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
def compute_analyze(pf, rf=0.04):
    port = read_positions(pf)
    if port.empty:
        return None
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
    con = contributions(pf)
    total = {"market_value": round(tmv, 2), "cost_value": round(tc, 2),
             "pnl": round(tmv - tc, 2),
             "pnl_pct": round((tmv / tc - 1) * 100, 1) if tc else 0,
             "realized": realized_total(pf),
             "invested": con["invested"], "proceeds": con["proceeds"],
             "net_invested": con["net_invested"]}

    def recs(df):
        return [{k: clean(v) for k, v in r.items()} for r in df.to_dict(orient="records")]

    return {"pnl": recs(pnl), "trend": recs(trend), "risk": recs(risk),
            "summary": {k: clean(v) for k, v in summary.items()}, "total": total}


def compute_history(pf, rng):
    port = read_positions(pf)
    if port.empty:
        return None
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
    out = {"portfolios": {}}
    for pf in list_portfolios():
        port = read_positions(pf)
        if port.empty:
            out["portfolios"][pf] = {"updated_at": datetime.now(timezone.utc).isoformat(), "empty": True}
            continue
        try:
            history = {}
            for rng in RANGES:
                try:
                    history[rng] = compute_history(pf, rng)
                except Exception:
                    history[rng] = None
            out["portfolios"][pf] = {"updated_at": datetime.now(timezone.utc).isoformat(),
                                     "empty": False, "analyze": compute_analyze(pf), "history": history}
        except Exception as e:
            print("[refresh_cache]", pf, e)
            out["portfolios"][pf] = {"updated_at": datetime.now(timezone.utc).isoformat(), "empty": True}
    write_cache(out)
