# คู่มือ deploy ขึ้น cloud ให้ทำงาน 24 ชม. (ฟรี)

เป้าหมาย: ให้เว็บแอปออนไลน์ตลอด เข้าได้จาก iPhone/เครื่องอื่นทุกที่ และอัพเดตราคาเองทุก 1 ชม. แม้ปิดคอม — โดยไม่เสียเงิน ด้วย **Render (ฟรี)** + **UptimeRobot (ฟรี)**

---

## ภาพรวมสถาปัตยกรรม

```
  หน้าบ้าน (Frontend)              หลังบ้าน (Backend = Flask บน Render)
  templates/*.html  ───fetch──►   /api/*  ──►  อ่าน cache.json (เร็ว)
  static/*.js,*.css                  ▲
                                     │ ทุก 1 ชม.
                              ตัวอัพเดตอัตโนมัติ (background thread)
                                     │ ดึงราคาใหม่ด้วย yfinance
                                     ▼
                                 cache.json
```

หน้าบ้านไม่ต้องรอ yfinance ทุกครั้ง — อ่านจาก cache ที่หลังบ้านเตรียมไว้ จึงโหลดเร็วและรีเฟรชเองได้

---

## ขั้นตอน deploy (ครั้งเดียว ~10 นาที)

### 1) เอาโค้ดขึ้น GitHub
1. สมัคร GitHub ฟรีที่ https://github.com
2. สร้าง repository ใหม่ (เช่นชื่อ `stock-portfolio`)
3. อัปโหลดไฟล์ทั้งหมดในโฟลเดอร์นี้เข้า repo
   - ถ้าใช้ git: `git init` → `git add .` → `git commit -m "init"` → `git push`
   - ถ้าไม่ถนัด git: กดปุ่ม **Add file → Upload files** บนหน้าเว็บ GitHub ลากไฟล์ทั้งหมดเข้าไปได้เลย

### 2) สร้างบริการบน Render
1. สมัคร Render ฟรีที่ https://render.com (ล็อกอินด้วย GitHub ได้)
2. กด **New → Web Service** แล้วเลือก repo ที่เพิ่งสร้าง
3. Render จะอ่านไฟล์ `render.yaml` ให้อัตโนมัติ (หรือกรอกเองตามนี้):
   - **Runtime:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --workers 1 --timeout 120`
   - **Plan:** Free
4. ที่หัวข้อ **Environment** เพิ่มตัวแปร:
   - `DASH_PASSWORD` = รหัสผ่านที่อยากตั้ง (กันคนอื่นเข้า) — **แนะนำให้ตั้ง**
   - `UPDATE_INTERVAL_SEC` = `3600` (อัพเดตทุก 1 ชม.)
5. กด **Create Web Service** รอ build เสร็จ จะได้ลิงก์แบบ
   `https://stock-portfolio-xxxx.onrender.com` — เปิดบน iPhone ได้เลย

### 3) ทำให้ออนไลน์ตลอด 24 ชม. (สำคัญ)
แผนฟรีของ Render จะ "หลับ" เมื่อไม่มีคนเข้านาน ~15 นาที ทำให้ตัวอัพเดตหยุด
แก้ด้วยการให้มีคน "ปลุก" เป็นระยะ — ใช้ **UptimeRobot** ฟรี:
1. สมัคร https://uptimerobot.com (ฟรี)
2. **Add New Monitor** → ประเภท **HTTP(s)**
3. URL ใส่: `https://ลิงก์ของคุณ.onrender.com/api/status`
4. ตั้ง interval = ทุก 5 นาที → Save

เท่านี้แอปจะตื่นตลอด ตัวอัพเดตราคาจะทำงานทุก 1 ชม. แม้คอมคุณปิดอยู่

---

## หมายเหตุข้อจำกัดแผนฟรี

- **ข้อมูลพอร์ตบน cloud จะรีเซ็ตเมื่อมีการ deploy ใหม่** (ดิสก์ของ Render free เป็นแบบชั่วคราว)
  ถ้าอยากให้พอร์ตอยู่ถาวร ให้แก้ไฟล์ `portfolio.csv` ในเครื่องแล้ว push ขึ้น GitHub ใหม่
  หรือเก็บไฟล์พอร์ตหลัก ๆ ไว้ใน repo
- รหัสผ่านตั้งผ่าน env `DASH_PASSWORD` (เว็บจะถาม username/password — ใส่ username อะไรก็ได้ ใส่ password ให้ตรง)
- ถ้าไม่อยากขึ้น cloud ใช้แบบในเครื่อง (`python app.py`) หรือแชร์ชั่วคราวด้วย `share.py` ก็ได้เหมือนเดิม

---

## สรุปค่าใช้จ่าย: ฟรีทั้งหมด

| ส่วน | บริการ | ค่าใช้จ่าย |
|------|--------|-----------|
| ข้อมูลราคาหุ้น | yfinance (Yahoo) | ฟรี |
| โฮสต์เว็บ | Render Free | ฟรี |
| ปลุกให้ออนไลน์ 24 ชม. | UptimeRobot Free | ฟรี |
