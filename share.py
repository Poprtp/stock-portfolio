#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
share.py — เปิดพอร์ตหุ้นให้เข้าจากที่ไหนก็ได้ (รวมถึง iPhone บนเน็ตมือถือ)
==========================================================================
ใช้ Cloudflare Tunnel (cloudflared) สร้างลิงก์ HTTPS สาธารณะให้ฟรี ไม่ต้องสมัครสมาชิก

เตรียมครั้งเดียว: ติดตั้ง cloudflared
  • Windows (วิธีง่าย):  winget install --id Cloudflare.cloudflared
  • หรือดาวน์โหลด cloudflared.exe จาก
    https://github.com/cloudflare/cloudflared/releases/latest
    แล้ววางไว้ในโฟลเดอร์เดียวกับไฟล์นี้

วิธีใช้:
  python share.py
แล้วหน้าเว็บลิงก์ + QR code จะเด้งขึ้นมา — เอา iPhone สแกน QR เปิดได้เลย
(ปิดการแชร์: ปิดหน้าต่างนี้ หรือกด Ctrl+C)

** แนะนำให้ตั้งรหัสผ่านก่อนแชร์ออกเน็ต ** (กันคนอื่นเข้าถึงพอร์ต)
  สร้างไฟล์ config.json ในโฟลเดอร์นี้:  {"password": "รหัสที่คุณตั้ง"}
"""
import os
import re
import sys
import time
import shutil
import socket
import subprocess
import threading
import webbrowser

BASE = os.path.dirname(os.path.abspath(__file__))
PORT = 5000


def start_server():
    """รันเว็บแอป Flask เป็น background"""
    sys.path.insert(0, BASE)
    import app
    app.app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)


def wait_port(port, timeout=15):
    for _ in range(timeout * 2):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.5)
    return False


def find_cloudflared():
    exe = shutil.which("cloudflared")
    if exe:
        return exe
    for name in ("cloudflared.exe", "cloudflared"):
        p = os.path.join(BASE, name)
        if os.path.exists(p):
            return p
    return None


def write_link_page(url, has_password):
    qr = "https://api.qrserver.com/v1/create-qr-code/?size=260x260&data=" + url
    lock = ("<p style='color:#22c55e'>🔒 ตั้งรหัสผ่านไว้แล้ว — ต้องล็อกอินก่อนเข้า</p>"
            if has_password else
            "<p style='color:#f59e0b'>⚠️ ยังไม่ได้ตั้งรหัสผ่าน ใครมีลิงก์นี้ก็เข้าได้ "
            "(ตั้งได้ในไฟล์ config.json)</p>")
    html = f"""<!doctype html><html lang="th"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>แชร์พอร์ต</title>
<style>body{{font-family:'Segoe UI',Tahoma,sans-serif;background:#0f172a;color:#e2e8f0;
text-align:center;padding:40px}}.card{{background:#1e293b;max-width:480px;margin:0 auto;
padding:30px;border-radius:16px}}a{{color:#6366f1;font-size:18px;word-break:break-all}}
img{{margin:20px 0;border-radius:12px;background:#fff;padding:10px}}
.hint{{color:#94a3b8;font-size:14px}}</style></head><body><div class="card">
<h2>📱 เปิดพอร์ตบนมือถือ</h2>
<p class="hint">เอา iPhone สแกน QR นี้ หรือเปิดลิงก์ด้านล่าง</p>
<img src="{qr}" alt="QR"><br>
<a href="{url}/dashboard" target="_blank">{url}/dashboard</a>
{lock}
<p class="hint">ลิงก์นี้ใช้ได้ตราบเท่าที่หน้าต่าง share.py ยังเปิดอยู่<br>
ปิดเมื่อไหร่ ลิงก์ก็หยุดทำงาน (รันใหม่จะได้ลิงก์ใหม่)</p>
</div></body></html>"""
    path = os.path.join(BASE, "share_link.html")
    open(path, "w", encoding="utf-8").write(html)
    return path


def main():
    cf = find_cloudflared()
    if not cf:
        print("\n[!] ไม่พบ cloudflared — ติดตั้งก่อนด้วยคำสั่ง:")
        print("    winget install --id Cloudflare.cloudflared")
        print("    หรือดาวน์โหลด cloudflared.exe มาวางในโฟลเดอร์นี้")
        print("    https://github.com/cloudflare/cloudflared/releases/latest\n")
        sys.exit(1)

    print("เริ่มเว็บแอป...")
    threading.Thread(target=start_server, daemon=True).start()
    if not wait_port(PORT):
        print("[!] เซิร์ฟเวอร์ไม่ขึ้น ตรวจสอบว่าติดตั้ง flask/yfinance ครบ")
        sys.exit(1)

    print("สร้างลิงก์สาธารณะผ่าน Cloudflare...")
    proc = subprocess.Popen(
        [cf, "tunnel", "--url", f"http://localhost:{PORT}"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1)

    url = None
    for line in proc.stdout:
        m = re.search(r"https://[-\w.]+\.trycloudflare\.com", line)
        if m:
            url = m.group(0)
            break

    if not url:
        print("[!] สร้างลิงก์ไม่สำเร็จ ลองรันใหม่อีกครั้ง")
        proc.terminate()
        sys.exit(1)

    has_pw = False
    try:
        import app as _a
        has_pw = bool(_a.get_password())
    except Exception:
        pass

    page = write_link_page(url, has_pw)
    print("\n" + "=" * 56)
    print("  ลิงก์สาธารณะ (เปิดบน iPhone ได้เลย):")
    print(f"  {url}/dashboard")
    print("=" * 56)
    if not has_pw:
        print("  ⚠️  ยังไม่ได้ตั้งรหัสผ่าน — ใครมีลิงก์ก็เข้าได้")
    print("  ปิดการแชร์: กด Ctrl+C หรือปิดหน้าต่างนี้\n")
    webbrowser.open("file:///" + page.replace("\\", "/"))

    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        print("\nปิดการแชร์แล้ว")


if __name__ == "__main__":
    main()
