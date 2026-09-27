export interface Asset {
  asset_id: string;
  department: string;
  asset_type: string;
  corridor_id: string;
  location: string;
  criticality: number;
  current_status: string;
  availability: number;
  historical_failure_rate: number;
}

export interface MaintenanceTask {
  task_id: string;
  asset_id: string;
  department: string;
  task_type: string;
  priority_score: number;
  criticality: number;
  failure_risk: number;
  days_overdue: number;
  safety_criticality: number;
  train_impact: number;
  due_date: string;
  estimated_duration_minutes: number;
  required_block_type: string;
  required_resources: string[];
  safety_requirements: string[];
  isolation_required: boolean;
  dependencies: string[];
  corridor_id: string;
  location: string;
  status: string;
  assigned_block_id: string | null;
  explanation: string;
}

export interface Train {
  train_id: string;
  train_type: string;
  route: string;
  corridor_id: string;
  scheduled_time: string;
  priority: number;
  direction: string;
}

export interface BlockWindow {
  window_id: string;
  corridor_id: string;
  start_time: string;
  end_time: string;
  block_type: string;
  day_of_week: number;
}

export interface MaintenanceBlock {
  block_id: string;
  corridor_id: string;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  block_type: string;
  assigned_tasks: string[];
  departments: string[];
  utilization: number;
  train_impact: number;
  status: string;
  explanation: string;
}

export interface PlanMetrics {
  asset_availability: number;
  maintenance_backlog: number;
  planned_blocks: number;
  train_conflicts: number;
  train_disruption_minutes: number;
  block_utilization: number;
  multi_dept_blocks: number;
  critical_tasks_completed: number;
  total_tasks: number;
  separate_blocks_avoided: number;
  total_downtime_minutes: number;
}

export interface Detection {
  label: string;
  confidence: number;
  bbox: [number, number, number, number];
  severity: string;
  defect_type: string;
  asset_type: string;
  /** Set by the UI for bbox % positioning; not sent to the backend. */
  natural_width?: number;
  natural_height?: number;
}

export interface InspectionAnalysis {
  analysis_id: string;
  asset_type: string;
  is_defective: boolean;
  detections: Detection[];
  annotated_image_b64: string | null;
  model_info: { kind?: string; model_available?: boolean };
  inference_ms: number;
}

export interface WorkflowCandidate {
  plan_id: string;
  strategy: string;
  block_start_min: number;
  block_end_min: number;
  task_ids: string[];
  departments: string[];
  operational_impact: string;
  freight_conflicts: number;
  passenger_conflicts: number;
  utilization: number;
  utility: number;
  explanation: string;
}

export interface WorkflowEvent {
  seq: number;
  agent: string;
  message: string;
  status: string;
  task_id: string | null;
  at: number;
}

export interface AgentWorkflow {
  workflow_id: string;
  ticket_id: string;
  log: WorkflowEvent[];
  engineer: Record<string, unknown>;
  planner: { compatible_tasks: unknown[]; departments_involved: string[]; coordinated_block_minutes: number; corridor_id: string };
  candidates: WorkflowCandidate[];
  selected: WorkflowCandidate | null;
  tasks_created: string[];
}

export interface DashboardData {
  asset_availability: number;
  total_assets: number;
  degraded_assets: number;
  maintenance_assets: number;
  maintenance_backlog: number;
  planned_blocks: number;
  block_utilization: number;
  train_conflicts: number;
  train_disruption_minutes: number;
  priority_distribution: {
    critical: number;
    high: number;
    medium: number;
    low: number;
    total: number;
  };
  recommendations: string[];
  total_tasks: number;
  scheduled_tasks: number;
  multi_dept_blocks: number;
}

export interface TaskExplanation {
  task_id: string;
  priority_score: number;
  criticality: number;
  failure_risk: number;
  days_overdue: number;
  train_impact: number;
  safety_criticality: number;
  corridor_id: string;
  assigned_block: string | null;
  block_start: string | null;
  block_end: string | null;
  compatible_tasks: number;
  reason: string;
  if_moved: string;
}

export interface BeforeAfter {
  before: {
    total_blocks: number;
    total_downtime_minutes: number;
    train_conflicts: number;
    asset_availability: number;
    multi_dept_blocks: number;
    block_utilization: number;
    separate_blocks_avoided: number;
  };
  after: PlanMetrics;
  improvements: {
    blocks_reduction: number;
    downtime_reduction: number;
    conflicts_reduction: number;
    multi_dept_blocks: number;
  };
}

export interface PriorityWeights {
  asset_criticality: number;
  failure_risk: number;
  overdue_factor: number;
  train_impact: number;
  safety_criticality: number;
}

export interface AuthUser {
  username: string;
  roles: string[];
  is_active: boolean;
  created_at: string;
}

export interface AuthState {
  user: AuthUser | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}
