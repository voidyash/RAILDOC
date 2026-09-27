-- RailDoc — Supabase Schema
-- Run this against your Supabase PostgreSQL database

-- Departments
CREATE TABLE IF NOT EXISTS departments (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

INSERT INTO departments (name) VALUES
    ('Engineering'), ('S&T'), ('Traction')
ON CONFLICT (name) DO NOTHING;

-- Corridors
CREATE TABLE IF NOT EXISTS corridors (
    corridor_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    section TEXT NOT NULL,
    capacity INT DEFAULT 2,
    restrictions TEXT[] DEFAULT '{}'
);

-- Assets
CREATE TABLE IF NOT EXISTS assets (
    asset_id TEXT PRIMARY KEY,
    department TEXT NOT NULL REFERENCES departments(name),
    asset_type TEXT NOT NULL,
    corridor_id TEXT NOT NULL REFERENCES corridors(corridor_id),
    location TEXT NOT NULL,
    criticality FLOAT NOT NULL DEFAULT 50.0,
    current_status TEXT NOT NULL DEFAULT 'Operational',
    availability FLOAT NOT NULL DEFAULT 100.0,
    historical_failure_rate FLOAT NOT NULL DEFAULT 0.0
);

-- Maintenance Tasks
CREATE TABLE IF NOT EXISTS maintenance_tasks (
    task_id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL REFERENCES assets(asset_id),
    department TEXT NOT NULL REFERENCES departments(name),
    task_type TEXT NOT NULL,
    priority_score FLOAT NOT NULL DEFAULT 0.0,
    criticality FLOAT NOT NULL DEFAULT 50.0,
    failure_risk FLOAT NOT NULL DEFAULT 50.0,
    days_overdue INT NOT NULL DEFAULT 0,
    safety_criticality FLOAT NOT NULL DEFAULT 50.0,
    train_impact FLOAT NOT NULL DEFAULT 50.0,
    due_date DATE NOT NULL,
    estimated_duration_minutes INT NOT NULL DEFAULT 60,
    required_block_type TEXT NOT NULL DEFAULT 'Block',
    required_resources TEXT[] DEFAULT '{}',
    safety_requirements TEXT[] DEFAULT '{}',
    isolation_required BOOLEAN NOT NULL DEFAULT FALSE,
    dependencies TEXT[] DEFAULT '{}',
    corridor_id TEXT NOT NULL REFERENCES corridors(corridor_id),
    location TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending',
    assigned_block_id TEXT,
    explanation TEXT DEFAULT ''
);

-- Trains
CREATE TABLE IF NOT EXISTS trains (
    train_id TEXT PRIMARY KEY,
    train_type TEXT NOT NULL,
    route TEXT NOT NULL,
    corridor_id TEXT NOT NULL REFERENCES corridors(corridor_id),
    scheduled_time TEXT NOT NULL,
    priority INT NOT NULL DEFAULT 1,
    direction TEXT NOT NULL DEFAULT 'Up'
);

-- Block Windows
CREATE TABLE IF NOT EXISTS block_windows (
    window_id TEXT PRIMARY KEY,
    corridor_id TEXT NOT NULL REFERENCES corridors(corridor_id),
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    block_type TEXT NOT NULL DEFAULT 'Block',
    day_of_week INT NOT NULL DEFAULT 0
);

-- Maintenance Blocks
CREATE TABLE IF NOT EXISTS maintenance_blocks (
    block_id TEXT PRIMARY KEY,
    corridor_id TEXT NOT NULL REFERENCES corridors(corridor_id),
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    duration_minutes INT NOT NULL DEFAULT 0,
    block_type TEXT NOT NULL DEFAULT 'Block',
    utilization FLOAT NOT NULL DEFAULT 0.0,
    train_impact FLOAT NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'Proposed',
    explanation TEXT DEFAULT ''
);

-- Block ↔ Task assignment (many-to-many)
CREATE TABLE IF NOT EXISTS block_task_assignments (
    block_id TEXT NOT NULL REFERENCES maintenance_blocks(block_id),
    task_id TEXT NOT NULL REFERENCES maintenance_tasks(task_id),
    PRIMARY KEY (block_id, task_id)
);

-- Block ↔ Department assignment (many-to-many)
CREATE TABLE IF NOT EXISTS block_departments (
    block_id TEXT NOT NULL REFERENCES maintenance_blocks(block_id),
    department TEXT NOT NULL REFERENCES departments(name),
    PRIMARY KEY (block_id, department)
);

-- Plans
CREATE TABLE IF NOT EXISTS plans (
    plan_id TEXT PRIMARY KEY,
    plan_type TEXT NOT NULL,
    week_number INT NOT NULL,
    corridor_id TEXT NOT NULL REFERENCES corridors(corridor_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status TEXT NOT NULL DEFAULT 'Draft',
    approved_by TEXT,
    metrics JSONB DEFAULT '{}'
);

-- Plan ↔ Block assignment
CREATE TABLE IF NOT EXISTS plan_blocks (
    plan_id TEXT NOT NULL REFERENCES plans(plan_id),
    block_id TEXT NOT NULL REFERENCES maintenance_blocks(block_id),
    PRIMARY KEY (plan_id, block_id)
);

-- Priority Weights (singleton config)
CREATE TABLE IF NOT EXISTS priority_weights (
    id INT PRIMARY KEY DEFAULT 1,
    asset_criticality FLOAT NOT NULL DEFAULT 0.30,
    failure_risk FLOAT NOT NULL DEFAULT 0.25,
    overdue_factor FLOAT NOT NULL DEFAULT 0.20,
    train_impact FLOAT NOT NULL DEFAULT 0.15,
    safety_criticality FLOAT NOT NULL DEFAULT 0.10,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO priority_weights (id) VALUES (1)
ON CONFLICT (id) DO NOTHING;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_tasks_corridor ON maintenance_tasks(corridor_id);
CREATE INDEX IF NOT EXISTS idx_tasks_department ON maintenance_tasks(department);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON maintenance_tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON maintenance_tasks(priority_score DESC);
CREATE INDEX IF NOT EXISTS idx_assets_corridor ON assets(corridor_id);
CREATE INDEX IF NOT EXISTS idx_trains_corridor ON trains(corridor_id);
CREATE INDEX IF NOT EXISTS idx_blocks_corridor ON maintenance_blocks(corridor_id);
CREATE INDEX IF NOT EXISTS idx_block_assignments_task ON block_task_assignments(task_id);
