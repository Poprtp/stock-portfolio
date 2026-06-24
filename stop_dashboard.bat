@echo off
REM หยุดเซิร์ฟเวอร์ที่รันอยู่บนพอร์ต 5000
set found=0
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
    set found=1
)
if "%found%"=="1" (echo หยุดเซิร์ฟเวอร์เรียบร้อยแล้ว) else (echo ไม่พบเซิร์ฟเวอร์ที่กำลังรัน)
timeout /t 2 >nul
