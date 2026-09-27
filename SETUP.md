# RailDoc — Setup on a Fresh Laptop

From zero to running demo. Time: **~15 minutes** (no training required —
the trained model weights are included in `models/`).

---

## 0. One-command start (recommended)

Once steps 1–5 are done once, everything boots with a single command:

```bash
./start.sh                # Git Bash / macOS / Linux
```

Windows (double-click): `start.cmd`

The script checks prerequisites, installs missing dependencies, creates
`backend/.env` from the example if absent, seeds the database if empty,
starts both servers, health-checks them, and prints the app URL. Stop with
`Ctrl+C` (or close the windows). Flags: `--reseed` regenerates demo data,
`--no-install` skips dependency checks for faster restarts.

Without Git Bash, `start.cmd` falls back to a built-in boot sequence that
still runs `python -m app.db.seed` and starts both servers — it just skips
the dependency auto-installs and `.env` creation.

---

## 1. Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Python | 3.11+ | `python --version` |
| Node.js | 22 LTS | `node --version` |
| Git for Windows (Windows, optional) | any | `bash --version` |
| (optional) NVIDIA GPU + driver | any CUDA 12.x driver | `nvidia-smi` |

No GPU? Everything still works — CV inference just runs on CPU (~10× slower,
a few seconds per image instead of ~1 s).

## 2. Get the project

Either unzip the project archive **or** clone the repo:

```bash
git clone <repo-url> raildoc && cd raildoc
```

What must survive the transfer:

- `models/` — trained YOLO weights (`best.pt` files, ~9 MB total). **Do not
  delete this folder** — it removes the need for retraining.
- `RAILDOC_02.yolo26/` — the annotated training dataset, used by the
  sample-prediction screen and for retraining. Verify its integrity any
  time with `python backend/scripts/validate_dataset.py`.
- `backend/.env` — Supabase credentials. This file is git-ignored, so copy
  it separately (or re-create it from `backend/.env.example`, §4).

You do **not** need to transfer `frontend/node_modules/` — `npm install`
rebuilds it in a minute.

## 3. Backend install

```bash
cd backend
pip install -r requirements.txt
```

GPU acceleration (optional, recommended for the demo machine):

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
```

Verify the models are detected:

```bash
python -c "from app.cv.inference import registry; print(registry.status())"
# → {'raildoc_detector': {'available': True, 'kind': 'yolo26n-det', ...}}
```

## 4. Configure the environment

```bash
cp .env.example .env      # Windows: copy .env.example .env
```

Edit `backend/.env`:

```env
SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_KEY="your-anon-key"
SUPABASE_SERVICE_KEY="your-service-role-key"
```

Create the tables once: open the Supabase SQL editor and run
`backend/app/db/setup.sql`.

## 5. Seed demo data

```bash
cd backend
python -m app.db.seed
```

Loads 150 assets, 300 tasks, 75 trains, 21 block windows across corridors
C-07 / C-12 / C-19. (Windows PowerShell users: if you see a
`UnicodeEncodeError`, run `set PYTHONIOENCODING=utf-8` first.)

Then generate the initial plan — start the backend and call the optimizer,
or simply click **Run Optimizer** on the Dashboard after logging in.

## 6. Run

Either use the one-command start (§0) or manually:

```bash
# Terminal 1
cd backend
python -m uvicorn app.main:app --port 8000

# Terminal 2
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** → sign in `admin` / `admin123`.

30-second health check: Dashboard loads with KPIs, **Model Info** shows the
detector **Ready**, Defect Inspection accepts any railway image.

## 7. Docker alternative

```bash
docker compose up
```

Frontend on :5173, backend on :8000. Model weights are mounted read-only
from `./models` — retraining is never needed at deploy.

## 8. Retraining (only if you want a new model)

The script fine-tunes YOLO26 (`yolo26n.pt`), so the environment needs
`ultralytics>=8.4.0`.

```bash
cd backend
python -m app.cv.train_detector   # ~35 min on an RTX 3060 Ti
```

New weights land in `models/raildoc_detection/raildoc_det/weights/best.pt`;
the backend picks them up on restart.

## 9. Verification & stress testing

CI runs these checks on every push
(`.github/workflows/ci.yml`) — including a backend **load-smoke job** that
boots the API and runs `stress_load.py` against it —; run them locally
after any change:

```bash
# 1. Backend tests — DB-backed tests self-skip when SUPABASE_URL is unset
cd backend && python -m pytest tests/ -v

# 2. Dataset integrity — pairing, box geometry, class ranges, leakage scan
python backend/scripts/validate_dataset.py        # run from the repo root

# 3. Frontend typecheck + production build
cd frontend && npm run build
```

Optional load test against a running backend:

```bash
cd backend && python -m uvicorn app.main:app --port 8000 &
python scripts/stress_load.py --duration 60 --clients 20
```

The harness reports per-operation p50/p95 latency and fails when 5xx +
transport errors exceed 1% of non-429 traffic (429 rate-limit responses
are expected under load and are not counted as errors).

The CI backend job also collects a coverage report and uploads
`coverage.xml` as a run artifact. To reproduce locally:

```bash
pip install pytest-cov
python -m pytest tests/ -v --cov=app --cov-report=term-missing
```

## 10. Performance & tuning (optional)

The backend keeps its event loop responsive by running CPU-heavy and
blocking work on dedicated pools. Defaults are fine for the demo machine;
these env vars tune them:

| Variable | Default | Meaning |
|----------|---------|---------|
| `HEAVY_POOL_SIZE` | `2` | Concurrent CPU-bound jobs (YOLO inference, OR-Tools solves, agent orchestration). Extra jobs **queue** instead of stacking GIL-fighting threads — raise it only on a dedicated multi-core box, and expect diminishing returns: each heavy job already spawns solver threads internally. |
| `IO_POOL_SIZE` | `8` | Threads for blocking DB/HTTP calls issued from async endpoints (plan approve/revert, image decode/upload). |
| `HEALTH_CACHE_TTL` | `15` | Seconds `/api/health` caches its Supabase verdict. Set `0` to disable (each probe then costs a full DB round trip). The load harness and uptime checks probe health continuously — keep some caching in front of a remote database. |
| `AUDIT_LOG_DIR` | `logs/audit` | Where the audit API reads `audit_*.log`. Set this when running the backend from a different working directory (e.g. Docker), otherwise the audit screen silently shows no entries. |

Behavior notes:

- Concurrency is **bounded, not unlimited**: more simultaneous optimizer/
  replan requests simply wait their turn. This is deliberate — the previous
  unbounded behavior stacked 10+ CP-SAT runs (each spawning 4 solver
  threads) into ~40 competing threads and pushed p95 latency to ~16 s.
- The audit API parses each log file once and re-parses only when the file
  changes (mtime/size check), so the Audit screen stays fast as logs grow.
- Remaining latency spikes while heavy jobs run are the single-process/GIL
  limitation documented in the PRD (§49.4, multi-worker deployment).

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `registry.status()` shows unavailable | `models/` folder missing or renamed — restore it, or set `RAILDOC_MODEL_DIR` to the folder containing `raildoc_detection/…`. |
| `UnicodeEncodeError` while seeding | `set PYTHONIOENCODING=utf-8` (PowerShell: `$env:PYTHONIOENCODING="utf-8"`) and rerun. |
| `/api/inspection/analyze` returns 422 on upload | `python-multipart` missing — `pip install -r requirements.txt` again. |
| Torch install fails | CPU-only is fine: `pip install torch torchvision` (plain PyPI). |
| 401 on every API call | `backend/.env` missing/mismatched with the seeded database. |
| Map tiles blank | Internet needed for OpenStreetMap tiles; markers still render. |
