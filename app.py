#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py — Flask backend (multi-portfolio).
  /           -> Dashboard
  /portfolio  -> Trades + holdings + analysis
Prices via yfinance (free). Auto-updates hourly into cache.json.
Login is disabled (open app).
"""
import os
import time
import threading
from datetime import datetime, timezone

from flask import Flask, request, jsonify, render_template

import core

UPDATE_INTERVAL = int(os.environ.get("UPDATE_INTERVAL_SEC", 3600))
app = Flask(__name__)


def pf_arg():
    return core.resolve_pf(request.args.get("pf") or (request.get_json(silent=True) or {}).get("pf"))


# ---------------- background updater ----------------
_started = False


def start_scheduler():
    global _started
    if _started:
        return
    _started = True

    def loop():
        if not core.read_cache().get("portfolios"):
            core.refresh_cache()
        while True:
            time.sleep(UPDATE_INTERVAL)
            core.refresh_cache()

    threading.Thread(target=loop, daemon=True).start()


def refresh_async():
    threading.Thread(target=core.refresh_cache, daemon=True).start()


# ---------------- portfolios ----------------
@app.get("/api/portfolios")
def api_portfolios():
    return jsonify({"names": core.list_portfolios()})


@app.post("/api/portfolios/add")
def api_pf_add():
    try:
        names = core.add_portfolio(request.get_json(force=True).get("name"))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid portfolio name"}), 400
    return jsonify({"ok": True, "names": names})


@app.post("/api/portfolios/remove")
def api_pf_remove():
    names = core.remove_portfolio(request.get_json(force=True).get("name"))
    refresh_async()
    return jsonify({"ok": True, "names": names})


# ---------------- transactions ----------------
@app.get("/api/transactions")
def api_tx_list():
    pf = pf_arg()
    df = core.read_tx(pf)
    out = [{"id": int(i), "date": r["date"], "ticker": r["ticker"], "type": r["type"],
            "shares": float(r["shares"]), "price": float(r["price"])} for i, r in df.iterrows()]
    return jsonify(out)


@app.post("/api/transactions/add")
def api_tx_add():
    d = request.get_json(force=True)
    try:
        core.add_tx(core.resolve_pf(d.get("pf")), d.get("date"), d.get("ticker"),
                    d.get("type"), d.get("shares"), d.get("price"))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid transaction. Check ticker / shares / price."}), 400
    refresh_async()
    return jsonify({"ok": True})


@app.post("/api/transactions/remove")
def api_tx_remove():
    try:
        core.remove_tx(int(request.get_json(force=True).get("id")))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid id"}), 400
    refresh_async()
    return jsonify({"ok": True})


@app.get("/api/positions")
def api_positions():
    pf = pf_arg()
    pos, realized = core.compute_positions(pf)
    rows = pos.to_dict(orient="records")
    for r in rows:
        r["realized"] = round(realized.get(r["ticker"], 0.0), 2)
    return jsonify({"positions": rows, "realized_total": round(sum(realized.values()), 2),
                    "contributions": core.contributions(pf)})


# ---------------- target / status / refresh ----------------
@app.get("/api/target")
def api_get_target():
    return jsonify({"target": core.read_target(pf_arg())})


@app.post("/api/target")
def api_set_target():
    d = request.get_json(force=True)
    try:
        core.write_target(core.resolve_pf(d.get("pf")), float(d.get("target", 0)))
    except (TypeError, ValueError):
        return jsonify({"error": "Target must be a number"}), 400
    return jsonify({"ok": True})


@app.get("/api/status")
def api_status():
    c = core.get_cache(pf_arg())
    return jsonify({"updated_at": c.get("updated_at"),
                    "has_data": bool(c.get("updated_at")) and not c.get("empty"),
                    "interval_sec": UPDATE_INTERVAL})


@app.post("/api/refresh")
def api_refresh():
    core.refresh_cache()
    return jsonify({"ok": True, "updated_at": core.get_cache(pf_arg()).get("updated_at")})


# ---------------- analytics ----------------
@app.get("/api/analyze")
def api_analyze():
    pf = pf_arg()
    c = core.get_cache(pf)
    if c.get("analyze"):
        return jsonify({**c["analyze"], "updated_at": c.get("updated_at")})
    a = core.compute_analyze(pf)
    if not a:
        return jsonify({"error": "No holdings yet. Add a buy transaction first."}), 400
    return jsonify({**a, "updated_at": datetime.now(timezone.utc).isoformat()})


@app.get("/api/history")
def api_history():
    pf = pf_arg()
    rng = request.args.get("range", "30d")
    c = core.get_cache(pf)
    if c.get("history", {}).get(rng):
        return jsonify({**c["history"][rng], "target": core.read_target(pf),
                        "updated_at": c.get("updated_at")})
    h = core.compute_history(pf, rng)
    if not h:
        return jsonify({"error": "No holdings yet. Add a buy transaction first."}), 400
    return jsonify({**h, "target": core.read_target(pf),
                    "updated_at": datetime.now(timezone.utc).isoformat()})


# ---------------- pages ----------------
@app.get("/")
def page_dashboard():
    return render_template("dashboard.html")


@app.get("/portfolio")
def page_portfolio():
    return render_template("portfolio.html")


start_scheduler()

if __name__ == "__main__":
    print("Open:  http://127.0.0.1:5000")
    app.run(host="0.0.0.0", debug=False, port=int(os.environ.get("PORT", 5000)))
