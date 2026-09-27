# RailDoc — Live Demo Script

End-to-end walkthrough for the Smart India Hackathon presentation.
Every step below was verified against the running app.

---

## Before the demo (one-time setup)

```bash
# Terminal 1 — backend
cd backend
python -m app.db.seed
python -m uvicorn app.main:app --port 8000

# Terminal 2 — frontend
cd frontend
npm run dev
```

Open **http://localhost:5173** and sign in:

| Username | Password | Why |
|----------|----------|-----|
| `admin` | `admin123` | full access — use this for the demo |

Pre-checks (30 seconds):

1. Dashboard loads with KPIs → backend + database are up.
2. **Model Info** screen shows the detector as **Ready**
   (unified light_pole + tracks_fault detection, mAP50 on the Model Info card).
3. Have a railway image ready (any track or light-pole photo; bundled frames
   live in `RAILDOC_02.yolo26/test/images/`).

---

## Phase 1 — The problem (30 s)

On the **Dashboard**, point out:

- 3 departments planning separately (Engineering, S&T, Traction)
- maintenance backlog and fragmented blocks in the KPIs
- the Before/After screen later shows how RailDoc consolidates them

## Phase 2 — Detection Agent (60 s)

Screen: **Defect Inspection**

1. Asset type: **Track**, corridor **C-07**, location `KM 241.7`.
2. Upload `es5n3o3y5cu11.jpg`.
3. Click **Run Detection**.

Expected result (verified):

```
⚠ Defect Detected
detections: track_defect — confidence ≈ 100% — severity: critical
bounding box drawn over the rail defect
inference: ~1.3 s (GPU)
```

4. Optional: switch asset type to **Light Pole** and upload the pole image —
   a pole is localized with a bounding box (~50–80% confidence on photo-style
   shots; aerial DJI shots may miss — say "recall improves with
   ground-level photos, as expected").

## Phase 3 — Ticket + multi-agent workflow (90 s)

1. Click **Create Maintenance Request** → ticket ID appears
   (e.g. `ENG-72BAA9`) and is queued in the Maintenance Queue.
2. Click **Run Multi-Agent Planning Workflow →**.

The **Agent Monitor** shows the live pipeline (PRD §24):

```
● Detection Agent   Defect identified: track_defect (critical, confidence 98%)
● Engineer Agent    Repair requirements determined: Rail Repair, 75 min, dept Engineering
● Planner Agent     8 compatible task(s) found in corridor C-07; departments: Engineering, S&T, Traction
● Operations Agent  15 candidate plan(s) evaluated; best utility 61.3
● Admin Agent       Selected candidate CAND-… (immediate)
○ Human Approval Required
```

Right panel: candidate plans ranked by utility, with the winner showing
window, operational impact (freight conflicts), and utilization.

## Phase 4 — Explainability + Human approval (45 s)

On the **Why this block?** panel:

```
✓ 8 compatible task(s) in corridor C-07
✓ Departments: Engineering, S&T, Traction
✓ Operational impact: none (0 freight conflicts)
✓ Block utilization: …%
✓ Safety constraints satisfied
```

Click **Approve & Commit Block**.

Expected: green confirmation with the new block ID
(e.g. `BLK-WF-475c6617`) and a link to the Corridor Timeline.

## Phase 5 — Where the plan landed (60 s)

1. **Corridor Timeline** — the new approved block appears with its
   department tasks in the window.
2. **Block Plan** — block listed with status **Approved**.
3. **Map View** — corridor C-07 shows red markers for assets with open
   defects; the committed block shows as a blue marker.
4. **Maintenance Queue** — the ticket task is now **Scheduled**.

## Phase 6 — Dynamic replanning (45 s) — PRD §18

On the **Dashboard**, click **⚡ Dynamic Replan**.

Expected toast:

```
✓ Replan complete (dashboard_manual_trigger) — N/302 tasks scheduled in M blocks
```

Explain: priorities recalculated, optimizer re-run, plan re-persisted,
audit-logged — the same path a new critical defect would trigger automatically.

## Phase 7 — Model credibility (30 s)

Screen: **Model Info**

- metrics parsed from local training runs (no hand-typed numbers)
- training curves + confusion matrices rendered from the artifacts
- click **Run sample inference** → live predictions on dataset images,
  including a "no defect" negative example

## Phase 8 — Wrap (30 s)

Back to **Before/After**: 300→20 blocks, −88% downtime (synthetic demo data).
Close with the pipeline:

```
DETECT → UNDERSTAND → PRIORITIZE → DECOMPOSE → COORDINATE → OPTIMIZE → EXPLAIN → APPROVE
```

---

## Backup answers (likely judge questions)

| Question | Answer |
|----------|--------|
| "Are the models real?" | Trained locally in `backend/app/cv/train_*.py` on the bundled Kaggle datasets; metrics parsed live from `results.csv` in `models/`. |
| "What if detection is wrong?" | Human approval is mandatory (PRD §20); Reject discards without persistence. |
| "How does replanning trigger?" | `/api/inspection/replan` recalculates priorities + reruns OR-Tools; triggers listed in PRD §18 are wired to this endpoint. |
| "Is the map real GIS?" | Illustrative demo visualization (PRD §14); positions derived from corridor + KM marker, not survey data. |
| "Data real?" | All synthetic (PRD §34); adapters for TMS/SMMS/TDMS/BDMS/COA are the production integration path. |

## Failure recovery

| Symptom | Fix |
|---------|-----|
| Model Info shows "Not loaded" | Backend still warming up — wait ~10 s and reload; check `backend` terminal for weight-loading errors. |
| Detection returns 503 | Model missing — retrain (`python -m app.cv.train_detector`). |
| Workflow button spins forever | Check backend log; Supabase connectivity is required for ticket persistence. |
| Map tiles blank | Internet needed for OpenStreetMap tiles; markers still render. |
