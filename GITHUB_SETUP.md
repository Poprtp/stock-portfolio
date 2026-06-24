# เชื่อมโฟลเดอร์นี้กับ GitHub (ตั้งครั้งเดียว) → จากนั้นอัปเดตได้ด้วยคลิกเดียว

หลังตั้งเสร็จ ทุกครั้งที่แก้โค้ด แค่ดับเบิลคลิก **update_github.bat** มันจะ push ขึ้น GitHub
แล้ว Render จะ redeploy ให้เองอัตโนมัติ

---

## ขั้นที่ 1 — ติดตั้ง Git (ครั้งเดียว)
1. ดาวน์โหลด Git จาก https://git-scm.com/download/win (เลือก 64-bit Setup)
2. ติดตั้งโดยกด Next ไปเรื่อยๆ ได้เลย (ค่าเริ่มต้นโอเคหมด)
3. ติดตั้งเสร็จ รีสตาร์ทเครื่องหนึ่งครั้ง (หรืออย่างน้อยปิด-เปิด Command Prompt ใหม่)

## ขั้นที่ 2 — เชื่อมโฟลเดอร์กับ repo (ครั้งเดียว)
1. เปิด File Explorer ไปที่ `D:\Claude Agent\rollercoaster`
2. คลิกช่อง address bar ด้านบน พิมพ์ `cmd` กด Enter (เปิด Command Prompt ที่โฟลเดอร์นี้)
3. พิมพ์ทีละบรรทัด (กด Enter หลังแต่ละบรรทัด) — แทนที่ `<USERNAME>` และ `<REPO>` ด้วยของคุณ:

```
git init
git branch -M main
git remote add origin https://github.com/<USERNAME>/<REPO>.git
git add -A
git commit -m "first commit from desktop"
git push -u origin main
```

   - หา URL ของ repo ได้จากหน้า repo บน GitHub กดปุ่มเขียว **Code** → คัดลอกลิงก์ HTTPS (ลงท้าย .git)
   - ตอน push ครั้งแรก จะมีหน้าต่างเด้งให้ **ล็อกอิน GitHub** (กดเข้าเบราว์เซอร์ตามขั้นตอน) — ทำครั้งเดียว เครื่องจะจำไว้

   ⚠️ ถ้าขึ้นว่า push ไม่ได้เพราะ repo มีไฟล์อยู่แล้ว (ที่อัปไว้ก่อนหน้า) ให้ใช้แทน:
   ```
   git pull origin main --allow-unrelated-histories
   git push -u origin main
   ```

## ขั้นที่ 3 — ใช้งานต่อจากนี้
เวลาแก้โค้ดเสร็จ แค่ **ดับเบิลคลิก `update_github.bat`** → จบ
(มันจะ add + commit + push ให้อัตโนมัติ และ Render จะ redeploy เอง)

---

### หมายเหตุความปลอดภัย
การล็อกอินครั้งแรกใช้บัญชี GitHub ของคุณเองบนเครื่องคุณเอง — ผมไม่ได้เข้าถึงรหัสหรือ token ใดๆ
ทุกอย่างเกิดบนเครื่องคุณ ปลอดภัยและคุณควบคุมเองทั้งหมด
