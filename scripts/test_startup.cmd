@echo off
REM ----------------------------------------------------------------
REM RailDoc startup smoke test (Windows)
REM
REM Drives start.cmd end-to-end without human interaction:
REM   Scenario 1: a corrupt backend/.env must abort with exit 1 and the
REM               abort must come from the env JSON checker.
REM   Scenario 2: a healthy fallback-path boot must reach /api/health
REM               and the Vite dev server; the runner tears the servers
REM               down again (start.cmd itself would leave them running).
REM
REM Usage:      cmd /c scripts\test_startup.cmd
REM Exit code:  0 = all scenarios passed, 1 = failure (message printed)
REM ----------------------------------------------------------------
setlocal EnableExtensions
cd /d "%~dp0.."

set "PASS=0"
set "FAIL=0"

REM --- sanity: our test hooks exist in start.cmd --------------------
findstr /c:"RAILDOC_FORCE_FALLBACK" start.cmd >nul || (echo [smoke] FAIL: RAILDOC_FORCE_FALLBACK hook missing in start.cmd & exit /b 1)
findstr /c:"RAILDOC_STARTUP_SMOKE" start.cmd >nul || (echo [smoke] FAIL: RAILDOC_STARTUP_SMOKE hook missing in start.cmd & exit /b 1)
findstr /c:"RAILDOC_ENV_PATH" start.cmd >nul || (echo [smoke] FAIL: RAILDOC_ENV_PATH hook missing in start.cmd & exit /b 1)

set "SCRATCH=%TEMP%\raildoc_smoke_%RANDOM%"
mkdir "%SCRATCH%" 2>nul
set "RAILDOC_STARTUP_SMOKE=1"
set "RAILDOC_FORCE_FALLBACK=1"

REM --- scenario 1: corrupt .env must abort --------------------------
echo [smoke] Scenario 1: corrupt .env abort
set "FAKE_ENV=%SCRATCH%\.env"
>"%FAKE_ENV%" echo SUPABASE_URL="https://example.supabase.co"
>>"%FAKE_ENV%" echo BAD_JSON="{not valid"

set "RAILDOC_ENV_PATH=%FAKE_ENV%"
call start.cmd > "%SCRATCH%\abort.log" 2>&1
set "ABORT_RC=%errorlevel%"
set "RAILDOC_ENV_PATH="

if "%ABORT_RC%"=="1" (
  findstr /c:"INVALID JSON" "%SCRATCH%\abort.log" >nul
  if not errorlevel 1 (
    echo [smoke] PASS: corrupt .env aborted with exit 1 and checker report.
    set /a PASS+=1
  ) else (
    echo [smoke] FAIL: exit 1 but no checker report in log:
    type "%SCRATCH%\abort.log"
    set /a FAIL+=1
  )
) else (
  echo [smoke] FAIL: corrupt .env did not abort ^(exit %ABORT_RC%, expected 1^). Log:
  type "%SCRATCH%\abort.log"
  set /a FAIL+=1
)

REM --- scenario 2: healthy fallback boot -----------------------------
echo [smoke] Scenario 2: fallback boot + health checks
if exist "backend\.env" (
  set "RAILDOC_ENV_PATH=backend\.env"
) else (
  echo [smoke] SKIP: no backend\.env - cannot run a real boot.
  goto :summary
)

call start.cmd > "%SCRATCH%\boot.log" 2>&1
set "BOOT_RC=%errorlevel%"
if not "%BOOT_RC%"=="0" (
  echo [smoke] FAIL: start.cmd exited %BOOT_RC%. Log:
  type "%SCRATCH%\boot.log"
  set /a FAIL+=1
  goto :teardown
)

node -e "let n=0;(async()=>{while(n<30){try{const r=await fetch('http://localhost:8000/api/health');if(r.ok)process.exit(0)}catch{}n++;await new Promise(r=>setTimeout(r,1000))}process.exit(1)})()" && (
  echo [smoke] PASS: backend /api/health reachable.
  set /a PASS+=1
) || (
  echo [smoke] FAIL: backend not healthy. boot log:
  type "%SCRATCH%\boot.log"
  set /a FAIL+=1
)

node -e "let n=0;(async()=>{while(n<45){try{const r=await fetch('http://localhost:5173/');if(r.ok)process.exit(0)}catch{}n++;await new Promise(r=>setTimeout(r,1000))}process.exit(1)})()" && (
  echo [smoke] PASS: frontend dev server reachable.
  set /a PASS+=1
) || (
  echo [smoke] FAIL: frontend not ready. boot log:
  type "%SCRATCH%\boot.log"
  set /a FAIL+=1
)

:teardown
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":8000 " ^| findstr "LISTENING"') do taskkill /F /T /PID %%P >nul 2>&1
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":5173 " ^| findstr "LISTENING"') do taskkill /F /T /PID %%P >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'uvicorn app.main:app' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

:summary
echo.
echo [smoke] Results: %PASS% passed, %FAIL% failed.
if "%FAIL%"=="0" (
  echo [smoke] ALL PASSED
  exit /b 0
)
exit /b 1
