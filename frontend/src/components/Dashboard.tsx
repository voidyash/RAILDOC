import { useState } from 'react';
import { useData } from '../api/DataContext';
import { useAuth } from '../api/AuthContext';
import { runReplan } from '../api/client';

export default function Dashboard() {
  const { dashboard: data, loading, loadError, optimizing, optimizeProgress, runOptimize, refresh } = useData();
  const { user } = useAuth();
  const canOptimize = user?.roles.some((r) => ['admin', 'planner', 'operations', 'engineer'].includes(r));
  const [replanning, setReplanning] = useState(false);
  const [replanMsg, setReplanMsg] = useState<string | null>(null);

  const handleReplan = async () => {
    setReplanning(true);
    setReplanMsg(null);
    try {
      const res = await runReplan('dashboard_manual_trigger');
      setReplanMsg(`✓ ${res.message} — ${res.tasks_scheduled}/${res.total_tasks} tasks scheduled in ${res.metrics?.planned_blocks ?? 'new'} blocks`);
      refresh?.();
    } catch {
      setReplanMsg('✗ Replan failed — check backend logs');
    } finally {
      setReplanning(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="h-8 w-64 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
          <div className="h-9 w-36 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse" />
        </div>
        <div className="grid grid-cols-3 gap-4">
          {[1,2,3,4,5,6].map(i => (
            <div key={i} className="h-24 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-center py-12">
        {loadError ? (
          <div className="max-w-md mx-auto mb-4 rounded-lg bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 px-4 py-3 text-sm text-red-700 dark:text-red-300">
            {loadError}
          </div>
        ) : null}
        <p className="text-gray-500 dark:text-gray-400 mb-4">No data loaded</p>
        <button
          onClick={() => refresh?.()}
          className="px-4 py-2 border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700/60 mb-3"
        >
          Retry
        </button>
        {canOptimize && (
          <button
            onClick={runOptimize}
            className="px-4 py-2 bg-slate-600 text-white rounded-lg hover:bg-slate-700"
          >
            Generate Initial Plan
          </button>
        )}
      </div>
    );
  }

  const kpis = [
    {
      label: 'Asset Availability',
      value: `${data.asset_availability}%`,
      color: data.asset_availability >= 90 ? 'text-green-600 dark:text-green-400' : 'text-amber-600 dark:text-amber-300',
      bg: data.asset_availability >= 90 ? 'bg-green-50 dark:bg-green-500/10' : 'bg-amber-50 dark:bg-amber-500/10',
    },
    {
      label: 'Maintenance Backlog',
      value: data.maintenance_backlog.toString(),
      color: data.maintenance_backlog < 50 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400',
      bg: data.maintenance_backlog < 50 ? 'bg-green-50 dark:bg-green-500/10' : 'bg-red-50 dark:bg-red-500/10',
    },
    {
      label: 'Planned Blocks',
      value: data.planned_blocks.toString(),
      color: 'text-slate-700 dark:text-slate-300',
      bg: 'bg-slate-100',
    },
    {
      label: 'Block Utilization',
      value: `${data.block_utilization}%`,
      color: data.block_utilization >= 70 ? 'text-green-600 dark:text-green-400' : 'text-amber-600 dark:text-amber-300',
      bg: data.block_utilization >= 70 ? 'bg-green-50 dark:bg-green-500/10' : 'bg-amber-50 dark:bg-amber-500/10',
    },
    {
      label: 'Train Conflicts',
      value: data.train_conflicts.toString(),
      color: data.train_conflicts === 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400',
      bg: data.train_conflicts === 0 ? 'bg-green-50 dark:bg-green-500/10' : 'bg-red-50 dark:bg-red-500/10',
    },
    {
      label: 'Multi-Dept Blocks',
      value: data.multi_dept_blocks.toString(),
      color: 'text-purple-600 dark:text-purple-400',
      bg: 'bg-purple-50 dark:bg-purple-500/10',
    },
  ];

  const priorityColors: Record<string, string> = {
    critical: 'bg-red-50 dark:bg-red-500/100',
    high: 'bg-orange-500',
    medium: 'bg-yellow-500',
    low: 'bg-green-50 dark:bg-green-500/100',
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Dashboard</h2>
        {canOptimize && (
          <div className="flex items-center gap-2">
            <button
              onClick={handleReplan}
              disabled={replanning || optimizing}
              className="px-4 py-2 border border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700/60 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
              title="Recalculate priorities and rerun the optimizer over current data"
            >
              {replanning ? 'Replanning…' : '⚡ Dynamic Replan'}
            </button>
            <button
              onClick={runOptimize}
              disabled={optimizing}
              className="px-4 py-2 bg-slate-600 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
            >
              {optimizing ? 'Optimizing...' : 'Run Optimizer'}
            </button>
          </div>
        )}
      </div>

      {replanMsg && (
        <div className={`rounded-lg px-4 py-3 text-sm border ${replanMsg.startsWith('✓') ? 'bg-green-50 dark:bg-green-500/10 border-green-200 dark:border-green-500/30 text-green-700 dark:text-green-300' : 'bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/30 text-red-700 dark:text-red-300'}`}>
          {replanMsg}
        </div>
      )}

      {optimizing && optimizeProgress.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Optimization Progress</h3>
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {optimizeProgress.filter((s) => s.status === 'done').length} / {optimizeProgress.length} steps
            </span>
          </div>
          <div className="space-y-3">
            {optimizeProgress.map((step) => (
              <div key={step.step} className="flex items-center gap-3">
                <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                  step.status === 'done' ? 'bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300' :
                  step.status === 'active' ? 'bg-slate-100 text-slate-700 dark:text-slate-300 dark:bg-slate-500/15 dark:text-slate-300 animate-pulse' :
                  step.status === 'error' ? 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300' :
                  'bg-gray-100 dark:bg-gray-700 text-gray-400 dark:text-gray-300'
                }`}>
                  {step.status === 'done' ? '✓' : step.status === 'active' ? '◉' : step.status === 'error' ? '✗' : step.step}
                </div>
                <div className="flex-1">
                  <span className={`text-sm ${
                    step.status === 'done' ? 'text-green-700 dark:text-green-300' :
                    step.status === 'active' ? 'text-slate-700 dark:text-slate-300 font-medium' :
                    step.status === 'error' ? 'text-red-700 dark:text-red-300' :
                    'text-gray-400 dark:text-gray-300'
                  }`}>
                    {step.label}
                  </span>
                </div>
                {step.status === 'active' && (
                  <div className="w-16 h-1.5 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
                    <div className="h-full bg-slate-500 rounded-full animate-pulse" style={{ width: '60%' }} />
                  </div>
                )}
              </div>
            ))}
          </div>
          <div className="mt-4 pt-3 border-t border-gray-100 dark:border-gray-700/60">
            <div className="w-full bg-gray-100 dark:bg-gray-700 rounded-full h-2 overflow-hidden">
              <div
                className="h-full bg-slate-500 rounded-full transition-all duration-500"
                style={{ width: `${(optimizeProgress.filter((s) => s.status === 'done').length / optimizeProgress.length) * 100}%` }}
              />
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-3 gap-4">
        {kpis.map((kpi) => (
          <div key={kpi.label} className={`${kpi.bg} rounded-lg p-4 border border-gray-100 dark:border-gray-700/60`}>
            <p className="text-sm text-gray-600 dark:text-gray-400">{kpi.label}</p>
            <p className={`text-3xl font-bold ${kpi.color} mt-1`}>{kpi.value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white dark:bg-gray-800 rounded-lg p-5 border border-gray-200 dark:border-gray-700">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Task Priority Distribution</h3>
          <div className="space-y-3">
            {Object.entries(data.priority_distribution ?? {}).map(([level, count]) => {
              if (level === 'total') return null;
              const percentage = (data.priority_distribution?.total ?? 0) > 0
                ? ((count as number) / (data.priority_distribution?.total ?? 1) * 100) : 0;
              return (
                <div key={level} className="flex items-center gap-3">
                  <span className="text-xs font-medium text-gray-600 dark:text-gray-400 w-16 capitalize">{level}</span>
                  <div className="flex-1 bg-gray-100 dark:bg-gray-700 rounded-full h-4 overflow-hidden">
                    <div
                      className={`h-full ${priorityColors[level]} rounded-full transition-all`}
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                  <span className="text-xs text-gray-500 dark:text-gray-400 w-12 text-right">{count as number}</span>
                </div>
              );
            })}
          </div>
          <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-700/60 text-xs text-gray-500 dark:text-gray-400">
            Total: {data.priority_distribution?.total ?? 0} tasks · {data.scheduled_tasks ?? 0} scheduled
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg p-5 border border-gray-200 dark:border-gray-700">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Recommendations</h3>
          {(data.recommendations?.length ?? 0) > 0 ? (
            <div className="space-y-2">
              {data.recommendations.map((rec, i) => (
                <div key={i} className="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-300 p-2 bg-gray-50 dark:bg-gray-700/40 rounded-lg">
                  <span>{rec}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-400 dark:text-gray-300 text-sm">
              Run the optimizer to generate recommendations
            </div>
          )}
          <div className="mt-4 pt-3 border-t border-gray-100 dark:border-gray-700/60">
            <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Fleet Overview</h4>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="bg-gray-50 dark:bg-gray-700/40 rounded-lg p-2">
                <div className="text-lg font-bold text-gray-900 dark:text-gray-100">{data.total_assets}</div>
                <div className="text-xs text-gray-500 dark:text-gray-400">Total Assets</div>
              </div>
              <div className="bg-amber-50 dark:bg-amber-500/10 rounded-lg p-2">
                <div className="text-lg font-bold text-amber-600 dark:text-amber-300">{data.degraded_assets}</div>
                <div className="text-xs text-gray-500 dark:text-gray-400">Degraded</div>
              </div>
              <div className="bg-red-50 dark:bg-red-500/10 rounded-lg p-2">
                <div className="text-lg font-bold text-red-600 dark:text-red-400">{data.maintenance_assets}</div>
                <div className="text-xs text-gray-500 dark:text-gray-400">Under Maint.</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-lg p-5 border border-gray-200 dark:border-gray-700">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">System Status</h3>
        <div className="grid grid-cols-4 gap-4 text-center">
          <div className="p-3 bg-slate-100 rounded-lg dark:bg-slate-700/60">
            <div className="text-2xl font-bold text-slate-700 dark:text-slate-300">{data.total_tasks}</div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Total Tasks</div>
          </div>
          <div className="p-3 bg-green-50 dark:bg-green-500/10 rounded-lg">
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">{data.planned_blocks}</div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Planned Blocks</div>
          </div>
          <div className="p-3 bg-purple-50 dark:bg-purple-500/10 rounded-lg">
            <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">{data.multi_dept_blocks}</div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Coordinated</div>
          </div>
          <div className="p-3 bg-amber-50 dark:bg-amber-500/10 rounded-lg">
            <div className="text-2xl font-bold text-amber-600 dark:text-amber-300">
              {data.train_disruption_minutes}min
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Train Impact</div>
          </div>
        </div>
      </div>
    </div>
  );
}
