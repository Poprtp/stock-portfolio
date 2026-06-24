#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py — Flask backend for the Stock Portfolio web app.
  Home page  /          -> Dashboard
  Manage     /portfolio -> Transactions (real buy/sell) + positions + analysis
Prices via yfinance (free). Auto-updates hourly into cache.json.
Password: set env DASH_PASSWORD or config.json {"password": "..."}.
"""
import os
import json
import time
import threading
from datetime import datetime, timezone

from flask import Flask, request, jsonify, render_template, Response

import core

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE, "config.json")
UPDATE_INTERVAL = int(os.environ.get("UPDATE_INTERVAL_SEC", 3600))

app = Flask(__name__)


# ---------------- auth ----------------
def get_password():
    pw = os.environ.get("DASH_PASSWORD", "").strip()
    if pw:
        return pw
    if os.path.exists(CONFIG_FILE):
        try:
            return str(json.load(open(CONFIG_FILE)).get("password", "")).strip()
        except Exception:
            return ""
    return ""


# Login disabled — the app is open (no password required).
# (get_password is kept only so share.py can still run without errors.)


# ---------------- background updater ----------------
_started = False


def start_scheduler():
    global _started
    if _started:
        return
    _started = True

    def loop():
        if not core.read_cache().get("updated_at"):
            core.refresh_cache()
        while True:
            time.sleep(UPDATE_INTERVAL)
            core.refresh_cache()

    threading.Thread(target=loop, daemon=True).start()


def refresh_async():
    threading.Thread(target=core.refresh_cache, daemon=True).start()


# ---------------- API: transactions ----------------
@app.get("/api/transactions")
def api_tx_list():
    df = core.read_tx()
    out = []
    for i, r in df.iterrows():
        out.append({"id": int(i), "date": r["date"], "ticker": r["ticker"],
                    "type": r["type"], "shares": float(r["shares"]), "price": float(r["price"])})
    return jsonify(out)


@app.post("/api/transactions/add")
def api_tx_add():
    d = request.get_json(force=True)
    try:
        core.add_tx(d.get("date"), d.get("ticker"), d.get("type"),
                    d.get("shares"), d.get("price"))
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
    pos, realized = core.compute_positions()
    rows = pos.to_dict(orient="records")
    for r in rows:
        r["realized"] = round(realized.get(r["ticker"], 0.0), 2)
    return jsonify({"positions": rows, "realized_total": round(sum(realized.values()), 2),
                    "contributions": core.contributions()})


# ---------------- API: target / status / refresh ----------------
@app.get("/api/target")
def api_get_target():
    return jsonify({"target": core.read_target()})


@app.post("/api/target")
def api_set_target():
    try:
        core.write_target(float(request.get_json(force=True).get("target", 0)))
    except (TypeError, ValueError):
        return jsonify({"error": "Target must be a number"}), 400
    return jsonify({"ok": True})


@app.get("/api/status")
def api_status():
    c = core.read_cache()
    return jsonify({"updated_at": c.get("updated_at"),
                    "has_data": bool(c.get("updated_at")) and not c.get("empty"),
                    "interval_sec": UPDATE_INTERVAL})


@app.post("/api/refresh")
def api_refresh():
    core.refresh_cache()
    return jsonify({"ok": True, "updated_at": core.read_cache().get("updated_at")})


# ---------------- API: analytics ----------------
@app.get("/api/analyze")
def api_analyze():
    c = core.read_cache()
    if c.get("analyze"):
        return jsonify({**c["analyze"], "updated_at": c.get("updated_at")})
    port = core.read_positions()
    if port.empty:
        return jsonify({"error": "No holdings yet. Add a buy transaction first."}), 400
    a = core.compute_analyze(port)
    if not a:
        return jsonify({"error": "Failed to fetch prices."}), 500
    return jsonify({**a, "updated_at": datetime.now(timezone.utc).isoformat()})


@app.get("/api/history")
def api_history():
    rng = request.args.get("range", "30d")
    c = core.read_cache()
    if c.get("history", {}).get(rng):
        return jsonify({**c["history"][rng], "target": core.read_target(),
                        "updated_at": c.get("updated_at")})
    port = core.read_positions()
    if port.empty:
        return jsonify({"error": "No holdings yet. Add a buy transaction first."}), 400
    h = core.compute_history(port, rng)
    if not h:
        return jsonify({"error": "Failed to fetch history."}), 500
    return jsonify({**h, "target": core.read_target(),
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
    print(f"Auto-updating prices every {UPDATE_INTERVAL}s")
    app.run(host="0.0.0.0", debug=False, port=int(os.environ.get("PORT", 5000)))
