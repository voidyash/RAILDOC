# System Architecture

## Overview

RailDoc is an AI-assisted railway maintenance
decision-support platform that converts fragmented maintenance requirements
into coordinated block plans.

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    React + TypeScript UI                   │
│  Dashboard │ Queue │ Timeline │ Blocks │ Simulation │ Expl │
└────────────────────────┬─────────────────────────────────┘
                         │ REST API
                         ▼
┌──────────────────────────────────────────────────────────┐
│                    FastAPI Backend                        │
│  API Layer │ Auth │ Plan Management │ Audit │ CORS        │
└───────┬────────────┬────────────┬────────────────────────┘
        │            │            │
        ▼            ▼            ▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│ Priority  │  │ Block    │  │ Explain  │
│ Engine    │  │ Optimizer│  │ Engine   │
│ (scoring) │  │(OR-Tools)│  │          │
└──────────┘  └──────────┘  └──────────┘
        │            │
        ▼            ▼
┌──────────────────────────────────┐
│        In-Memory Data Store      │
│  Assets │ Tasks │ Trains │ Blocks│
└──────────────────────────────────┘
        ▲
        │
┌──────────────────────────────────┐
│     Mock Integration Layer       │
│  TMS │ SMMS │ TDMS │ COA        │
│  (synthetic data generators)     │
└──────────────────────────────────┘
```

## Data Flow

```
1. Data Ingestion
   TMS/SMMS/TDMS/COA → Synthetic JSON → Unified Model
                                          │
2. Priority Scoring                        │
   Weighted scoring ← Configurable weights │
                                          │
3. Compatibility Detection                 │
   Safety + resource + corridor checks     │
                                          │
4. Block Optimization                      │
   OR-Tools CP-SAT + Greedy Heuristic ─────┘
                                          │
5. Plan Generation
   Blocks + Assignments + Metrics          │
                                          │
6. Explainability
   Why each task/block was selected ◄──────┘
                                          │
7. Human Review
   Approve / Modify / Regenerate
```

## Key Components

### Priority Engine
- **Location:** `backend/app/ai/priority_engine.py`
- **Config:** `models/priority/weights.json`
- **Algorithm:** Weighted scoring with configurable weights
- **Output:** Priority score (0-100) for each maintenance task

### Block Optimizer
- **Location:** `backend/app/optimizer/block_optimizer.py`
- **Constraints:** `optimizer/constraints/hard_constraints.json`
- **Objectives:** `optimizer/objectives/objectives.json`
- **Solver Config:** `optimizer/solver/config.json`
- **Algorithm:** Greedy heuristic with constraint checking (CP-SAT for smaller instances)

### Explainability Engine
- **Location:** Backend API endpoints `/api/explain/task/{id}` and `/api/explain/block/{id}`
- **Output:** Human-readable reasons for scheduling decisions

### What-If Simulator
- **Location:** Backend API endpoint `/api/simulate`
- **Capability:** Modify constraints and regenerate plans for comparison

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/data/assets` | GET | All assets |
| `/api/data/tasks` | GET | All maintenance tasks |
| `/api/data/trains` | GET | All trains |
| `/api/data/corridors` | GET | All corridors |
| `/api/data/block-windows` | GET | Available block windows |
| `/api/data/regenerate` | POST | Regenerate synthetic data |
| `/api/priority/weights` | GET/PUT | Get/update priority weights |
| `/api/priority/calculate` | GET | Calculate all priorities |
| `/api/optimize` | POST | Run the optimizer |
| `/api/plans/current` | GET | Get current plan |
| `/api/plans/approve` | POST | Approve current plan |
| `/api/explain/task/{id}` | GET | Explain task scheduling |
| `/api/explain/block/{id}` | GET | Explain block composition |
| `/api/simulate` | POST | Run what-if simulation |
| `/api/comparison/before-after` | GET | Before/after metrics |
| `/api/dashboard` | GET | Dashboard KPIs |

## Data Model

### Core Entities
- **Asset** — Railway infrastructure component with criticality rating
- **MaintenanceTask** — Work item with priority, department, and requirements
- **Train** — Scheduled train movement with corridor and timing
- **BlockWindow** — Available maintenance window
- **MaintenanceBlock** — Generated block with assigned tasks
- **Plan** — Weekly/monthly plan containing blocks

### Relationships
```
Asset (1) ──── (N) MaintenanceTask
MaintenanceTask (N) ──── (1) MaintenanceBlock
MaintenanceBlock (N) ──── (1) Plan
Corridor (1) ──── (N) Asset
Corridor (1) ──── (N) BlockWindow
Corridor (1) ──── (N) Train
```

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | React + TypeScript + Tailwind | UI |
| Charts | Recharts | Data visualization |
| Backend | Python + FastAPI | API server |
| Optimization | Google OR-Tools | Constraint solving |
| ML | scikit-learn (planned) | Risk prediction |
| Data | JSON (in-memory) | Prototype storage |
| Deployment | Docker + Docker Compose | Containerization |
