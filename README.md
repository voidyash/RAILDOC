# 🚆 RailDoc

> AI-assisted railway maintenance coordination tool that consolidates Engineering, S&T, and Traction work into fewer, better-used maintenance blocks while keeping train movements protected.
>
> Built for the **Smart India Hackathon**.

This is a full-stack web app with:
- a **React + TypeScript + Vite** frontend, and
- a **Python + FastAPI** backend that handles authentication, data access, priority scoring, and block optimization.

The backend can run against **Supabase** as its data store, but it is also built to work with mock users and synthetic data for demo and development use.

---

## Who this is for

**If you are just using the app:**
- it helps plan railway maintenance work across departments
- it turns many small separate tasks into shared maintenance blocks
- it shows explanations for why tasks were scheduled the way they were
- it includes a live clock and date in the header for the current session

**If you are a developer:**
- this is a React + TypeScript + Vite frontend talking to a FastAPI backend
- the backend uses JWT authentication with role-based access
- data can be stored in Supabase via PostgREST, or the app can run from generated synthetic datasets
- the optimizer is built with **Google OR-Tools CP-SAT**

---

## What It Does

Railway maintenance across departments is often planned separately, which leads to fragmented blocks, wasted capacity, and unnecessary disruption to train operations. This system:

1. **Ingests** maintenance data from TMS, SMMS, TDMS, and COA sources, using simulated/synthetic data in the demo
2. **Scores** maintenance tasks with a configurable priority engine
3. **Optimizes** block assignments using constraint-aware scheduling
4. **Coordinates** cross-department work into shared maintenance blocks
5. **Explains** scheduling decisions in plain language
6. **Simulates** what-if scenarios before committing to a plan

### Before vs After

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Total Blocks | 300 | 20 | **-93%** |
| Downtime | 18,000 min | 2,100 min | **-88%** |
| Train Conflicts | 150 | 36 | **-76%** |
| Block Utilization | 35% | 85% | **+143%** |
| Multi-Dept Blocks | 0 | 6 | **+∞** |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React, TypeScript, Tailwind CSS, Recharts, Leaflet (react-leaflet), Vite |
| Backend | Python, FastAPI |
| Optimization | Google OR-Tools (CP-SAT solver) |
| Database | Supabase (PostgreSQL + PostgREST REST API) |
| Auth | JWT, role-based access control, mock users for demo |
| Deployment | Docker, Docker Compose, nginx |

---

## Project Structure

```
raildoc/
├── frontend/                  # React + TypeScript UI
│   ├── src/
│   │   ├── components/        # Dashboard, Inspection, RailMap, ModelInfo,
│   │   │                     # Queue, Timeline, Blocks, Explain, Simulate,
│   │   │                     # Comparison, Users, Audit, Login
│   │   ├── api/               # REST client, Auth context, Data context
│   │   ├── data/              # Maintenance recommendation mapping (defect → tools + repair time)
│   │   ├── types/             # TypeScript types
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   └── index.css
│   ├── public/
│   ├── index.html
│   ├── vite.config.ts
│   ├── package.json
│   └── nginx.conf
│
├── backend/                   # FastAPI backend
│   ├── app/
│   │   ├── main.py           # FastAPI app and API routes
│   │   ├── api/              # Auth, audit, and inspection routes
│   │   ├── core/             # Security, middleware, audit, validation,
│   │   │                     # exception handling, datastore
│   │   ├── models/           # Pydantic domain models
│   │   ├── agents/           # Admin orchestrator + Engineer/Planner/
│   │   │                     # Operations agents + structured protocol
│   │   ├── cv/               # YOLO training scripts + inference layer
│   │   ├── ai/               # Priority scoring engine
│   │   ├── optimizer/        # OR-Tools block optimizer
│   │   ├── db/               # Supabase queries, schema, seed,
│   │   │                     # setup SQL
│   │   ├── services/         # Synthetic data generator
│   │   └── integrations/     # TMS / SMMS / TDMS / COA adapter slots
│   ├── requirements.txt
│   └── .env / .env.example
│
├── docs/demo/                 # Hackathon demo script
│
├── data/synthetic/           # Generated JSON datasets
└── README.md
```

---

## Quick Start

**One command:**

```bash
./start.sh        # Windows: double-click start.cmd
```

Checks deps, seeds if needed, starts both servers, and opens the app.
Details and flags in **[SETUP.md](SETUP.md)** — the full fresh-laptop guide
with a no-retraining checklist, GPU notes, verification steps, and
troubleshooting.

### Manual Prerequisites

- Python 3.11+
- Node.js 22 LTS
- For full database mode: a [Supabase](https://supabase.com) project

### 1. Backend Environment

```bash
cd backend
cp .env.example .env
```

Edit `backend/.env`.

The important variables are:

```env
SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_KEY="your-anon-key"
SUPABASE_SERVICE_KEY="your-service-role-key"
```

Other variables are optional. If you do not set Supabase credentials, the backend can still run, but data persistence paths that depend on Supabase will not work as expected.

### 2. Database Setup

If you are using Supabase:

1. Create a project at [supabase.com](https://supabase.com)
2. Open **SQL Editor**
3. Paste the contents of `backend/app/db/setup.sql`
4. Run it

That SQL file creates the tables the app expects and enables permissive policies for development.

If you want the schema separately, it is also available in `backend/app/db/schema.sql`.

### 3. Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 4. Seed the Database

```bash
cd backend
python -m app.db.seed
```

This loads synthetic data from `data/synthetic/`.

### 5. Start the Backend

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

The backend runs on **http://localhost:8000**.

### 6. Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**.

The frontend proxies `/api` requests to the backend in local development, so the app should work with the dev server running.

---

## Demo Credentials

| Username | Password | Notes |
|----------|----------|-------|
| `admin` | `admin123` | Full access |
| `planner` | `planner123` | Planner access |
| `operations` | `operations123` | Operations access |
| `engineer` | `engineer123` | Engineer access |

The app also assigns a hidden `viewer` role with limited permissions automatically.

---

## Roles and Access

| Area | Viewer | Engineer | Operations | Planner | Admin |
|------|--------|----------|------------|---------|-------|
| View dashboard, queue, timeline | ✅ | ✅ | ✅ | ✅ | ✅ |
| Defect Inspection & approval | ❌ | ✅ | ✅ | ✅ | ✅ |
| Map view | ✅ | ✅ | ✅ | ✅ | ✅ |
| View blocks, explain, comparison | ✅ | ✅ | ✅ | ✅ | ✅ |
| Run optimizer | ❌ | ✅ | ✅ | ✅ | ✅ |
| Approve plans | ❌ | ✅ | ✅ | ✅ | ✅ |
| What-If simulator | ❌ | ✅ | ✅ | ✅ | ✅ |
| Edit priority weights | ❌ | ❌ | ❌ | ✅ | ✅ |
| User management | ❌ | ❌ | ❌ | ❌ | ✅ |
| Audit log viewer | ❌ | ❌ | ❌ | ❌ | ✅ |

---

## Screens

| Screen | What you can do there |
|--------|------------------------|
| **Login** | Sign in with demo credentials |
| **Dashboard** | KPIs, priority distribution, recommendations, optimization progress, ⚡ Dynamic Replan |
| **Defect Inspection** | Upload an image, run local YOLO defect models with bounding boxes, review the AI maintenance recommendation (required tools + estimated repair time) and verify or edit it, generate a maintenance ticket, watch the multi-agent workflow, and approve the recommended block |
| **Map View** | Leaflet map on OpenStreetMap tiles with corridor polylines, status-coded assets (green/yellow/red), planned blocks, and trains |
| **Model Info** | Training metrics parsed live from local runs, training curves/confusion matrices, and one-click live sample predictions |
| **Maintenance Queue** | Browse and sort tasks by priority, department, status, and due date |
| **Corridor Timeline** | Gantt-style timeline with trains, windows, blocks, and department work |
| **Block Plan** | Review generated blocks, select them, and approve or revert |
| **Explainability** | Inspect task and block explanations |
| **What-If Simulator** | Change constraints and compare scenarios |
| **Before/After** | See quantified impact of optimization |
| **User Management** | Create users and assign roles Admin only |
| **Audit Log** | Review security and operation events Admin only |

---

## How the Optimizer Works

### Priority Scoring

The priority score is based on:

- asset criticality
- failure risk
- overdue factor
- train impact
- safety criticality

The weights are configurable through the API and the database.

### Constraint Optimization

The optimizer groups compatible tasks into shared blocks while respecting:

- train timetable constraints
- corridor availability
- safety requirements
- resource availability
- task dependencies
- operational restrictions

### Multi-Department Coordination

Instead of planning separate blocks for each department, the optimizer looks for compatible windows and coordinates work such as:

- Engineering
- S&T
- Traction

### Performance Behavior in the Current Build

The current backend keeps the event loop responsive by never running CPU-heavy or blocking work on it:

- **Bounded heavy pool** — YOLO inference, OR-Tools solves and agent orchestration run on a small dedicated executor (`app/core/pools.py`, sized by `HEAVY_POOL_SIZE`, default 2). Concurrent heavy jobs queue instead of stacking dozens of GIL-fighting threads; the loop keeps serving reads while a solve runs.
- **Blocking DB calls off the loop** — `async def` endpoints (plan approve/revert, inspection analyze) push synchronous PostgREST calls to a wider I/O pool (`IO_POOL_SIZE`, default 8).
- **Parallel DB reads** — `get_blocks` fetches blocks/assignments/departments concurrently; the dashboard, optimizer and simulation fan out their data fetches with `ThreadPoolExecutor`.
- **Caches** — `/api/health` caches its Supabase verdict for `HEALTH_CACHE_TTL` seconds (default 15, `0` disables) so probes don't each pay a full DB round trip; the audit API parses log files once and re-parses only when a file's mtime/size changes.

Under the 20-client stress harness this yields 0% 5xx with health p50 ~67 ms (was ~1.5 s) and no latency scaling with audit-log size. Remaining p95 spikes on co-hosted CPU work are the documented single-process/GIL limitation (PRD §49.4).

---

## Docker

From the project root:

```bash
docker compose up          # older installs: docker-compose up
```

Typical local ports:

- Frontend: **http://localhost:5173**
- Backend: **http://localhost:8000**

If you use Docker, make sure the backend environment is configured correctly before starting.

---

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SUPABASE_URL` | Supabase project URL | Yes, if using Supabase |
| `SUPABASE_KEY` | Supabase anon/public key | Yes, if using Supabase |
| `SUPABASE_SERVICE_KEY` | Supabase service_role key | Yes, if using Supabase for writes |
| `JWT_SECRET_KEY` | JWT signing secret | Optional |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime | Optional |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime | Optional |
| `HEALTH_CACHE_TTL` | Seconds `/api/health` caches its DB verdict (0 disables) | Optional |
| `AUDIT_LOG_DIR` | Directory the audit API reads `audit_*.log` from (default `logs/audit`) | Optional |
| `HEAVY_POOL_SIZE` | Threads for CPU-bound work (inference, solver, orchestration) | Optional |
| `IO_POOL_SIZE` | Threads for blocking DB/HTTP calls from async endpoints | Optional |

---

## Data

The demo uses synthetic data for:

- 3 departments: Engineering, S&T, Traction
- 150 assets across 3 corridors
- 300 maintenance tasks
- 75 trains per day
- 21 block windows across corridors

This data is for demonstration only and is not real railway data.

---

## Detection Models & Demo Flow

### Local CV model (trained on the bundled dataset)

| Model | Task | Dataset | Metric |
|-------|------|---------|--------|
| `models/raildoc_detection/raildoc_det` | Unified detection: light poles + track faults with bounding boxes (YOLO26n-det) | `RAILDOC_02.yolo26` (876 train / 262 val imgs) | mAP50 0.635 (poles 0.681 · track faults 0.589) |

Retrain from scratch (needs `ultralytics>=8.4.0` — the first release with
YOLO26; the script fine-tunes `yolo26n.pt`):

```bash
cd backend
pip install "ultralytics>=8.4.0" torch torchvision opencv-python-headless pillow
python -m app.cv.train_detector   # ~35 min on an RTX 3060 Ti
```

### End-to-end demo story (Defect Inspection screen)

1. **Upload** a track or light-pole image — the Detection Agent finds defects
   and assets, draws bounding boxes, and reports severity. A separate
   maintenance recommendation layer maps the detected defect class to
   required tools and an estimated repair time, which the operator can edit
   and verify (detection confidence stays in app state and is not displayed
   in the maintenance UI).
2. **Create Maintenance Request** — a ticket is generated and queued.
3. **Run Multi-Agent Planning Workflow** — watch the Agent Monitor as the
   Engineer, Planner, and Operations agents analyze the problem and the Admin
   Agent ranks candidate block plans by utility score.
4. **Approve & Commit Block** — the selected candidate becomes an approved
   maintenance block; its tasks are marked Scheduled and the block appears on
   the Corridor Timeline, Block Plan, and Map View.

### Dynamic replanning (PRD §18)

The **⚡ Dynamic Replan** button on the Dashboard (and
`POST /api/inspection/replan`) recalculates priorities for all pending
tasks, reruns the OR-Tools optimizer, persists the new plan, and writes an
audit entry. In production this endpoint is what new critical defects,
train schedule changes, or resource outages would trigger automatically.

### Full presentation walkthrough

See **[docs/demo/DEMO_SCRIPT.md](docs/demo/DEMO_SCRIPT.md)** for the
minute-by-minute demo script: exact images to upload, expected agent output,
explainability panels, judge Q&A, and failure recovery.

> The CV models, datasets, and demo metrics are for prototype demonstration only —
> not certified railway inspection results (PRD §42).

---

## Key Features in the Current App

### Audit Logging

Security-sensitive actions are logged, including:

- login attempts
- plan creation, approval, and revert
- optimizer and simulation runs
- priority weight changes
- data regeneration
- unauthorized access attempts

Admins can view audit logs with filters and statistics.

### Live Clock and Date

The header shows the current time and date for the session using IST formatting.

### Role-Based UI

The sidebar and available actions change based on the logged-in user's roles.

### Human-Verified Maintenance Recommendations

Each detection carries an AI-generated maintenance recommendation — required
tools and an estimated repair time — looked up from an editable defect-class
mapping (`frontend/src/data/maintenanceRecommendations.ts`) that is kept
deliberately separate from the CV detection layer. The recommendation is
always presented as requiring human verification: operators can rename, add
and remove tools, correct the estimated time, and save a "Human Verified"
version while the original AI recommendation is preserved. Unknown defect
classes degrade gracefully with a manual-entry prompt instead of an error.

### Map Basemap

The Map View uses public OpenStreetMap raster tiles in both light and dark mode, so the map itself
looks the same in either theme. Only the surrounding chrome (popups, zoom controls, attribution) is
themed. Dark-toned third-party basemaps such as CARTO or Mapbox are deliberately avoided: without a
paid API key they stamp an "API key required" watermark across every tile.

### Optimization Progress

The dashboard shows progress while the optimizer runs.

### Corridor Timeline Popovers

Clicking departments or blocks in the timeline opens a popover with quick details and navigation.

### Plan Approval Workflow

Block Plan includes approve and undo behavior with status feedback.

---

## API Overview

The backend exposes endpoints for:

- authentication and user management
- assets, tasks, trains, corridors, block windows
- priority weights and recalculation
- optimization and simulation
- plans, approval, and revert
- task and block explanations
- before/after comparison
- dashboard data
- audit logs, event types, and stats

Full endpoint behavior is defined in `backend/app/main.py` and the related API modules.

---

## Testing, Dataset Validation & Stress Testing

| Check | Command | What it covers |
|-------|---------|----------------|
| Backend tests | `cd backend && python -m pytest tests/ -v` | Auth, validation, optimizer, CV layer, the audit API (caching, filters, status-notation matching), and the stress/edge-case suite (`tests/test_stress.py`: rate-limit bursts → 429 JSON, malformed bodies → 400, hostile scenarios → 422, upload size caps, bounded in-memory stores) |
| Dataset validation | `cd backend && python scripts/validate_dataset.py` | Image/label pairing per split, YOLO box geometry (finite, in `[0,1]`, no zero-size or overflowing boxes), class ranges vs. `data.yaml`, image decode checks, and a cross-split duplicate (leakage) scan over `RAILDOC_02.yolo26/` |
| Frontend build | `cd frontend && npm run build` | TypeScript typecheck + production bundle |
| Load / stress test | start the backend, then `cd backend && python scripts/stress_load.py --duration 60 --clients 20` | Concurrent mixed traffic (dashboard reads, simulations, uploads, approve/revert churn, optimizer runs) with per-operation p50/p95 latency and a 5xx error budget |

Notes on the load harness:

- It probes `/api/health` first and falls back to a **DB-free traffic mix** when Supabase is unreachable (`--db auto|on|off` to override).
- Each virtual client carries its own `X-Forwarded-For` identity, so rate limits behave as they would for real users.
- **429s are counted separately** — hitting a rate limit is correct behaviour, not an error. Exit code is non-zero only when 5xx + transport errors exceed `--max-5xx-pct` (default 1%).
- CI runs the backend suite, the dataset validator, and the frontend build on every push — plus a **load-smoke job** that boots the API on the runner and runs `stress_load.py` against it for 30 s (`.github/workflows/ci.yml`). DB-backed tests self-skip when `SUPABASE_URL` is unset, and the backend job publishes a coverage report (`--cov=app`) as a run artifact.

The start scripts run the seed step for you: `start.sh` (and the fallback path of `start.cmd`) executes `python -m app.db.seed` before booting the backend; `start.sh` only reseeds when the database is empty or `--reseed` is passed. Both scripts also sanity-check `backend/.env` before boot — JSON-valued entries (connection specs etc.) must be valid single-line JSON, and the scripts report the offending line instead of letting the backend crash later with a cryptic parse error.

---

## Future Scope

Not in the MVP — the post-hackathon roadmap (detailed in [PRD.md](PRD.md) §49):

- **Live integrations** — real TMS/SMMS/TDMS/BDMS/COA connectors behind the existing mock adapter interfaces, plus live timetable feeds for automatic replanning.
- **ML & CV** — learned priority weights, per-asset failure prediction, more defect classes and segmentation for the detector, and an active-learning loop from inspector corrections.
- **Planning depth** — multi-week/monthly horizons, crew rostering and skill matching, stochastic train-delay simulation in the What-If engine.
- **Scale & hardening** — multi-worker deployment (shared rate-limit/lock store), CI running tests + dataset validator + build + load smoke test, refresh-token rotation / OIDC SSO, observability and alerting.
- **Field & geospatial** — offline-first mobile inspection app, real GIS corridor geometry instead of KM-marker projection, satellite change detection as a clearly separated secondary source.
- **Governance** — audit-log export to SIEM, role-specific dashboards, plan-version diff views, and compliance reporting.

---

## License

MIT
