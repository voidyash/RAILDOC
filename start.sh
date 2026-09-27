#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# RailDoc one-command startup (bash / Git Bash)
#
#   ./start.sh              — normal start (installs what's missing)
#   ./start.sh --reseed     — wipe + reseed demo data before starting
#   ./start.sh --no-install — skip dependency checks (faster restarts)
#
# Stops both servers with Ctrl+C.
# ─────────────────────────────────────────────────────────────────────
set -u

cd "$(dirname "$0")"
ROOT="$(pwd)"

RESEED=0
NO_INSTALL=0
for arg in "$@"; do
  case "$arg" in
    --reseed)    RESEED=1 ;;
    --no-install) NO_INSTALL=1 ;;
    *) echo "unknown flag: $arg"; exit 1 ;;
  esac
done

BLUE='\033[1;34m'; GREEN='\033[1;32m'; YELLOW='\033[1;33m'; RED='\033[1;31m'; NC='\033[0m'
step()  { echo -e "${BLUE}▶${NC} $1"; }
ok()    { echo -e "${GREEN}✓${NC} $1"; }
warn()  { echo -e "${YELLOW}!${NC} $1"; }
fail()  { echo -e "${RED}✗ $1${NC}"; exit 1; }

PIDS=()
cleanup() {
  echo ""
  step "Shutting down..."
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null
  done
  # kill anything still listening on the demo ports (Windows/Git Bash safe)
  for port in 8000 5173; do
    if command -v netstat >/dev/null 2>&1; then
      for pid in $(netstat -ano 2>/dev/null | grep ":$port " | grep LISTENING | awk '{print $5}' | sort -u); do
        taskkill //F //PID "$pid" >/dev/null 2>&1
      done
    fi
  done
  ok "Stopped."
}
trap cleanup EXIT INT TERM

# ── 1. Prerequisites ────────────────────────────────────────────────
step "Checking prerequisites"
command -v python >/dev/null 2>&1 || fail "Python not found. Install Python 3.11+ and retry."
command -v node   >/dev/null 2>&1 || fail "Node.js not found. Install Node 18+ and retry."
ok "python $(python --version 2>&1 | awk '{print $2}') / node $(node --version)"

# ── 2. Python deps ──────────────────────────────────────────────────
if [ "$NO_INSTALL" -eq 0 ]; then
  step "Checking Python dependencies"
  MISSING=$(python - <<'EOF'
need = ["fastapi", "uvicorn", "httpx", "ortools", "jose", "passlib",
        "multipart", "dotenv", "ultralytics", "cv2", "PIL", "yaml"]
missing = []
for m in need:
    try:
        __import__(m)
    except ImportError:
        missing.append(m)
print(" ".join(missing))
EOF
)
  if [ -n "$MISSING" ]; then
    warn "missing: $MISSING — installing from requirements.txt (this can take a while the first time)"
    pip install -r backend/requirements.txt >/dev/null 2>&1 \
      || fail "pip install failed — run 'pip install -r backend/requirements.txt' manually."
    # torch CUDA build is optional; plain PyPI torch is enough to import
    python -c "import torch" 2>/dev/null || pip install torch torchvision >/dev/null 2>&1
  fi
  ok "Python dependencies ready"
else
  echo " skipped dependency checks (--no-install)"
fi

# ── 3. Frontend deps ────────────────────────────────────────────────
if [ "$NO_INSTALL" -eq 0 ]; then
  step "Checking frontend dependencies"
  if [ ! -d frontend/node_modules ]; then
    warn "node_modules missing — running npm install (one-time)"
    (cd frontend && npm install --no-fund --no-audit >/dev/null 2>&1) \
      || fail "npm install failed — run it manually in frontend/."
  fi
  ok "Frontend dependencies ready"
fi

# ── 4. Environment file ─────────────────────────────────────────────
step "Checking backend/.env"
if [ ! -f backend/.env ]; then
  if [ -f backend/.env.example ]; then
    cp backend/.env.example backend/.env
    warn "created backend/.env from example — add your Supabase keys!"
    echo "        edit backend/.env, then re-run this script."
  fi
  fail "backend/.env missing"
fi
grep -q "SUPABASE_URL=" backend/.env || fail "backend/.env has no SUPABASE_URL"

# Sanity-check JSON-valued .env entries (e.g. connection specs): an invalid
# JSON line crashes the backend at startup with a raw parse error — report
# the offending line here instead.
if grep -Eq '^[A-Z0-9_]+="[\[{]' backend/.env; then
  python - <<'EOF' || fail "backend/.env has an invalid JSON value (see line reported above)"
import json, sys

with open("backend/.env", encoding="utf-8") as f:
    for lineno, raw in enumerate(f, 1):
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip("'\"")
        if value:
            # .env convention: inner quotes are backslash-escaped inside the
            # double-quoted value — unescape them before parsing.
            # (An empty value must be skipped: value[:1] in "[{" is True for "".)
            if value.startswith(("[", "{")):
                normalized = value.replace('\\"', '"')
                try:
                    json.loads(normalized)
                except json.JSONDecodeError as e:
                    print(f"  line {lineno}: {key} = {value[:60]}... -> {e.msg}")
                    sys.exit(1)
print("ok")
EOF
fi
ok "Environment configured"

# ── 5. Model weights ────────────────────────────────────────────────
step "Checking trained model weights"
if [ -f models/raildoc_detection/raildoc_det/weights/best.pt ]; then
  ok "weights present (no training needed)"
else
  warn "weights missing — detection endpoints will return 503 until trained:"
  echo "        cd backend && python -m app.cv.train_detector"
fi

# ── 6. Seed data ────────────────────────────────────────────────────
step "Checking database seed"
# Probe from backend/ so `app` is importable and load_dotenv() finds
# backend/.env — run from the repo root BOTH failed (import error → "error"),
# so every run wrongly re-seeded even with data already present.
SEED_OK=$(cd backend && PYTHONIOENCODING=utf-8 python - <<'EOF'
try:
    from app.db import queries as db
    corridors = db.get_corridors()
    print("ok" if corridors else "empty")
except Exception:
    print("error")
EOF
)
if [ "$RESEED" -eq 1 ] || [ "$SEED_OK" != "ok" ]; then
  [ "$SEED_OK" != "ok" ] && warn "database empty or unreachable — seeding..." 
  [ "$RESEED" -eq 1 ] && warn "--reseed: regenerating demo data..."
  (cd backend && PYTHONIOENCODING=utf-8 python -m app.db.seed >/dev/null 2>&1) \
    || fail "seeding failed — check Supabase credentials in backend/.env"
  ok "demo data seeded"
else
  ok "demo data present"
fi

# ── 7. Boot servers ─────────────────────────────────────────────────
mkdir -p backend/logs frontend/logs

step "Starting backend (port 8000)"
(cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > logs/start_backend.log 2>&1) &
PIDS+=($!)

step "Waiting for backend health..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
    ok "backend is up"
    break
  fi
  [ "$i" -eq 30 ] && fail "backend did not become healthy — see backend/logs/start_backend.log"
  sleep 1
done

step "Starting frontend (port 5173)"
# Clear Vite's dependency-optimizer cache: a stale cache from an interrupted
# run can make the first browser page load hang on the optimizer.
rm -rf frontend/node_modules/.vite
(cd frontend && npm run dev > logs/start_frontend.log 2>&1) &
PIDS+=($!)

step "Waiting for frontend..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:5173/ >/dev/null 2>&1; then
    ok "frontend is up"
    break
  fi
  [ "$i" -eq 30 ] && fail "frontend did not start — see frontend/logs/start_frontend.log"
  sleep 1
done

echo ""
echo -e "${GREEN}════════════════════════════════════════════${NC}"
echo -e "${GREEN}  RailDoc is running${NC}"
echo -e "${GREEN}════════════════════════════════════════════${NC}"
echo -e "  App:      ${BLUE}http://localhost:5173${NC}"
echo -e "  API:      ${BLUE}http://localhost:8000/api/health${NC}"
echo -e "  Login:    admin / admin123"
echo -e "  Logs:     backend/logs/start_backend.log · frontend/logs/start_frontend.log"
echo -e ""
echo -e "  Press ${YELLOW}Ctrl+C${NC} to stop both servers."
echo ""
wait
