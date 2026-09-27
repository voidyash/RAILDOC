import { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import axios from 'axios';
import * as api from './client';
import type {
  Asset, MaintenanceTask, Train, BlockWindow,
  MaintenanceBlock, DashboardData, BeforeAfter
} from '../types';

export interface OptimizeProgress {
  step: number;
  totalSteps: number;
  label: string;
  status: 'pending' | 'active' | 'done' | 'error';
}

interface DataContextType {
  assets: Asset[];
  tasks: MaintenanceTask[];
  trains: Train[];
  corridors: any[];
  blockWindows: BlockWindow[];
  blocks: MaintenanceBlock[];
  dashboard: DashboardData | null;
  comparison: BeforeAfter | null;
  loading: boolean;
  loadError: string | null;
  optimizing: boolean;
  optimizeProgress: OptimizeProgress[];
  refresh: () => Promise<void>;
  runOptimize: () => Promise<void>;
}

const DataContext = createContext<DataContextType | null>(null);

/** Progress steps shown while the optimizer runs (module-level constant —
 *  stable identity, safe as a useCallback dependency). */
const OPTIMIZE_STEPS = [
  'Calculating task priorities',
  'Running block optimizer',
  'Persisting blocks to database',
  'Updating task statuses',
  'Loading updated dashboard',
];

export function DataProvider({ children }: { children: React.ReactNode }) {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [tasks, setTasks] = useState<MaintenanceTask[]>([]);
  const [trains, setTrains] = useState<Train[]>([]);
  const [corridors, setCorridors] = useState<any[]>([]);
  const [blockWindows, setBlockWindows] = useState<BlockWindow[]>([]);
  const [blocks, setBlocks] = useState<MaintenanceBlock[]>([]);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [comparison, setComparison] = useState<BeforeAfter | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [optimizing, setOptimizing] = useState(false);
  const [optimizeProgress, setOptimizeProgress] = useState<OptimizeProgress[]>([]);
  const loaded = useRef(false);

  const loadBaseData = useCallback(async () => {
    try {
      const [a, t, tr, c, w] = await Promise.all([
        api.getAssets(),
        api.getTasks(),
        api.getTrains(),
        api.getCorridors(),
        api.getBlockWindows(),
      ]);
      setAssets(a);
      setTasks(t);
      setTrains(tr);
      setCorridors(c);
      setBlockWindows(w);
      return { tasks: t };
    } catch (err) {
      console.error('Failed to load base data:', err);
      setLoadError(
        axios.isAxiosError(err)
          ? `Server error ${err.response?.status ?? ''}: ${err.response?.statusText ?? 'request failed'}`
          : 'Could not reach the server'
      );
      return { tasks: [] };
    }
  }, []);

  const loadPlanData = useCallback(async () => {
    try {
      const [plan, dash] = await Promise.all([
        api.getCurrentPlan(),
        api.getDashboard(),
      ]);
      setBlocks(plan.blocks);
      setDashboard(dash);
      setLoadError(null);
    } catch (err) {
      console.error('Failed to load plan data:', err);
      setLoadError(
        axios.isAxiosError(err)
          ? `Server error ${err.response?.status ?? ''}: ${err.response?.statusText ?? 'request failed'}`
          : 'Could not reach the server'
      );
    }
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    await loadBaseData();
    await loadPlanData();
    setLoading(false);
  }, [loadBaseData, loadPlanData]);

  const runOptimize = useCallback(async () => {
    setOptimizing(true);
    setOptimizeProgress(
      OPTIMIZE_STEPS.map((label, i) => ({
        step: i + 1,
        totalSteps: OPTIMIZE_STEPS.length,
        label,
        status: i === 0 ? 'active' : 'pending',
      }))
    );
    try {
      setOptimizeProgress((prev) =>
        prev.map((s, i) => (i === 0 ? { ...s, status: 'done' } : i === 1 ? { ...s, status: 'active' } : s))
      );
      await api.runOptimizer();

      setOptimizeProgress((prev) =>
        prev.map((s, i) => (i === 1 ? { ...s, status: 'done' } : i === 2 ? { ...s, status: 'active' } : s))
      );

      setOptimizeProgress((prev) =>
        prev.map((s, i) => (i === 2 ? { ...s, status: 'done' } : i === 3 ? { ...s, status: 'active' } : s))
      );
      const updatedTasks = await api.getTasks();
      setTasks(updatedTasks);

      setOptimizeProgress((prev) =>
        prev.map((s, i) => (i === 3 ? { ...s, status: 'done' } : i === 4 ? { ...s, status: 'active' } : s))
      );
      const [dash, plan] = await Promise.all([
        api.getDashboard(),
        api.getCurrentPlan(),
      ]);
      setDashboard(dash);
      setBlocks(plan.blocks);

      setOptimizeProgress((prev) => prev.map((s) => ({ ...s, status: 'done' as const })));

      api.getBeforeAfter().then(setComparison).catch(() => {});
    } catch (err) {
      console.error('Optimization failed:', err);
      setOptimizeProgress((prev) =>
        prev.map((s) => (s.status === 'active' ? { ...s, status: 'error' } : s))
      );
    } finally {
      setOptimizing(false);
    }
    // No reactive deps: OPTIMIZE_STEPS is a stable module-level constant
    // (oxlint's exhaustive-deps heuristic false-positives on it either way).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (loaded.current) return;
    loaded.current = true;

    (async () => {
      setLoading(true);
      await loadBaseData();
      await loadPlanData();
      setLoading(false);

      api.getBeforeAfter().then(setComparison).catch(() => {});
    })();
  }, [loadBaseData, loadPlanData]);

  return (
    <DataContext.Provider value={{
      assets, tasks, trains, corridors, blockWindows,
      blocks, dashboard, comparison,
      loading, loadError, optimizing, optimizeProgress, refresh, runOptimize
    }}>
      {children}
    </DataContext.Provider>
  );
}

export function useData() {
  const ctx = useContext(DataContext);
  if (!ctx) throw new Error('useData must be used within DataProvider');
  return ctx;
}
