import { useState } from 'react';
import { useData } from '../api/DataContext';

type SortKey = 'priority_score' | 'criticality' | 'failure_risk' | 'days_overdue' | 'due_date';

export default function MaintenanceQueue() {
  const { tasks, loading } = useData();
  const [sortKey, setSortKey] = useState<SortKey>('priority_score');
  const [filterDept, setFilterDept] = useState<string>('All');
  const [filterStatus, setFilterStatus] = useState<string>('All');

  const filtered = tasks
    .filter((t) => filterDept === 'All' || t.department === filterDept)
    .filter((t) => filterStatus === 'All' || t.status === filterStatus)
    .sort((a, b) => {
      if (sortKey === 'due_date') return a.due_date.localeCompare(b.due_date);
      return b[sortKey] - a[sortKey];
    });

  const getPriorityBadge = (score: number) => {
    if (score >= 80) return { label: 'Critical', class: 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300' };
    if (score >= 60) return { label: 'High', class: 'bg-orange-100 text-orange-700 dark:bg-orange-500/15 dark:text-orange-300' };
    if (score >= 40) return { label: 'Medium', class: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-500/15 dark:text-yellow-300' };
    return { label: 'Low', class: 'bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300' };
  };

  const getDeptColor = (dept: string) => {
    switch (dept) {
      case 'Engineering': return 'bg-slate-100 text-slate-700 dark:text-slate-300 dark:bg-slate-500/15 dark:text-slate-300';
      case 'S&T': return 'bg-purple-100 text-purple-700 dark:bg-purple-500/15 dark:text-purple-300';
      case 'Traction': return 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300';
      default: return 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300';
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-64 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
        <div className="h-10 w-full bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
        <div className="space-y-2">
          {[1,2,3,4,5].map(i => <div key={i} className="h-14 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />)}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Maintenance Queue</h2>
        <div className="text-sm text-gray-500 dark:text-gray-400">{filtered.length} of {tasks.length} tasks</div>
      </div>

      <div className="flex gap-3">
        <select value={filterDept} onChange={(e) => setFilterDept(e.target.value)}
          className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800">
          <option value="All">All Departments</option>
          <option value="Engineering">Engineering</option>
          <option value="S&T">S&T</option>
          <option value="Traction">Traction</option>
        </select>
        <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}
          className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800">
          <option value="All">All Status</option>
          <option value="Pending">Pending</option>
          <option value="Scheduled">Scheduled</option>
          <option value="Completed">Completed</option>
        </select>
        <select value={sortKey} onChange={(e) => setSortKey(e.target.value as SortKey)}
          className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800">
          <option value="priority_score">Sort by Priority</option>
          <option value="criticality">Sort by Criticality</option>
          <option value="failure_risk">Sort by Failure Risk</option>
          <option value="days_overdue">Sort by Overdue</option>
          <option value="due_date">Sort by Due Date</option>
        </select>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-700/40 border-b border-gray-200 dark:border-gray-700">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Task</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Dept</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Asset</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Corridor</th>
              <th className="text-right px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Priority</th>
              <th className="text-right px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Risk</th>
              <th className="text-right px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Overdue</th>
              <th className="text-right px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Duration</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Due</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-400">Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, 50).map((task) => {
              const badge = getPriorityBadge(task.priority_score);
              return (
                <tr key={task.task_id} className="border-b border-gray-100 dark:border-gray-700/60 hover:bg-gray-50 dark:hover:bg-gray-700/50">
                  <td className="px-4 py-2.5">
                    <div className="font-medium text-gray-900 dark:text-gray-100">{task.task_id}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">{task.task_type}</div>
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${getDeptColor(task.department)}`}>
                      {task.department}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-gray-600 dark:text-gray-400">{task.asset_id}</td>
                  <td className="px-4 py-2.5 text-gray-600 dark:text-gray-400">{task.corridor_id}</td>
                  <td className="px-4 py-2.5 text-right">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${badge.class}`}>
                      {badge.label} {task.priority_score.toFixed(0)}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right text-gray-600 dark:text-gray-400">{task.failure_risk.toFixed(0)}%</td>
                  <td className="px-4 py-2.5 text-right">
                    {task.days_overdue > 0 ? (
                      <span className="text-red-600 dark:text-red-400 font-medium">{task.days_overdue}d</span>
                    ) : (
                      <span className="text-gray-400 dark:text-gray-300">-</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-right text-gray-600 dark:text-gray-400">{task.estimated_duration_minutes}min</td>
                  <td className="px-4 py-2.5 text-gray-600 dark:text-gray-400">{task.due_date}</td>
                  <td className="px-4 py-2.5">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      task.status === 'Scheduled' ? 'bg-slate-100 text-slate-700 dark:text-slate-300 dark:bg-slate-500/15 dark:text-slate-300' :
                      task.status === 'Pending' ? 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400' :
                      'bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300'
                    }`}>
                      {task.status}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {filtered.length > 50 && (
          <div className="px-4 py-3 bg-gray-50 dark:bg-gray-700/40 text-sm text-gray-500 dark:text-gray-400 text-center">
            Showing 50 of {filtered.length} tasks
          </div>
        )}
      </div>
    </div>
  );
}
