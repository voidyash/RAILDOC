import axios from 'axios';
import type {
  Asset, MaintenanceTask, Train, BlockWindow,
  MaintenanceBlock, PlanMetrics, DashboardData,
  TaskExplanation, BeforeAfter, PriorityWeights,
  AuthUser, Detection, AgentWorkflow
} from '../types';

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
});

let _accessToken: string | null = null;
let _refreshToken: string | null = null;

export function setAuthTokens(access: string | null, refresh: string | null) {
  _accessToken = access;
  _refreshToken = refresh;
  if (access) {
    localStorage.setItem('abp_access_token', access);
    localStorage.setItem('abp_refresh_token', refresh ?? '');
  } else {
    localStorage.removeItem('abp_access_token');
    localStorage.removeItem('abp_refresh_token');
  }
}

export function loadAuthTokens(): { accessToken: string | null; refreshToken: string | null } {
  if (_accessToken) return { accessToken: _accessToken, refreshToken: _refreshToken };
  const access = localStorage.getItem('abp_access_token');
  const refresh = localStorage.getItem('abp_refresh_token');
  _accessToken = access;
  _refreshToken = refresh;
  return { accessToken: access, refreshToken: refresh };
}

export function clearAuthTokens() {
  setAuthTokens(null, null);
}

api.interceptors.request.use((config) => {
  if (_accessToken) {
    config.headers.Authorization = `Bearer ${_accessToken}`;
  }
  return config;
});

// Shared in-flight refresh: when a burst of parallel requests (the dashboard
// fires ~7 at once) all 401 on the same expired token, every caller awaits the
// SAME refresh promise and then retries — instead of all but one being
// rejected, which left the dashboard permanently empty.
let _refreshPromise: Promise<string | null> | null = null;

function refreshAccessToken(): Promise<string | null> {
  if (!_refreshToken) return Promise.resolve(null);
  if (!_refreshPromise) {
    _refreshPromise = axios
      .post('/api/auth/refresh', { refresh_token: _refreshToken }, { timeout: 15000 })
      .then((resp) => {
        const { access_token, refresh_token } = resp.data;
        setAuthTokens(access_token, refresh_token);
        return access_token as string;
      })
      .catch(() => {
        clearAuthTokens();
        return null;
      })
      .finally(() => {
        _refreshPromise = null;
      });
  }
  return _refreshPromise;
}

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err.config;
    const url: string = original?.url ?? '';
    const isAuthCall = url.includes('/auth/login') || url.includes('/auth/refresh');
    if (err.response?.status === 401 && !isAuthCall && original && !original._retry) {
      original._retry = true;
      const newToken = await refreshAccessToken();
      if (newToken) {
        original.headers.Authorization = `Bearer ${newToken}`;
        return api(original);
      }
    }
    return Promise.reject(err);
  }
);

export const login = (username: string, password: string): Promise<{
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}> =>
  api.post('/auth/login', { username, password }).then(r => r.data);

export const refreshToken = (token: string): Promise<{
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}> =>
  api.post('/auth/refresh', { refresh_token: token }).then(r => r.data);

export const getCurrentUser = (): Promise<AuthUser> =>
  api.get('/auth/me').then(r => r.data);

export const getAssets = (): Promise<Asset[]> =>
  api.get('/data/assets').then(r => r.data);

export const getTasks = (): Promise<MaintenanceTask[]> =>
  api.get('/data/tasks').then(r => r.data);

export const getTrains = (): Promise<Train[]> =>
  api.get('/data/trains').then(r => r.data);

export const getCorridors = (): Promise<any[]> =>
  api.get('/data/corridors').then(r => r.data);

export const getBlockWindows = (): Promise<BlockWindow[]> =>
  api.get('/data/block-windows').then(r => r.data);

export const regenerateData = (): Promise<any> =>
  api.post('/data/regenerate').then(r => r.data);

export const getPriorityWeights = (): Promise<PriorityWeights> =>
  api.get('/priority/weights').then(r => r.data);

export const updatePriorityWeights = (weights: Partial<PriorityWeights>): Promise<any> =>
  api.put('/priority/weights', weights).then(r => r.data);

export const calculatePriorities = (): Promise<any> =>
  api.get('/priority/calculate').then(r => r.data);

export const runOptimizer = (scenario?: any): Promise<{
  blocks: MaintenanceBlock[];
  metrics: PlanMetrics;
  assigned_tasks: number;
  total_tasks: number;
}> => api.post('/optimize', scenario || null, { timeout: 60000 }).then(r => r.data);

export const getCurrentPlan = (): Promise<{
  blocks: MaintenanceBlock[];
  metrics: PlanMetrics | null;
  total_tasks: number;
  assigned_tasks: number;
}> => api.get('/plans/current').then(r => r.data);

export const approvePlan = (blockIds?: string[]): Promise<{ message: string; plan_id: string; approved_blocks: string[] }> =>
  api.post('/plans/approve', blockIds ? { block_ids: blockIds } : {}).then(r => r.data);

export const revertPlan = (planId: string, blockIds?: string[]): Promise<any> =>
  api.post('/plans/revert', { plan_id: planId, block_ids: blockIds ?? [] }).then(r => r.data);

export const explainTask = (taskId: string): Promise<TaskExplanation> =>
  api.get(`/explain/task/${taskId}`).then(r => r.data);

export const explainBlock = (blockId: string): Promise<any> =>
  api.get(`/explain/block/${blockId}`).then(r => r.data);

export const runSimulation = (scenario: any): Promise<any> =>
  api.post('/simulate', scenario).then(r => r.data);

export const getBeforeAfter = (): Promise<BeforeAfter> =>
  api.get('/comparison/before-after').then(r => r.data);

export const getDashboard = (): Promise<DashboardData> =>
  api.get('/dashboard').then(r => r.data);

export const healthCheck = (): Promise<any> =>
  api.get('/health').then(r => r.data);

export const listUsers = (): Promise<AuthUser[]> =>
  api.get('/auth/users').then(r => r.data);

// ─── Inspection / Detection Agent ────────────────────────────────────

export interface InspectionAnalysis {
  analysis_id: string;
  asset_type: string;
  is_defective: boolean;
  detections: Detection[];
  annotated_image_b64: string | null;
  model_info: { kind?: string; model_available?: boolean };
  inference_ms: number;
}

export const analyzeImage = (
  file: File,
  assetType: string,
  draw = true
): Promise<InspectionAnalysis> => {
  const form = new FormData();
  form.append('file', file);
  form.append('asset_type', assetType);
  form.append('draw', String(draw));
  return api.post('/inspection/analyze', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  }).then(r => r.data);
};

export const createTicket = (
  detection: Detection,
  corridorId: string,
  location: string,
  assetId?: string
): Promise<{ ticket_id: string; task: MaintenanceTask }> =>
  api.post('/inspection/ticket', {
    detection,
    corridor_id: corridorId,
    location,
    asset_id: assetId,
  }).then(r => r.data);

export const runWorkflow = (
  ticketId: string,
  detection: Detection,
  corridorId: string,
  location: string
): Promise<AgentWorkflow> =>
  api.post('/inspection/workflow', {
    ticket: {
      task_id: ticketId,
      detection,
      corridor_id: corridorId,
      location,
    },
  }, { timeout: 120000 }).then(r => r.data);

export const getModelStatus = (): Promise<Record<string, {
  available: boolean;
  kind?: string;
  weights_dir: string;
  error: string | null;
}>> => api.get('/inspection/models').then(r => r.data);

export const commitWorkflow = (
  workflowId: string,
  decision: 'approve' | 'reject'
): Promise<{
  message: string;
  workflow_id: string;
  block_id?: string;
  scheduled_tasks?: string[];
  decided_by?: string;
}> =>
  api.post(`/inspection/workflow/${workflowId}/commit`, { decision }, { timeout: 60000 }).then(r => r.data);

// ─── Model Info / Replanning ─────────────────────────────────────────

export interface ModelTrainingInfo {
  weights_dir: string;
  task: string;
  epochs_trained?: number;
  best_epoch?: number;
  metrics?: Record<string, number | null>;
  config?: Record<string, unknown>;
  artifacts?: { results_png: boolean; confusion_matrix: boolean; val_predictions: boolean };
  available?: boolean;
}

export const getModelInfo = (): Promise<Record<string, {
  available: boolean;
  weights_dir: string;
  error: string | null;
} & { training?: ModelTrainingInfo }>> =>
  api.get('/inspection/models').then(r => r.data);

export interface SamplePrediction {
  asset_type: string;
  source: string;
  is_defective?: boolean;
  detections?: Array<{ defect_type: string; confidence: number; bbox: number[]; severity: string }>;
  annotated_image_b64?: string | null;
  error?: string;
}

export const getSamplePredictions = (): Promise<{ samples: SamplePrediction[] }> =>
  api.get('/inspection/samples', { timeout: 120000 }).then(r => r.data);

export const runReplan = (reason: string): Promise<{
  message: string;
  reason: string;
  metrics: PlanMetrics;
  tasks_scheduled: number;
  total_tasks: number;
}> => api.post('/inspection/replan', { reason }, { timeout: 120000 }).then(r => r.data);

export const createUser = (data: {
  username: string;
  password: string;
  roles: string[];
}): Promise<AuthUser> =>
  api.post('/auth/users', data).then(r => r.data);

export interface AuditEntry {
  timestamp: string;
  event_type: string;
  username: string;
  client_ip: string;
  resource_type?: string;
  resource_id?: string;
  action?: string;
  details?: Record<string, any>;
  status: string;
  error_message?: string;
}

export const getAuditLogs = (filters: {
  event_type?: string;
  username?: string;
  status?: string;
  date?: string;
  limit?: number;
} = {}): Promise<{ entries: AuditEntry[]; total: number }> =>
  api.get('/audit/logs', { params: filters }).then(r => r.data);

export const getAuditEventTypes = (): Promise<{ event_types: string[] }> =>
  api.get('/audit/event-types').then(r => r.data);

export const getAuditStats = (filters: { date?: string } = {}): Promise<{
  total: number;
  event_counts: Record<string, number>;
  user_counts: Record<string, number>;
  status_counts: Record<string, number>;
}> => api.get('/audit/stats', { params: filters }).then(r => r.data);
