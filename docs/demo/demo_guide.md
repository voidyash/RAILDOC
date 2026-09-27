# Demo Guide — RailDoc

## Pre-Demo Setup

```bash
# 1. Start backend
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000

# 2. Start frontend
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## Demo Script (10-15 minutes)

### Act 1: The Problem (2 min)

**Show the Maintenance Queue** (Screen 2)

- 300 maintenance tasks across 3 departments
- Tasks are scattered, no coordination
- Highlight: Engineering, S&T, and Traction each want blocks in the same corridor at overlapping times
- Point out overdue tasks, high criticality items

> "Right now, each department plans independently. Engineering wants
> 09:00-10:00, S&T wants 09:30-10:15, Traction wants 09:45-10:30.
> Without coordination, this means 3 separate blocks."

### Act 2: AI Prioritization (2 min)

**Click "Run Optimizer"** on Dashboard

- Show priority distribution updating
- Show the AI recommendations appearing
- Explain the scoring model:

> "AI scores each task based on 5 factors: asset criticality (30%),
> failure risk (25%), overdue factor (20%), train impact (15%),
> and safety criticality (10%). These weights are configurable."

### Act 3: The Optimized Plan (3 min)

**Navigate to Block Plan** (Screen 4)

- Show generated blocks with multi-department coordination
- Click on a block to see explanation
- Highlight: 3 departments combined into 1 block

> "The optimizer found that Engineering, S&T, and Traction tasks
> in corridor C-07 are compatible. Instead of 3 blocks causing
> 135 minutes of downtime, we now have 1 coordinated block causing
> only 45 minutes."

### Act 4: Corridor Timeline (2 min)

**Navigate to Corridor Timeline** (Screen 3)

- Show the Gantt-style visualization
- Highlight train movements vs maintenance blocks
- Show how blocks avoid train conflicts

### Act 5: Explainability (2 min)

**Navigate to Explainability** (Screen 5)

- Select a task → show why it was scheduled
- Show score breakdown, compatible tasks, reason
- Select a block → show coordination benefit

> "Every decision is explainable. This task was scheduled because
> it has high priority, low train impact, and 3 compatible tasks
> in the same corridor."

### Act 6: Before/After (2 min)

**Navigate to Before/After** (Screen 7)

- Show the quantified improvement:

```
Before: 300 blocks, 18000 min downtime, 150 conflicts
After:  20 blocks,  2100 min downtime,  36 conflicts
```

- Blocks eliminated: 280
- Downtime saved: 15900 minutes
- Multi-department blocks: 6

### Act 7: What-If Simulation (2 min)

**Navigate to What-If Simulator** (Screen 6)

- Load baseline
- Run "Extended Block Duration" preset (90 min)
- Show the comparison
- Run "Heavy Freight Traffic" preset (+20%)
- Show how the plan adapts

> "Controllers can test scenarios before committing to a plan.
> What if we extend blocks by 30 minutes? What if freight traffic
> increases 20%?"

## Key Metrics to Highlight

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Total Blocks | 300 | 20 | -93% |
| Downtime | 18000 min | 2100 min | -88% |
| Train Conflicts | 150 | 36 | -76% |
| Block Utilization | 35% | 85% | +143% |
| Multi-Dept Blocks | 0 | 6 | +∞ |

## Demo Data

The system uses synthetic but realistic data:

- **3 departments:** Engineering, S&T, Traction
- **150 assets** across 3 corridors (C-07, C-12, C-19)
- **300 maintenance tasks** (defects, overdue, preventive, inspection)
- **75 trains** (passenger + goods) per day
- **21 block windows** across corridors
- Deliberate conflicts injected for demo impact

## Talking Points

1. **This is not a dashboard.** It's a decision-support optimization system.
2. **AI prioritizes. Optimization schedules. Humans approve.**
3. **Every decision is explainable.** No black-box scheduling.
4. **Multi-department coordination** is the key differentiator.
5. **Before/after evidence** proves the value quantitatively.
6. **What-if simulation** lets controllers test scenarios safely.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Backend won't start | `pip install -r requirements.txt` |
| Frontend blank page | `npm install` then `npm run dev` |
| No blocks generated | Click "Run Optimizer" first |
| Slow optimization | Optimizer has 30s timeout; reduce task count |
