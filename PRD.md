# PRODUCT REQUIREMENTS DOCUMENT

## RailDoc — AI-Powered Automatic Block Planning & Railway Asset Inspection

**Version:** 2.0
**Product Type:** AI-powered railway maintenance inspection, planning and decision-support platform
**Deployment:** Local / Dockerized MVP
**Primary Objective:** Maximize railway asset availability while minimizing maintenance downtime, block fragmentation and train disruption.

---

# 1. PRODUCT SUMMARY

## 1.1 Product Name

**RailDoc**

## 1.2 Product Vision

RailDoc is an AI-powered railway maintenance decision-support platform that combines:

* Computer vision-based defect detection
* Multi-agent AI coordination
* Maintenance prioritization
* Cross-department task coordination
* Constraint-based block optimization
* Geospatial visualization
* Dynamic replanning
* Explainable AI
* Human approval

The system receives railway inspection information, identifies defects, determines the required maintenance, distributes the workload among specialized AI agents, finds compatible maintenance activities, and generates an optimized maintenance block plan.

## 1.3 Core Principle

> **AI detects and prioritizes the problem. Specialized agents analyze and coordinate it. Optimization decides when and how the work should happen. Humans approve the final plan.**

---

# 2. PROBLEM STATEMENT

Railway infrastructure maintenance involves multiple departments and disconnected activities.

Relevant information can include:

* Track defects
* Signal defects
* OHE/traction defects
* Light-pole defects
* Preventive maintenance
* Overdue maintenance
* Train schedules
* Freight movements
* Available maintenance blocks
* Corridor restrictions
* Resource availability

When these activities are planned independently, the railway can experience:

* Separate blocks for compatible work
* Poor inter-department coordination
* Excess asset downtime
* Maintenance backlog
* Inefficient block utilization
* Unnecessary train disruption
* Delayed response to critical defects

RailDoc introduces an intelligent coordination layer between inspection, maintenance departments and operations.

---

# 3. GOALS

## Primary Goal

**Maximize fixed railway asset availability with minimum operational disruption.**

## Supporting Goals

1. Detect infrastructure defects using computer vision.
2. Automatically create maintenance tasks from detected defects.
3. Prioritize maintenance tasks according to severity and operational importance.
4. Divide complex maintenance problems among specialized AI agents.
5. Coordinate Engineering, S&T and Traction activities.
6. Identify compatible tasks that can share a maintenance block.
7. Optimize block allocation using Google OR-Tools.
8. Minimize train disruption.
9. Minimize maintenance downtime.
10. Reduce maintenance backlog.
11. Provide explainable decisions.
12. Support dynamic replanning.
13. Provide geospatial visualization.
14. Maintain human approval for operational plans.
15. Run the complete MVP locally.

---

# 4. SYSTEM SCOPE

RailDoc consists of six major layers:

```text
┌───────────────────────────────────────────────┐
│                 USER INTERFACE                │
│ Dashboard | Map | Defects | Plans | Timeline │
└───────────────────────┬───────────────────────┘
                        ↓
┌───────────────────────────────────────────────┐
│              AI AGENT ORCHESTRATOR            │
│                 ADMIN AGENT                   │
└───────────────────────┬───────────────────────┘
                        ↓
        ┌───────────────┼────────────────┐
        ↓               ↓                ↓
 Detection         Engineer           Planner
   Agent             Agent             Agent
        │               │                │
        └───────────────┼────────────────┘
                        ↓
                 Operations Agent
                        ↓
┌───────────────────────────────────────────────┐
│          OPTIMIZATION / DECISION LAYER        │
│                 Google OR-Tools               │
└───────────────────────┬───────────────────────┘
                        ↓
┌───────────────────────────────────────────────┐
│                DATA / MODEL LAYER             │
│ PostgreSQL | Dataset | ML Models | Audit Data │
└───────────────────────────────────────────────┘
```

---

# 5. AI AGENT ARCHITECTURE

The traditional organizational roles are converted into specialized AI agents.

## 5.1 Admin Agent — Master Orchestrator

The Admin Agent is the central decision-making coordinator.

It does not perform every task itself.

Its responsibilities are:

* Receive new maintenance incidents.
* Understand the problem.
* Break the problem into subtasks.
* Assign subtasks to appropriate agents.
* Collect agent outputs.
* Evaluate candidate solutions.
* Trigger replanning when required.
* Send candidate plans to the optimization engine.
* Generate an explainable final recommendation.
* Maintain workflow state.
* Escalate critical issues for human approval.

### Example

```text
New Track Defect
       ↓
Admin Agent
       ↓
"What needs to happen?"
       ↓
┌──────────────┬──────────────┬──────────────┐
↓              ↓              ↓
Engineer       Planner        Operations
Agent          Agent          Agent
↓              ↓              ↓
Repair         Compatible     Train
requirements   tasks          impact
       \          |           /
        \         |          /
         └────────┼─────────┘
                  ↓
             OR-Tools
                  ↓
          Optimized Block
                  ↓
           Human Approval
```

---

# 6. DETECTION AGENT

## Purpose

Identify infrastructure defects from inspection images.

## Input

* Railway track images
* Light-pole images
* Future infrastructure datasets
* Inspector-uploaded images

## Dataset

The MVP will use static datasets stored locally in:

```text
RAILDOC_02.yolo26/
├── train/
├── valid/
└── test/
```

The dataset contains annotated railway imagery covering:

* Light poles (asset detection)
* Track faults (defect detection with bounding boxes)

The dataset will be used locally for model training.

## Processing Pipeline

```text
Image
 ↓
Preprocessing
 ↓
Object Detection
 ↓
Defect Localization
 ↓
Defect Classification
 ↓
Confidence Score (kept in app state, not displayed in the maintenance UI)
 ↓
Severity Estimation
 ↓
Maintenance Recommendation ← defect-class mapping (tools + time)
 ↓
Maintenance Ticket
```

## Output

```json
{
  "asset_id": "TRACK-C07-241",
  "asset_type": "track",
  "defect_type": "rail_crack",
  "confidence": 0.94,
  "severity": "critical",
  "location": "KM 241.7",
  "department": "engineering"
}
```

## Object Detection Requirement

The system must visually highlight the detected defect.

Example:

```text
Original Image
       ↓
Object Detection
       ↓
┌─────────────────────┐
│      Rail Crack     │
│      ███████        │ ← Bounding Box
└─────────────────────┘
```

The UI should show:

* Original image
* Detected defect
* Bounding box
* Defect type
* Required tools + estimated repair time (maintenance recommendation — human editable, see §23.1)
* Severity
* Asset ID
* Location

The detection confidence is kept in application state for auditing and
downstream consumers, but it is not displayed in the maintenance-facing UI.

---

# 7. ENGINEER AGENT

## Purpose

Determine what physical maintenance is required.

## Responsibilities

* Analyze detected defect.
* Determine maintenance type.
* Identify responsible department.
* Estimate maintenance duration.
* Identify required resources.
* Identify safety requirements.
* Identify isolation/disconnection requirements.
* Determine technical compatibility with other tasks.

## Output

```text
Defect:
Rail Crack

Severity:
Critical

Department:
Engineering

Maintenance:
Rail Repair

Estimated Duration:
60 minutes

Resources:
Track maintenance crew
Repair equipment

Safety:
Track isolation required
```

---

# 8. PLANNER AGENT

## Purpose

Find maintenance activities that can potentially be performed together.

The Planner Agent analyzes:

* Location
* Corridor
* Time
* Block type
* Department
* Resources
* Safety requirements
* Isolation requirements
* Dependencies
* Technical compatibility

Example:

```text
Track Repair
     +
Signal Inspection
     +
OHE Inspection
     ↓
Compatibility Check
     ↓
Compatible
     ↓
Candidate Shared Block
```

The Planner Agent creates **candidate plans**.

It does not override hard safety or operational constraints.

---

# 9. OPERATIONS AGENT

## Purpose

Evaluate the effect of proposed maintenance blocks on railway operations.

It analyzes:

* Train timetable
* Passenger trains
* Freight trains
* Corridor availability
* Existing blocks
* Train conflicts
* Operational restrictions
* Block duration

Example:

```text
Candidate Block
02:00–03:30
       ↓
Operations Agent
       ↓
Train timetable analysis
       ↓
✓ No passenger conflict
✓ Corridor available
⚠ 1 freight movement affected
       ↓
Operational Impact = Low
```

---

# 10. UTILITY-BASED DECISION ENGINE

RailDoc uses a utility-based approach for selecting between possible maintenance strategies.

A conceptual utility score is:

```text
UTILITY =

+ Asset Availability
+ Critical Tasks Completed
+ Block Utilization
+ Multi-Department Coordination

- Asset Downtime
- Train Disruption
- Number of Blocks
- Unused Capacity
- Maintenance Backlog
```

Weights are configurable.

Example:

```text
Candidate A → Utility = 71
Candidate B → Utility = 89
Candidate C → Utility = 63

Selected:
Candidate B
```

The utility engine is responsible for evaluating the quality of alternatives.

The mathematical feasibility and scheduling problem is handled by OR-Tools.

---

# 11. OPTIMIZATION ENGINE

## Technology

**Google OR-Tools**

## Responsibilities

* Block allocation
* Task scheduling
* Constraint satisfaction
* Cross-department coordination
* Conflict avoidance
* Objective optimization

## Decision Variables

```text
x(task, block)
start(task)
end(task)
block_activation(block)
```

## Hard Constraints

A task can only be scheduled if:

```text
corridor_available = true

block_type_compatible = true

resources_available = true

safety_requirements_satisfied = true

isolation_requirements_satisfied = true

no_train_conflict = true

dependencies_satisfied = true
```

## Optimization Objectives

### Maximize

* Asset availability
* Critical task completion
* Block utilization
* Multi-department coordination

### Minimize

* Asset downtime
* Train disruption
* Number of blocks
* Unused capacity
* Maintenance backlog
* Conflicting activities

---

# 12. COMPLETE END-TO-END ALGORITHM

```text
STEP 1
Inspector identifies a potential defect
        ↓
STEP 2
Inspector uploads image through application
        ↓
STEP 3
Detection Agent receives image
        ↓
STEP 4
Computer Vision Model performs inference
        ↓
STEP 5
Object Detection highlights actual defect
        ↓
STEP 6
Defect is classified
        ↓
STEP 7
Severity + confidence are calculated
(confidence stays internal — not displayed)
        ↓
STEP 8
Maintenance ticket is generated, with a maintenance
recommendation (required tools + estimated repair time)
attached from the defect-class mapping
        ↓
STEP 9
Admin Agent receives ticket
        ↓
STEP 10
Admin Agent decomposes the problem
        ↓
STEP 11
Engineer Agent determines repair requirements
        ↓
STEP 12
Planner Agent searches for compatible maintenance work
        ↓
STEP 13
Operations Agent evaluates train/block impact
        ↓
STEP 14
Agents return their findings to Admin Agent
        ↓
STEP 15
Candidate maintenance plans are generated
        ↓
STEP 16
Utility Engine evaluates candidates
        ↓
STEP 17
OR-Tools checks hard constraints
        ↓
STEP 18
Optimal block plan is generated
        ↓
STEP 19
Operational impact is calculated
        ↓
STEP 20
System explains why the plan was selected
        ↓
STEP 21
Human reviews the recommendation
        ↓
STEP 22
Approve / Modify / Reject
        ↓
STEP 23
Final maintenance plan is stored
        ↓
STEP 24
Asset and maintenance status are updated
        ↓
STEP 25
Audit record is generated
```

---

# 13. DATASET INTEGRATION

## 13.1 Unified RailDoc Detection Dataset (RAILDOC_02.yolo26)

Static training dataset for the Detection Agent.

```text
RAILDOC_02.yolo26/
```

Classes:

* `light_pole`
* `tracks_fault`

Used for:

* Training
* Validation
* Testing
* Object detection (unified light-pole + track-fault model)

## 13.2 Dataset Architecture

```text
RAILDOC_02.yolo26/
│
├── train/
│   ├── images/
│   └── labels/
│
├── valid/
│   ├── images/
│   └── labels/
│
└── test/
    ├── images/
    └── labels/
```

The model must be trained locally from the supplied dataset for the MVP.

---

# 14. GOOGLE EARTH / GOOGLE GLOBE INTEGRATION

## Purpose

The geospatial source is used as a **testing and visualization layer**, not as the primary training dataset.

The system can select a specific railway corridor or geographic area and use available static imagery/data to demonstrate inference.

## Workflow

```text
Selected Geographic Area
          ↓
Google Globe / Geospatial Source
          ↓
Static Test Imagery
          ↓
Trained Detection Model
          ↓
Defect Detection
          ↓
Asset Location
          ↓
Maintenance Ticket
          ↓
AI Agent Workflow
          ↓
Optimized Maintenance Plan
```

## Important MVP Boundary

The system should explicitly distinguish:

### Training Data

```text
Kaggle Dataset
      ↓
Model Training
```

### Testing / Demonstration Data

```text
Selected Geographic Area
      ↓
External Geospatial Imagery
      ↓
Model Inference
```

The prototype must not claim that satellite/geospatial imagery provides the same inspection quality as dedicated railway inspection equipment.

---

# 15. RAILWAY SYSTEM INTEGRATIONS

The production architecture should support adapters for the major railway information systems.

## 15.1 TMS — Track Management System

Provides:

* Track defects
* Track maintenance tasks
* Asset information
* Location
* Maintenance status
* Inspection information

```text
TMS
 ↓
TMS Adapter
 ↓
Unified RailDoc Data Model
```

## 15.2 SMMS — Signalling Maintenance & Management System

Provides:

* Signal defects
* Signal maintenance
* Signal assets
* Maintenance status
* Required resources

```text
SMMS
 ↓
SMMS Adapter
 ↓
Unified Data Model
```

## 15.3 TDMS — Traction Distribution Management System

Provides:

* OHE/traction defects
* Electrical maintenance tasks
* Asset information
* Isolation requirements
* Maintenance status

```text
TDMS
 ↓
TDMS Adapter
 ↓
Unified Data Model
```

## 15.4 BDMS — Block/Disconnection Management

Provides:

* Block requests
* Disconnection requests
* Block availability
* Block status
* Requested duration

```text
BDMS
 ↓
BDMS Adapter
 ↓
Block Availability
 ↓
Optimizer
```

## 15.5 COA — Control Office Application

Provides operational information such as:

* Train timetable
* Corridor availability
* Train movements
* Operational restrictions

```text
COA
 ↓
COA Adapter
 ↓
Operations Agent
 ↓
OR-Tools
```

For the hackathon MVP, these systems should be represented through **mock adapters and realistic schemas**, because proprietary live railway APIs are not assumed to be available.

---

# 16. UNIFIED DATA MODEL

All incoming information must be converted into a common structure.

Each maintenance task should contain:

```text
Task ID
Department
Asset ID
Asset Type
Location
Corridor
Task Type
Defect Type
Criticality
Failure Risk
Due Date
Estimated Duration
Required Block Type
Required Resources
Safety Requirement
Isolation Requirement
Train Impact
Dependencies
Status
Source
```

Example:

```json
{
  "task_id": "ENG-241",
  "department": "engineering",
  "asset_id": "TRACK-C07-241",
  "asset_type": "track",
  "location": "KM 241.7",
  "corridor": "C-07",
  "task_type": "repair",
  "defect_type": "rail_crack",
  "criticality": 92,
  "failure_risk": 0.78,
  "estimated_duration": 60,
  "required_block_type": "track_isolation",
  "safety_requirement": "mandatory",
  "status": "pending"
}
```

---

# 17. PRIORITY ENGINE

Every maintenance task receives a priority score.

Initial MVP scoring:

```text
Priority Score =

30% Asset Criticality
+
25% Failure Risk
+
20% Overdue Factor
+
15% Train Impact
+
10% Safety Criticality
```

The weights must be configurable.

ML-based priority prediction can be introduced later when sufficient historical data is available.

---

# 18. DYNAMIC REPLANNING

The Admin Agent must trigger replanning when important conditions change.

Examples:

```text
New Critical Defect
       ↓
Admin Agent
       ↓
Recalculate Priorities
       ↓
Find Compatible Tasks
       ↓
Recalculate Utility
       ↓
OR-Tools
       ↓
New Plan
```

Replanning triggers include:

* New critical defect
* Block becomes unavailable
* Train added
* Train removed
* Train schedule changes
* Maintenance duration changes
* Resource becomes unavailable
* Asset criticality changes
* New maintenance request

---

# 19. INSPECTION WORKFLOW

## Inspector Workflow

```text
Inspector Login
      ↓
Select Asset / Location
      ↓
Upload Image
      ↓
Detection Agent
      ↓
Defect Detected
      ↓
Bounding Box
      ↓
Defect Classification
      ↓
Severity
      ↓
Submit Inspection
```

The inspector does not manually decide the complete maintenance plan.

The system converts the inspection into an actionable maintenance request.

---

# 20. HUMAN-IN-THE-LOOP

RailDoc is a decision-support platform.

It must **not automatically issue safety-critical railway commands**.

The final workflow is:

```text
AI Recommendation
       ↓
Human Review
       ↓
┌──────┼───────┐
↓      ↓       ↓
Approve Modify Reject
       ↓
    Regenerate
       ↓
Final Approved Plan
```

The approved plan is stored with:

* User
* Timestamp
* Model version
* Dataset version
* Optimization configuration
* Agent decisions
* Changes
* Final plan

---

# 21. EXPLAINABILITY

For every major decision, the system should explain:

### Why was this defect prioritized?

```text
Criticality: 92/100
Failure Risk: 78%
Safety Criticality: High
Overdue: 14 days

Reason:
High-risk critical asset requiring immediate maintenance.
```

### Why this block?

```text
Available Window:
02:00–03:30

Compatible Tasks:
3

Train Impact:
Low

Block Utilization:
96%

Reason:
Three compatible maintenance activities can be
completed within the same corridor block.
```

### Why were tasks combined?

```text
Engineering + S&T + Traction

Shared:
✓ Corridor
✓ Block window
✓ Compatible isolation
✓ Resource availability

Result:
1 coordinated block instead of 3 separate blocks.
```

---

# 22. UI REQUIREMENTS

## Screen 1 — Command Dashboard

Display:

* Asset availability
* Critical defects
* Maintenance backlog
* Planned blocks
* Block utilization
* Train impact
* AI recommendations
* Active agent workflows

Example:

```text
Asset Availability       94.7%
Critical Defects              8
Maintenance Backlog         127
Planned Blocks                32
Block Utilization             91%
Train Impact                 -18%

AI Recommendation:
Combine 3 compatible tasks
```

---

# 23. DEFECT INSPECTION SCREEN

Display:

```text
┌───────────────────────────────────┐
│          INSPECTION IMAGE         │
│                                   │
│       ┌───────────────┐           │
│       │  RAIL CRACK   │           │
│       └───────────────┘           │
└───────────────────────────────────┘

Defect: Rail Crack
Severity: Critical
Asset: TRACK-C07-241
Location: KM 241.7

MAINTENANCE REQUIREMENTS
AI-generated · Requires Human Verification

Required Tools:
• Rail Grinder        [Edit]
• Measuring Gauge     [Edit]
• Safety Kit          [Edit]   [+ Add Tool]

Estimated Repair Time:
2 hr 30 min

[ Edit Recommendations ]

[Create Maintenance Request]
```

## 23.1 Maintenance Recommendation Layer

The recommendation layer is deliberately separate from the detection layer:
the CV model (YOLO26n-det) never generates tools or repair times. After
inference, the detected defect class is looked up in an editable frontend
mapping (`frontend/src/data/maintenanceRecommendations.ts`) that provides,
per defect class:

* defect display name
* required tools / equipment
* estimated repair time

Rules:

* The mapping is a plain data structure — supporting a new defect class is a
  single entry, no model changes.
* Unknown defect classes degrade gracefully: the card shows "Maintenance
  recommendation unavailable" and the operator can add tools and estimated
  time manually.
* Two states are maintained: the original AI recommendation is never
  destroyed, and edits are saved into a separate "Human Verified"
  recommendation marked with a ✓ Verified badge.
* Operators can rename, add and remove tools and correct the estimated time;
  edits persist for the current detection/session.
* Wording always presents the suggestion as "AI Maintenance Recommendation ·
  Requires Human Verification" until the operator saves, after which it
  reads "Human Verified Recommendation".

---

# 24. AI AGENT MONITOR

Display the workflow in real time:

```text
● Detection Agent
  Defect identified

● Admin Agent
  Task decomposition complete

● Engineer Agent
  Repair requirements determined

● Planner Agent
  3 compatible tasks found

● Operations Agent
  Train impact calculated

● Optimization Engine
  Optimal block generated

✓ Human Approval Required
```

This is important for the hackathon demo because judges can actually see the multi-agent system working rather than being told that agents exist.

---

# 25. MAP / GEOSPATIAL SCREEN

The map should show:

* Railway corridor
* Assets
* Defective assets
* Critical assets
* Maintenance locations
* Active blocks
* Planned blocks
* Train routes where available
* Inspection locations

Example:

```text
Map
 │
 ├── Green → Healthy asset
 ├── Yellow → Maintenance required
 ├── Red → Critical defect
 └── Blue → Planned maintenance block
```

The geospatial layer is primarily for visualization and testing in the MVP.

## Basemap

The MVP renders the map on public OpenStreetMap raster tiles, and uses the same tileset in both light
and dark mode so the map imagery is identical in either theme. Only the map chrome (popups, zoom
controls, attribution text) follows the application theme.

Dark-toned third-party basemaps (CARTO, Mapbox, MapTiler and similar) are deliberately not used: the
free/no-key tiers stamp an "API key required" watermark over the tiles, which is unacceptable for a
demo. Reintroducing a dark basemap would require a licensed key and a corresponding config entry.

---

# 26. MAINTENANCE QUEUE

Columns:

```text
Task
Department
Asset
Location
Defect
Priority
Risk
Due Date
Duration
Required Block
Status
Assigned Agent
```

Tasks should be sortable by AI-generated priority.

---

# 27. CORRIDOR TIMELINE

Timeline/Gantt visualization showing:

* Train movements
* Maintenance blocks
* Department tasks
* Block windows
* Conflicts
* Downtime

Example:

```text
08:00       09:00       10:00       11:00

Train ────────────────●───────────────

Engineering       ███████

S&T                    ██████

Traction                    ██████

Optimized Block        █████████████
                       09:00–10:00
```

---

# 28. WHAT-IF SIMULATOR

Users can modify:

* Block duration
* Train traffic
* Asset criticality
* Resource availability
* Corridor availability
* Maintenance duration

The optimizer generates a new plan.

Output:

```text
CURRENT PLAN
vs
SCENARIO PLAN
```

Compare:

* Asset availability
* Block utilization
* Train impact
* Backlog
* Downtime
* Number of blocks
* Critical tasks completed

---

# 29. AGENT COMMUNICATION PROTOCOL

Agents should communicate through structured task objects rather than uncontrolled natural-language messages.

Example:

```json
{
  "task_id": "ENG-241",
  "requested_by": "admin_agent",
  "assigned_to": "engineer_agent",
  "action": "assess_repair",
  "input": {
    "defect_type": "rail_crack",
    "severity": "critical"
  }
}
```

Agent response:

```json
{
  "task_id": "ENG-241",
  "agent": "engineer_agent",
  "result": "repair_required",
  "duration": 60,
  "resources": [
    "track_crew",
    "repair_equipment"
  ],
  "block_type": "track_isolation",
  "safety": "mandatory"
}
```

This makes the system deterministic, debuggable and auditable.

---

# 30. DATABASE

## PostgreSQL

Core entities:

```text
users
assets
inspections
defects
maintenance_tasks
departments
trains
corridors
block_windows
agent_tasks
agent_results
plans
plan_versions
optimization_runs
approvals
audit_logs
model_versions
dataset_versions
```

---

# 31. BACKEND

## FastAPI

Responsibilities:

* Authentication
* Inspection upload
* Defect inference API
* Agent orchestration
* Maintenance management
* Optimization API
* Plan generation
* What-if simulation
* Approval workflow
* Audit logging

Example API structure:

```text
/api/inspection
/api/defects
/api/assets
/api/maintenance
/api/agents
/api/planning
/api/optimization
/api/plans
/api/simulation
/api/approval
/api/audit
```

---

# 32. FRONTEND

Technology:

* React
* TypeScript
* Tailwind CSS
* Recharts
* Timeline/Gantt library
* Leaflet via react-leaflet, on OpenStreetMap tiles

Primary views:

```text
Dashboard
Inspection
Defects
Maintenance Queue
Map
Agent Monitor
Timeline
Block Plans
What-If Simulator
Explainability
Audit
```

---

# 33. MACHINE LEARNING STACK

## Computer Vision

The CV layer may use an object-detection architecture appropriate to the supplied dataset.

Responsibilities:

* Defect localization
* Defect classification
* Confidence estimation

## General ML

Potential technologies:

* Python
* PyTorch
* OpenCV
* scikit-learn
* XGBoost / LightGBM
* Pandas
* NumPy

## Model Pipeline

```text
Dataset
 ↓
Preprocessing
 ↓
Train / Validation Split
 ↓
Model Training
 ↓
Evaluation
 ↓
Model Versioning
 ↓
Local Model Registry
 ↓
Inference API
```

---

# 34. STATIC DATA VS DYNAMIC DATA

The MVP explicitly separates training from operational simulation.

## Static Data

Used for model development:

```text
Kaggle
 ↓
Track Dataset
 ↓
Training

Kaggle
 ↓
Light-Pole Dataset
 ↓
Training
```

## Simulated Operational Data

Used for planning:

```text
assets.json
tasks.json
trains.json
corridors.json
block_windows.json
resources.json
```

## Geospatial Testing

```text
Selected Geographic Area
 ↓
External Geospatial Source
 ↓
Testing / Visualization
 ↓
Detection Model
```

## Future Live Data

```text
TMS
SMMS
TDMS
BDMS
COA
 ↓
Production Adapters
 ↓
RailDoc
```

This separation prevents synthetic/demo data from being represented as real railway operational data.

---

# 35. MOCK INTEGRATION LAYER

Since live railway APIs may not be available during the hackathon, RailDoc will implement mock adapters.

```text
integrations/
│
├── tms/
├── smms/
├── tdms/
├── bdms/
└── coa/
```

Each adapter exposes the same interface that a future real integration would use.

Example:

```text
Mock TMS
   ↓
TMS Adapter
   ↓
Unified Data Model
```

Later:

```text
Real TMS
   ↓
Same TMS Adapter Interface
   ↓
Unified Data Model
```

This makes the prototype integration-ready without pretending to have access to proprietary railway systems.

---

# 36. REPOSITORY STRUCTURE

```text
raildoc/
│
├── frontend/
│   └── src/
│       ├── components/
│       ├── pages/
│       ├── dashboard/
│       ├── inspection/
│       ├── agents/
│       ├── timeline/
│       ├── map/
│       └── api/
│
├── backend/
│   └── app/
│       ├── api/
│       ├── models/
│       ├── schemas/
│       ├── services/
│       │
│       ├── agents/
│       │   ├── admin/
│       │   ├── detection/
│       │   ├── engineer/
│       │   ├── planner/
│       │   └── operations/
│       │
│       ├── cv/
│       ├── optimizer/
│       ├── integrations/
│       │   ├── tms/
│       │   ├── smms/
│       │   ├── tdms/
│       │   ├── bdms/
│       │   └── coa/
│       │
│       └── main.py
│
├── RAILDOC_02.yolo26/
│
├── models/
│   └── raildoc_detection/
│
├── data/
│   ├── synthetic/
│   ├── timetable/
│   ├── corridors/
│   └── forecasts/
│
├── optimizer/
│   ├── constraints/
│   ├── objectives/
│   └── solver/
│
├── docs/
│
├── docker-compose.yml
├── .env.example
└── README.md
```

---

# 37. TECHNOLOGY STACK

## Frontend

* React
* TypeScript
* Tailwind CSS
* Recharts
* Gantt/timeline visualization
* Leaflet (OpenStreetMap tiles)

## Backend

* Python
* FastAPI

## Computer Vision

* Python
* PyTorch
* OpenCV
* Object Detection Model

## ML

* scikit-learn
* XGBoost / LightGBM
* Pandas
* NumPy

## Agent System

* Local AI models / local agent runtime
* Structured agent-to-agent communication
* Admin Agent orchestration
* Tool/function-based execution

## Optimization

* Google OR-Tools

## Database

* PostgreSQL

## Deployment

* Docker
* Docker Compose
* Localhost

---

# 38. SECURITY AND SAFETY

Because railway infrastructure is safety-sensitive:

RailDoc must:

* Keep humans in the approval loop.
* Never directly control railway signaling.
* Never issue safety-critical operational commands.
* Validate all incoming data.
* Maintain role-based authorization.
* Maintain audit logs.
* Track model versions.
* Track dataset versions.
* Track plan versions.
* Record every approval/modification.
* Prevent agents from bypassing hard safety constraints.

---

# 39. PERFORMANCE METRICS

## Computer Vision

* Precision
* Recall
* F1-score
* mAP
* Detection confidence
* False-positive rate

## Maintenance

* Defect-to-maintenance time
* Critical defect completion
* Maintenance backlog
* Average downtime

## Planning

* Asset availability
* Block utilization
* Number of blocks
* Separate blocks avoided
* Multi-department blocks
* Train disruption minutes
* Train conflicts
* Unused block capacity

---

# 40. BEFORE VS AFTER DEMONSTRATION

The hackathon demonstration should compare conventional planning against RailDoc.

## Before

```text
Engineering Block
09:00–10:00

S&T Block
09:30–10:30

Traction Block
10:00–11:00

Total:
3 blocks
High downtime
Multiple operational conflicts
```

## RailDoc

```text
RailDoc detects compatibility

Engineering
      +
S&T
      +
Traction
      ↓
One optimized block
09:30–10:30
```

Example simulated result:

```text
                    BEFORE       AFTER

Blocks                 3           1
Downtime             135 min      60 min
Train Conflicts         6           1
Tasks Completed         3           3+
Utilization            52%         96%
```

These values must be clearly labelled as **simulation/demo metrics**, not real railway performance claims.

---

# 41. DEMONSTRATION SCENARIO

The complete demo should tell one story.

## Phase 1 — Train the AI

```text
Kaggle Track Dataset
       ↓
Train Detection Model
       ↓
Validation
       ↓
Model Ready
```

## Phase 2 — Detect Defect

Inspector uploads a track image.

```text
Image
 ↓
Detection Agent
 ↓
Rail Crack
 ↓
Bounding Box
 ↓
94% Confidence
 ↓
Critical
```

## Phase 3 — Admin Agent

```text
Admin Agent receives:

Critical track defect
Corridor C-07
KM 241.7
```

It creates subtasks.

## Phase 4 — Agent Collaboration

```text
Engineer Agent
→ 60-minute repair
→ Track isolation

Planner Agent
→ Finds 2 compatible maintenance tasks

Operations Agent
→ Identifies 1 freight conflict

Admin Agent
→ Builds candidate plans
```

## Phase 5 — Optimization

```text
Candidate Plans
      ↓
Utility Evaluation
      ↓
OR-Tools
      ↓
Optimal Block
```

## Phase 6 — Explainability

```text
Why this block?

✓ Critical defect
✓ Low train impact
✓ 2 compatible tasks
✓ Same corridor
✓ Safety constraints satisfied
✓ 96% block utilization
```

## Phase 7 — Human Approval

```text
[ APPROVE ]

[ MODIFY ]

[ REJECT ]
```

## Phase 8 — Final Output

```text
BLOCK C-07-021

02:00–03:00

Engineering
• Rail repair

S&T
• Signal inspection

Traction
• OHE inspection

Train Impact:
1 freight movement adjusted

Utilization:
96%

Status:
Awaiting Human Approval
```

---

# 42. WHAT THE SYSTEM DOES NOT CLAIM

The MVP does **not** claim:

* Real-time railway control.
* Certified railway safety.
* Direct signaling control.
* Direct access to proprietary railway databases.
* Perfect defect detection.
* Satellite imagery equivalent to inspection-grade imagery.
* Real-world railway performance based on synthetic data.
* Fully autonomous railway maintenance decisions.

It is a prototype decision-support system.

---

# 43. MVP PRIORITY

## P0 — Mandatory

### Computer Vision

* Track dataset ingestion
* Track defect detection
* Defect localization
* Defect classification
* Confidence/severity
* Inspection upload

### AI Agents

* Admin Agent
* Detection Agent
* Engineer Agent
* Planner Agent
* Operations Agent

### Planning

* Unified data model
* Priority engine
* OR-Tools optimizer
* Block generation
* Cross-department coordination
* Explainability

### UI

* Dashboard
* Defect screen
* Agent monitor
* Maintenance queue
* Block plan
* Timeline

### Integration

* Local dataset integration
* Mock TMS
* Mock SMMS
* Mock TDMS
* Mock BDMS
* Mock COA
* Geospatial visualization/testing

---

# 44. P1 — Important

* Light-pole defect detection
* What-if simulator
* Weekly planning
* Monthly planning
* Dynamic replanning
* Advanced geospatial visualization
* Approval workflow
* Audit history
* Model/version tracking

---

# 45. P2 — Future

* Live railway integrations
* Advanced failure prediction
* Historical learning loop
* Real-time inspection feeds
* Real railway GIS integration
* Advanced forecasting
* Cloud deployment
* Role-specific dashboards
* Predictive maintenance
* Automated resource optimization

---

# 46. PRODUCT DIFFERENTIATION

RailDoc should not be presented as simply:

> “An AI that detects railway defects.”

That is too narrow.

The real system is:

```text
DETECT
   ↓
UNDERSTAND
   ↓
PRIORITIZE
   ↓
DECOMPOSE
   ↓
COORDINATE
   ↓
OPTIMIZE
   ↓
EXPLAIN
   ↓
APPROVE
```

The five core technical pillars are:

1. **Computer Vision-based asset inspection**
2. **Multi-agent maintenance coordination**
3. **Constraint-based block optimization**
4. **Multi-department maintenance planning**
5. **Explainable, human-approved decision making**

---

# 47. FINAL SYSTEM ARCHITECTURE

```text
                       ┌──────────────────────┐
                       │   INSPECTOR / USER   │
                       └──────────┬───────────┘
                                  │
                            Upload Image
                                  ↓
                 ┌────────────────────────────┐
                 │     DETECTION AGENT        │
                 │                            │
                 │ Computer Vision            │
                 │ Object Detection           │
                 │ Defect Classification      │
                 └─────────────┬──────────────┘
                               │
                         Defect Ticket
                               ↓
                 ┌────────────────────────────┐
                 │       ADMIN AGENT          │
                 │    Master Orchestrator     │
                 └─────────────┬──────────────┘
                               │
              ┌────────────────┼────────────────┐
              ↓                ↓                ↓
      ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
      │ ENGINEER     │ │ PLANNER      │ │ OPERATIONS   │
      │ AGENT        │ │ AGENT        │ │ AGENT        │
      │              │ │              │ │              │
      │ Repair       │ │ Compatible   │ │ Train impact │
      │ Resources    │ │ tasks        │ │ Blocks       │
      │ Safety       │ │ Scheduling   │ │ Conflicts    │
      └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
             │                │                │
             └────────────────┼────────────────┘
                              ↓
                    ┌────────────────────┐
                    │   UTILITY ENGINE   │
                    └─────────┬──────────┘
                              ↓
                    ┌────────────────────┐
                    │    GOOGLE          │
                    │    OR-TOOLS        │
                    │                    │
                    │ Constraint Solver  │
                    └─────────┬──────────┘
                              ↓
                    ┌────────────────────┐
                    │ OPTIMIZED BLOCK    │
                    │ PLAN               │
                    └─────────┬──────────┘
                              ↓
                    ┌────────────────────┐
                    │ EXPLAINABILITY     │
                    │ ENGINE             │
                    └─────────┬──────────┘
                              ↓
                    ┌────────────────────┐
                    │ HUMAN APPROVAL     │
                    └─────────┬──────────┘
                              ↓
                    ┌────────────────────┐
                    │ FINAL MAINTENANCE  │
                    │ PLAN               │
                    └────────────────────┘


DATA / INTEGRATIONS
────────────────────────────────────────────────────

Kaggle Track Dataset ────────┐
Kaggle Light-Pole Dataset ────┤
                             ↓
                      ML Training Layer
                             ↓
                       Local AI Models


TMS ─────┐
SMMS ────┤
TDMS ────┤──→ Mock/Real Adapters ──→ Unified Data Model
BDMS ────┤
COA ─────┘


Geospatial Source
      ↓
Selected Area / Imagery
      ↓
Testing + Visualization
      ↓
RailDoc


All Data
   ↓
PostgreSQL
   ↓
Audit + History + Model/Plan Versions
```

---

# 48. NORTH STAR

> **RailDoc transforms a detected railway defect into an optimized, explainable and human-approved maintenance action by combining computer vision, multi-agent AI and mathematical optimization.**

The key architecture is:

> **Detection Agent finds the problem. Admin Agent coordinates the response. Engineer Agent understands the repair. Planner Agent finds compatible work. Operations Agent protects train movement. Utility Engine evaluates alternatives. OR-Tools finds the feasible optimum. Humans approve the final plan.**

---

# 49. FUTURE SCOPE

The capabilities below are explicitly out of scope for the MVP and define the post-hackathon roadmap.

## 49.1 Live Railway Integrations

* Replace the mock adapter layer (§35) with real TMS / SMMS / TDMS / BDMS / COA connectors behind the same adapter interfaces.
* Live timetable feeds for train-conflict evaluation and automatic replanning triggers (§18).
* Production-grade authentication against a railway identity provider instead of local mock users.

## 49.2 Machine Learning

* ML-learned priority weights (§17) trained on historical maintenance outcomes instead of hand-tuned defaults.
* Failure-prediction models per asset class using `historical_failure_rate`, inspection history and environmental data.
* Detection-model expansion: additional defect classes (signalling, OHE, weld defects), segmentation masks, drone/inspection-camera imagery, and higher-resolution inputs.
* Active-learning loop: inspector corrections on false detections feed the next training cycle.
* Automated model / dataset / plan version registry (§20, §38) with regression gates on mAP.

## 49.3 Planning Depth

* Multi-week and monthly planning horizons with rolling replans (§44).
* Crew rostering, skill matching and resource leveling layered on top of block optimization.
* Stochastic train-delay modelling and weather disruption in the What-If simulator (§28).
* Depot and relief-maintenance scheduling beyond corridor blocks.

## 49.4 Platform & Scale

Already implemented in the MVP (single process):

* **Bounded concurrency** (the in-process GIL mitigation): CPU-heavy work — YOLO inference, OR-Tools solves, agent orchestration — runs on a bounded pool (`backend/app/core/pools.py`, sized by `HEAVY_POOL_SIZE`, default ≈ cores/4) instead of unbounded thread fan-out; blocking DB calls from `async def` endpoints run on a wider I/O pool (`IO_POOL_SIZE`). Excess heavy jobs **queue** rather than stacking dozens of GIL-fighting threads, so the event loop keeps serving reads while a solve runs. Measured effect under the 20-client stress harness: 0% 5xx and overall p95 roughly halved (≈19 s → ≈9 s). This mitigates contention *within one process only* — it does not replace multi-worker deployment.
* **Latency caches:** `/api/health` caches its DB verdict for `HEALTH_CACHE_TTL` seconds (default 15) so probes do not each pay a full Supabase round trip; the audit API parses each log file once and re-parses only on change (mtime/size), with the directory configurable via `AUDIT_LOG_DIR`.
* **CI pipeline** (`.github/workflows/ci.yml`): backend test suite with coverage artifact, dataset validator, frontend build, and a **load-smoke job** that boots the API and runs `scripts/stress_load.py` against it (per-operation latency report uploaded as an artifact; the job fails when 5xx + transport errors exceed 1% of non-429 traffic).

Still open (post-MVP):

* Multi-worker / multi-host deployment: move rate-limit buckets, the plan-write lock and the heavy-job queue to a shared store (Redis) — the current implementation is deliberately single-process, and queued heavy work is lost on process restart.
* Refresh-token rotation, OAuth2/OIDC single sign-on, and managed secret storage.
* Observability: request tracing, solver telemetry, alerting on 5xx budgets, and per-operation p95 latency tracking.

## 49.5 Field & Geospatial

* Offline-first mobile inspection app for field inspectors with deferred sync.
* Real GIS corridor geometry and surveyed asset coordinates replacing the KM-marker projection (§25).
* Satellite / geospatial change detection as a secondary detection source (§14), clearly separated from inspection-grade imagery.

## 49.6 Reporting & Governance

* Audit-log export to SIEM / security tooling.
* Role-specific dashboards (§45) and scheduled report generation.
* Plan-version diff views comparing approved vs. regenerated plans.
* Compliance reporting against railway maintenance regulations.