@echo off
REM ----------------------------------------------------------------
REM RailDoc one-command startup (Windows double-click / cmd)
REM Prefers Git Bash + start.sh; falls back to a minimal Python + Node
REM boot sequence when bash.exe is not reachable.
REM ----------------------------------------------------------------
setlocal EnableExtensions
cd /d "%~dp0"

REM --- locate a usable bash ---------------------------------------
REM Git for Windows adds only Git\cmd to PATH; the real bash.exe lives
REM in Git\bin, so "where bash" fails on a default double-click. Also
REM ignore C:\Windows\System32\bash.exe (WSL) - start.sh needs Windows
REM Python/Node, which WSL does not have.
set "FOUND_BASH="
for /f "delims=" %%B in ('where bash 2^>nul') do if not defined FOUND_BASH set "FOUND_BASH=%%B"
if not defined FOUND_BASH goto :probe_git_bash
echo %FOUND_BASH% | "%SystemRoot%\System32\findstr.exe" /i "System32" >nul
if not errorlevel 1 set "FOUND_BASH="
:probe_git_bash
if not defined FOUND_BASH if exist "%ProgramFiles%\Git\bin\bash.exe" set "FOUND_BASH=%ProgramFiles%\Git\bin\bash.exe"
if not defined FOUND_BASH if exist "%ProgramFiles(x86)%\Git\bin\bash.exe" set "FOUND_BASH=%ProgramFiles(x86)%\Git\bin\bash.exe"
if not defined FOUND_BASH if exist "%LocalAppData%\Programs\Git\bin\bash.exe" set "FOUND_BASH=%LocalAppData%\Programs\Git\bin\bash.exe"

if not defined FOUND_BASH goto :fallback
REM Test hook: RAILDOC_FORCE_FALLBACK=1 exercises the fallback path even
REM when Git Bash is present (used by scripts/test_startup.cmd / CI).
if defined RAILDOC_FORCE_FALLBACK (
  echo [start] RAILDOC_FORCE_FALLBACK set - skipping Git Bash path.
  goto :fallback
)

echo [start] Launching start.sh via Git Bash ...
"%FOUND_BASH%" start.sh %*
goto :eof

:fallback
echo [start] Git Bash not found - using fallback startup (no auto-install checks).

REM --- prerequisites -----------------------------------------------
python --version >nul 2>nul
if errorlevel 1 (
  echo [start] ERROR: Python not found ^(or it is the Microsoft Store stub^). Install Python 3.11+ and retry.
  call :maybe_pause
  exit /b 1
)
where node >nul 2>nul
if errorlevel 1 (
  echo [start] ERROR: Node.js not found. Install Node 18+ and retry.
  call :maybe_pause
  exit /b 1
)

REM --- environment file --------------------------------------------
REM RAILDOC_ENV_PATH lets automation point the checker at a scratch copy
REM (scripts/test_startup.cmd corrupts one and asserts the abort).
set "ENV_PATH=backend\.env"
if defined RAILDOC_ENV_PATH set "ENV_PATH=%RAILDOC_ENV_PATH%"
if not exist "%ENV_PATH%" (
  echo [start] ERROR: backend\.env missing. Copy backend\.env.example and add Supabase keys.
  call :maybe_pause
  exit /b 1
)

REM Sanity-check JSON-valued .env entries: an invalid JSON line crashes the
REM backend at boot with a raw parse error. Report the offending line here.
set "PYTHONIOENCODING=utf-8"
python backend\scripts\check_env.py "%ENV_PATH%"
if errorlevel 1 (
  echo [start] ERROR: backend\.env has an invalid JSON value - fix the entry reported above.
  call :maybe_pause
  exit /b 1
)

REM --- free the demo ports from a previous run ---------------------
REM /T kills the process tree (uvicorn spawns a worker child that can
REM outlive its parent and keep the port bound). The second sweep reaps
REM orphaned uvicorn workers whose dead parent still owns the netstat
REM entry, which a plain PID kill cannot reach.
REM entry, which a plain PID kill cannot reach. Matched narrowly to this
REM app's own uvicorn command line so other projects' servers are untouched.
REM Also clear Vite's dependency-optimizer cache: a stale cache from a
REM previous/interrupted run makes the first browser page load hang on
REM "[optimizer] bundling dependencies...".
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":8000 " ^| findstr "LISTENING"') do taskkill /F /T /PID %%P >nul 2>&1
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":5173 " ^| findstr "LISTENING"') do taskkill /F /T /PID %%P >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'uvicorn app.main:app' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

if not exist "backend\logs" mkdir "backend\logs"
if not exist "frontend\logs" mkdir "frontend\logs"

if not exist "frontend\node_modules" (
  echo [start] Installing frontend dependencies...
  pushd frontend
  call npm install --no-fund --no-audit
  popd
)

REM Seed demo data before boot (mirrors start.sh step 6). A failed seed
REM (missing Supabase keys) only warns - the backend can still boot for
REM UI demos without a database.
echo [start] Seeding demo data: python -m app.db.seed
pushd backend
python -m app.db.seed
if errorlevel 1 (
  echo [start] WARNING: seeding failed - check SUPABASE_URL and SUPABASE_SERVICE_KEY in backend\.env
)
popd

echo [start] Starting backend on :8000 ...
start "RailDoc backend" cmd /c "cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > logs\start_backend.log 2>&1"

echo [start] Waiting for backend health...
node -e "let n=0;(async()=>{while(n<30){try{const r=await fetch('http://localhost:8000/api/health');if(r.ok)process.exit(0)}catch{}n++;await new Promise(r=>setTimeout(r,1000))}process.exit(1)})()"
if errorlevel 1 (
  echo [start] WARNING: backend not healthy yet - check backend\logs\start_backend.log
) else (
  echo [start] backend OK
)

echo [start] Clearing Vite optimizer cache ...
if exist "frontend\node_modules\.vite" rmdir /s /q "frontend\node_modules\.vite"

echo [start] Starting frontend on :5173 ...
start "RailDoc frontend" cmd /c "cd frontend && npm run dev > logs\start_frontend.log 2>&1"

echo [start] Waiting for frontend...
node -e "let n=0;(async()=>{while(n<45){try{const r=await fetch('http://localhost:5173/');if(r.ok)process.exit(0)}catch{}n++;await new Promise(r=>setTimeout(r,1000))}process.exit(1)})()"
if errorlevel 1 (
  echo [start] WARNING: frontend not ready yet - check frontend\logs\start_frontend.log
) else (
  echo [start] frontend OK
)

REM Test hook: automation sets RAILDOC_STARTUP_SMOKE=1 so the smoke run
REM neither pops a browser nor blocks on the final pause.
if defined RAILDOC_STARTUP_SMOKE (
  echo [start] RAILDOC_STARTUP_SMOKE set - skipping browser launch.
  goto :eof
)

start "" http://localhost:5173

echo.
echo   RailDoc starting:
echo     App:   http://localhost:5173
echo   Two console windows were opened - close them to stop the servers.
echo.
call :maybe_pause

goto :eof

REM Pauses only for interactive humans; automation (RAILDOC_STARTUP_SMOKE=1)
REM returns immediately so CI never blocks.
:maybe_pause
if defined RAILDOC_STARTUP_SMOKE goto :eof
pause
goto :eof
