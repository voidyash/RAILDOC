import { useEffect, useState } from 'react';
import { useData } from '../api/DataContext';
import { explainTask, explainBlock } from '../api/client';
import type { TaskExplanation } from '../types';

export default function Explainability() {
  const { tasks, blocks, loading } = useData();
  const [selectedTask, setSelectedTask] = useState('');
  const [selectedBlock, setSelectedBlock] = useState('');
  const [taskExplanation, setTaskExplanation] = useState<TaskExplanation | null>(null);
  const [blockExplanation, setBlockExplanation] = useState<any>(null);

  useEffect(() => {
    if (selectedTask) {
      explainTask(selectedTask).then(setTaskExplanation).catch(console.error);
    }
  }, [selectedTask]);

  useEffect(() => {
    if (selectedBlock) {
      explainBlock(selectedBlock).then(setBlockExplanation).catch(console.error);
    }
  }, [selectedBlock]);

  const getScoreBar = (value: number) => (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-100 dark:bg-gray-700 rounded-full h-2 overflow-hidden">
        <div className={`h-full rounded-full ${value >= 70 ? 'bg-red-500' : value >= 40 ? 'bg-amber-50 dark:bg-amber-500/100' : 'bg-green-50 dark:bg-green-500/100'}`}
          style={{ width: `${value}%` }} />
      </div>
      <span className="text-xs font-medium text-gray-600 dark:text-gray-400 w-10 text-right">{value.toFixed(0)}</span>
    </div>
  );

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-64 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
        <div className="grid grid-cols-2 gap-6">
          <div className="h-96 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse" />
          <div className="h-96 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Explainability</h2>
      <div className="grid grid-cols-2 gap-6">
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1 block">Select a Task</label>
            <select value={selectedTask} onChange={(e) => setSelectedTask(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800">
              <option value="">Choose a task...</option>
              {tasks.filter(t => t.assigned_block_id).sort((a, b) => b.priority_score - a.priority_score).map(t => (
                <option key={t.task_id} value={t.task_id}>
                  {t.task_id} — {t.department} — Priority: {t.priority_score.toFixed(0)}
                </option>
              ))}
            </select>
          </div>
          {taskExplanation && (
            <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-bold text-gray-900 dark:text-gray-100">{taskExplanation.task_id}</h3>
                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Priority: {taskExplanation.priority_score.toFixed(0)}</span>
              </div>
              <div className="space-y-2 mb-4">
                <div><div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Asset Criticality</div>{getScoreBar(taskExplanation.criticality)}</div>
                <div><div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Failure Risk</div>{getScoreBar(taskExplanation.failure_risk)}</div>
                <div><div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Train Impact</div>{getScoreBar(taskExplanation.train_impact)}</div>
                <div><div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Safety Criticality</div>{getScoreBar(taskExplanation.safety_criticality)}</div>
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm mb-4">
                <div className="bg-gray-50 dark:bg-gray-700/40 rounded-lg p-2"><div className="text-xs text-gray-500 dark:text-gray-400">Days Overdue</div><div className="font-medium text-gray-900 dark:text-gray-100">{taskExplanation.days_overdue > 0 ? taskExplanation.days_overdue : 'Not overdue'}</div></div>
                <div className="bg-gray-50 dark:bg-gray-700/40 rounded-lg p-2"><div className="text-xs text-gray-500 dark:text-gray-400">Corridor</div><div className="font-medium text-gray-900 dark:text-gray-100">{taskExplanation.corridor_id}</div></div>
                <div className="bg-gray-50 dark:bg-gray-700/40 rounded-lg p-2"><div className="text-xs text-gray-500 dark:text-gray-400">Assigned Block</div><div className="font-medium text-gray-900 dark:text-gray-100">{taskExplanation.assigned_block || 'None'}</div></div>
                <div className="bg-gray-50 dark:bg-gray-700/40 rounded-lg p-2"><div className="text-xs text-gray-500 dark:text-gray-400">Compatible Tasks</div><div className="font-medium text-gray-900 dark:text-gray-100">{taskExplanation.compatible_tasks}</div></div>
              </div>
              <div className="bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-600 rounded-lg p-3">
                <h4 className="text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">Decision Reason</h4>
                <p className="text-sm text-slate-800 dark:text-slate-200">{taskExplanation.reason}</p>
              </div>
              <div className="mt-3 bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded-lg p-3">
                <h4 className="text-xs font-medium text-amber-700 dark:text-amber-300 mb-1">If Moved</h4>
                <p className="text-sm text-amber-800 dark:text-amber-200">{taskExplanation.if_moved}</p>
              </div>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1 block">Select a Block</label>
            <select value={selectedBlock} onChange={(e) => setSelectedBlock(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800">
              <option value="">Choose a block...</option>
              {blocks.map(b => (
                <option key={b.block_id} value={b.block_id}>
                  {b.block_id} — {b.start_time}-{b.end_time} ({b.departments.join(' + ')})
                </option>
              ))}
            </select>
          </div>
          {blockExplanation && (
            <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-5">
              <h3 className="font-bold text-gray-900 dark:text-gray-100 mb-2">{blockExplanation.block_id}</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">{blockExplanation.corridor} · {blockExplanation.time}</p>
              <div className="flex gap-2 mb-3">
                {blockExplanation.departments.map((dept: string) => (
                  <span key={dept} className="px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700 dark:bg-slate-500/15 dark:text-slate-300">{dept}</span>
                ))}
              </div>
              <div className="mb-4">
                <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Block Utilization</div>
                <div className="flex items-center gap-2">
                  <div className="flex-1 bg-gray-100 dark:bg-gray-700 rounded-full h-3 overflow-hidden">
                    <div className="h-full bg-slate-50 dark:bg-slate-800/600 rounded-full" style={{ width: `${blockExplanation.utilization}%` }} />
                  </div>
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{blockExplanation.utilization}%</span>
                </div>
              </div>
              <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Assigned Tasks</h4>
              <div className="space-y-2 mb-4">
                {blockExplanation.tasks.map((task: any) => (
                  <div key={task.task_id} className="p-2 bg-gray-50 dark:bg-gray-700/40 rounded-lg">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{task.task_id}</span>
                      <span className="text-xs text-gray-500 dark:text-gray-400">Priority: {task.priority_score?.toFixed(0)}</span>
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">{task.task_type} · {task.department} · {task.estimated_duration_minutes}min</div>
                  </div>
                ))}
              </div>
              <div className="bg-green-50 dark:bg-green-500/10 border border-green-200 dark:border-green-500/30 rounded-lg p-3 mb-3">
                <h4 className="text-xs font-medium text-green-700 dark:text-green-300 mb-1">Why This Block?</h4>
                <p className="text-sm text-green-800 dark:text-green-200">{blockExplanation.explanation}</p>
              </div>
              <div className="bg-purple-50 dark:bg-purple-500/10 border border-purple-200 dark:border-purple-500/30 rounded-lg p-3">
                <h4 className="text-xs font-medium text-purple-700 dark:text-purple-300 mb-1">Coordination Benefit</h4>
                <p className="text-sm text-purple-800 dark:text-purple-200">{blockExplanation.coordination_benefit}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
