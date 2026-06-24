@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   อัปเดตโค้ดขึ้น GitHub (push)
echo ============================================
echo.
git add -A
git commit -m "Update from desktop %date% %time%"
git push
echo.
echo เสร็จแล้ว! Render จะ redeploy ให้อัตโนมัติใน 2-5 นาที
echo (ถ้าขึ้น error ให้แคปหน้าจอส่งให้ผมดู)
pause
