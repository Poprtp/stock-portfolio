@echo off
cd /d "%~dp0"
echo ============================================
echo   Pushing your code to GitHub...
echo ============================================
echo.
git add -A
git commit -m "Update from desktop"
git push
echo.
echo ============================================
echo   Done. Render will redeploy in a few minutes.
echo   If you see a red error above, screenshot it.
echo ============================================
pause
