@echo off
echo Starting Point App BIID Servers...
echo.

echo [1/2] Starting Django Backend Server...
cd /d "C:\Users\rockr\OneDrive\claude code\melty-pointapp\pointapp-biid\backend"
start "Django Backend" cmd /k "python manage.py runserver 8001"

echo [2/2] Starting Next.js Frontend Server...  
cd /d "C:\Users\rockr\OneDrive\claude code\melty-pointapp\pointapp-biid"
start "Next.js Frontend" cmd /k "npm run dev"

echo.
echo Servers are starting...
echo - Django Backend: http://localhost:8001
echo - Next.js Frontend: http://localhost:3000
echo.
echo Press any key to exit this window...
pause >nul