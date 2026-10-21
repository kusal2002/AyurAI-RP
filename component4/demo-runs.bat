@echo off
REM ============================================================
REM  AyurAI Component 4 - live demo runs (no servers needed)
REM  1) Federated training: 3 clinics, FedProx, privacy budget 2.0
REM  2) FAKL prototype: federated knowledge-graph update (synthetic data)
REM ============================================================

REM Print symbols like the Greek letter epsilon correctly in any Windows console
set "PYTHONUTF8=1"
chcp 65001 >nul

set "REPO=%~dp0.."
cd /d "%REPO%"
call "C:\venvs\component4\Scripts\activate.bat"

echo ===== 1) Federated training (about 15 seconds) =====
python component4\federated\run.py 2.0 --strategy fedprox

echo.
echo ===== 2) FAKL prototype (about 2 seconds) =====
python component4\fakl\run_fakl.py

echo.
pause
