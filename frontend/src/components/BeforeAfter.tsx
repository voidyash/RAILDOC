import { useData } from '../api/DataContext';

export default function BeforeAfter() {
  const { comparison: data, loading, runOptimize } = useData();

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-64 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
        <div className="h-32 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse" />
        <div className="grid grid-cols-2 gap-6">
          <div className="h-80 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse" />
          <div className="h-80 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse" />
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500 dark:text-gray-400 mb-4">Run the optimizer first to see before/after comparison</p>
        <button onClick={runOptimize} className="px-4 py-2 bg-slate-600 text-white rounded-lg hover:bg-slate-700 text-sm font-medium">
          Run Optimizer
        </button>
      </div>
    );
  }

  const { before, after, improvements } = data;

  const metrics = [
    { label: 'Total Blocks', before: before.total_blocks, after: after.planned_blocks, unit: '', better: 'lower' },
    { label: 'Total Downtime', before: before.total_downtime_minutes, after: after.total_downtime_minutes, unit: ' min', better: 'lower' },
    { label: 'Train Conflicts', before: before.train_conflicts, after: after.train_conflicts, unit: '', better: 'lower' },
    { label: 'Asset Availability', before: before.asset_availability, after: after.asset_availability, unit: '%', better: 'higher' },
    { label: 'Block Utilization', before: before.block_utilization, after: after.block_utilization, unit: '%', better: 'higher' },
    { label: 'Multi-Dept Blocks', before: before.multi_dept_blocks, after: after.multi_dept_blocks, unit: '', better: 'higher' },
  ];

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Before vs After Optimization</h2>

      <div className="bg-slate-800 rounded-lg p-6 text-white">
        <h3 className="text-lg font-bold mb-2">Optimization Impact Summary</h3>
        <div className="grid grid-cols-4 gap-4">
          <div><div className="text-3xl font-bold">{improvements.blocks_reduction}</div><div className="text-sm opacity-80">Blocks Eliminated</div></div>
          <div><div className="text-3xl font-bold">{improvements.downtime_reduction}min</div><div className="text-sm opacity-80">Downtime Saved</div></div>
          <div><div className="text-3xl font-bold">{improvements.conflicts_reduction}</div><div className="text-sm opacity-80">Conflicts Resolved</div></div>
          <div><div className="text-3xl font-bold">{improvements.multi_dept_blocks}</div><div className="text-sm opacity-80">Multi-Dept Blocks</div></div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-5">
          <div className="flex items-center gap-2 mb-4"><span className="w-3 h-3 bg-red-400 rounded-full" /><h3 className="text-lg font-bold text-gray-900 dark:text-gray-100">Before (Unoptimized)</h3></div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">Each task gets its own block. No coordination between departments.</p>
          <div className="space-y-3">
            {metrics.map((m) => (
              <div key={m.label} className="flex items-center justify-between p-2 bg-red-50 dark:bg-red-500/10 rounded-lg">
                <span className="text-sm text-gray-600 dark:text-gray-400">{m.label}</span>
                <span className="text-lg font-bold text-red-600 dark:text-red-400">{m.before}{m.unit}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-5">
          <div className="flex items-center gap-2 mb-4"><span className="w-3 h-3 bg-green-400 rounded-full" /><h3 className="text-lg font-bold text-gray-900 dark:text-gray-100">After (Optimized)</h3></div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">Tasks are prioritized by risk and grouped into coordinated multi-department blocks.</p>
          <div className="space-y-3">
            {metrics.map((m) => {
              const improved = m.better === 'lower' ? m.after < m.before : m.after > m.before;
              return (
                <div key={m.label} className={`flex items-center justify-between p-2 rounded-lg ${improved ? 'bg-green-50 dark:bg-green-500/10' : 'bg-amber-50 dark:bg-amber-500/10'}`}>
                  <span className="text-sm text-gray-600 dark:text-gray-400">{m.label}</span>
                  <div className="flex items-center gap-2">
                    <span className={`text-lg font-bold ${improved ? 'text-green-600 dark:text-green-400' : 'text-amber-600 dark:text-amber-300'}`}>{m.after}{m.unit}</span>
                    <span className={`text-xs ${improved ? 'text-green-500 dark:text-green-400' : 'text-amber-500 dark:text-amber-400'}`}>{improved ? '✓' : '→'}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-5">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Key Improvements</h3>
        <div className="grid grid-cols-3 gap-4">
          <div className="p-4 bg-green-50 dark:bg-green-500/10 rounded-lg border border-green-200 dark:border-green-500/30">
            <div className="text-2xl font-bold text-green-600 dark:text-green-400 mb-1">{improvements.blocks_reduction > 0 ? `${((improvements.blocks_reduction / before.total_blocks) * 100).toFixed(0)}%` : '0%'}</div>
            <div className="text-sm text-green-700 dark:text-green-300">Fewer Blocks</div>
            <div className="text-xs text-green-600 dark:text-green-400 mt-1">{before.total_blocks} → {after.planned_blocks} blocks</div>
          </div>
          <div className="p-4 bg-slate-50 dark:bg-slate-800/60 rounded-lg border border-slate-200 dark:border-slate-600">
            <div className="text-2xl font-bold text-slate-700 dark:text-slate-300 mb-1">{improvements.downtime_reduction > 0 ? `${((improvements.downtime_reduction / before.total_downtime_minutes) * 100).toFixed(0)}%` : '0%'}</div>
            <div className="text-sm text-slate-700 dark:text-slate-300">Less Downtime</div>
            <div className="text-xs text-slate-600 dark:text-slate-400 mt-1">{before.total_downtime_minutes} → {after.total_downtime_minutes} minutes</div>
          </div>
          <div className="p-4 bg-purple-50 dark:bg-purple-500/10 rounded-lg border border-purple-200 dark:border-purple-500/30">
            <div className="text-2xl font-bold text-purple-600 dark:text-purple-400 mb-1">{improvements.conflicts_reduction > 0 ? `${((improvements.conflicts_reduction / Math.max(before.train_conflicts, 1)) * 100).toFixed(0)}%` : '0%'}</div>
            <div className="text-sm text-purple-700 dark:text-purple-300">Fewer Conflicts</div>
            <div className="text-xs text-purple-600 dark:text-purple-400 mt-1">{before.train_conflicts} → {after.train_conflicts} conflicts</div>
          </div>
        </div>
      </div>

      <div className="bg-gray-50 dark:bg-gray-700/40 rounded-lg p-5 border border-gray-200 dark:border-gray-700">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Analysis</h3>
        <div className="text-sm text-gray-700 dark:text-gray-300 space-y-2">
          <p><strong>Without optimization:</strong> {before.total_blocks} separate blocks are needed, causing {before.total_downtime_minutes} minutes of total downtime and {before.train_conflicts} train conflicts.</p>
          <p><strong>With constraint-based scheduling:</strong> The system identifies {improvements.multi_dept_blocks} opportunities to coordinate Engineering, S&T, and Traction work in shared blocks, reducing total blocks to {after.planned_blocks} and downtime to {after.total_downtime_minutes} minutes.</p>
          {improvements.downtime_reduction > 0 && (
            <p><strong>Result:</strong> {improvements.downtime_reduction} minutes of asset downtime avoided, improving asset availability to {after.asset_availability}%.</p>
          )}
        </div>
      </div>
    </div>
  );
}
