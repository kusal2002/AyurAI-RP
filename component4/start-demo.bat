@echo off
REM ============================================================
REM  AyurAI Component 4 - start everything for the demo
REM  Double-click this file (Docker Desktop must be open first).
REM  Opens: PostgreSQL (Docker), the API window, the dashboard
REM  window, and the browser at http://localhost:5173
REM ============================================================

REM Print symbols like the Greek letter epsilon correctly in any Windows console
set "PYTHONUTF8=1"
chcp 65001 >nul

REM Repository root = the folder above this file
set "REPO=%~dp0.."
set "VENV=C:\venvs\component4\Scripts\activate.bat"

echo [1/4] Checking Docker Desktop...
docker info >nul 2>&1
if errorlevel 1 (
    echo.
    echo   Docker Desktop is not running.
    echo   Open Docker Desktop, wait until it says "Engine running", then run this again.
    pause
    exit /b 1
)

echo [2/4] Starting PostgreSQL...
docker compose -f "%REPO%\component4\docker-compose.yml" --profile db up -d postgres
if errorlevel 1 (
    echo   Could not start PostgreSQL. See the message above.
    pause
    exit /b 1
)

REM Wait (up to about 60 seconds) until the database accepts connections
set /a TRIES=0
:wait_for_database
docker exec ayurai-postgres pg_isready -U ayurai -d ayurai_audit >nul 2>&1
if not errorlevel 1 goto database_ready
set /a TRIES+=1
if %TRIES% GEQ 30 (
    echo   PostgreSQL did not become ready. Check Docker Desktop.
    pause
    exit /b 1
)
timeout /t 2 /nobreak >nul
goto wait_for_database
:database_ready
echo   PostgreSQL is ready.

echo [3/4] Starting the Component 4 API in a new window...
start "C4 API (keep open)" cmd /k "cd /d "%REPO%" && call "%VENV%" && python component4\api\main.py"

echo [4/4] Starting the dashboard in a new window...
if exist "%REPO%\ayurai-client\node_modules" (
    start "Dashboard (keep open)" cmd /k "cd /d "%REPO%\ayurai-client" && npm run dev"
) else (
    echo   First run: installing dashboard packages - this takes a few minutes.
    start "Dashboard (keep open)" cmd /k "cd /d "%REPO%\ayurai-client" && npm ci && npm run dev"
)

echo.
echo Waiting for the API and dashboard to start...
timeout /t 15 /nobreak >nul
start "" http://localhost:5173

echo.
echo ============================================================
echo  Done. The dashboard is opening at http://localhost:5173
echo  Keep the "C4 API" and "Dashboard" windows open.
echo  To stop: close those two windows (or press Ctrl+C in them).
echo ============================================================
pause
