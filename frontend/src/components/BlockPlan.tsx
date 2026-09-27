import { useState, useEffect, useRef } from 'react';
import { useData } from '../api/DataContext';
import { useAuth } from '../api/AuthContext';
import { approvePlan, revertPlan } from '../api/client';
import type { MaintenanceTask } from '../types';

const UNDO_SECONDS = 5;

export default function BlockPlan() {
  const { blocks, tasks, loading } = useData();
  const { user } = useAuth();
  const canApprove = user?.roles.some((r) => ['admin', 'planner', 'operations', 'engineer'].includes(r));
  const [selectedBlock, setSelectedBlock] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [approving, setApproving] = useState(false);
  const [approvalStatus, setApprovalStatus] = useState<'idle' | 'pending_undo' | 'reverted' | 'error'>('idle');
  const [undoCountdown, setUndoCountdown] = useState(UNDO_SECONDS);
  const approvedPlanId = useRef<string | null>(null);
  const approvedBlockIds = useRef<Set<string>>(new Set());
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const getTaskById = (id: string) => tasks.find((t) => t.task_id === id);

  const getDeptColor = (dept: string) => {
    switch (dept) {
      case 'Engineering': return 'bg-slate-100 text-slate-700 dark:text-slate-300 border-slate-200 dark:bg-slate-500/15 dark:text-slate-300 dark:border-slate-500/30';
      case 'S&T': return 'bg-purple-100 text-purple-700 border-purple-200 dark:bg-purple-500/15 dark:text-purple-300 dark:border-purple-500/30';
      case 'Traction': return 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300 border-amber-200 dark:border-amber-500/30';
      default: return 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-700';
    }
  };

  // Track which blocks are approved (from DB status). Synced from `blocks`
  // during render (react.dev "adjusting state when props change") instead of
  // an effect, so no cascading render is triggered after commit.
  const [prevBlocks, setPrevBlocks] = useState(blocks);
  const [locallyApproved, setLocallyApproved] = useState<Set<string>>(() => {
    const approved = new Set<string>();
    for (const b of blocks) {
      if (b.status === 'Approved') approved.add(b.block_id);
    }
    return approved;
  });
  if (prevBlocks !== blocks) {
    setPrevBlocks(blocks);
    const approved = new Set<string>();
    for (const b of blocks) {
      if (b.status === 'Approved') approved.add(b.block_id);
    }
    setLocallyApproved(approved);
  }

  const clearCountdown = () => {
    if (countdownRef.current) {
      clearInterval(countdownRef.current);
      countdownRef.current = null;
    }
  };

  useEffect(() => {
    return () => clearCountdown();
  }, []);

  // Selection helpers
  const allSelectableIds = blocks.filter((b) => b.status !== 'Approved').map((b) => b.block_id);
  const allSelected = allSelectableIds.length > 0 && allSelectableIds.every((id) => selectedIds.has(id));

  const toggleSelectAll = () => {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(allSelectableIds));
    }
  };

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleApprove = async () => {
    const toApprove = [...selectedIds];
    if (toApprove.length === 0) {
      setApprovalStatus('error');
      setTimeout(() => setApprovalStatus('idle'), 3000);
      return;
    }
    setApproving(true);
    setApprovalStatus('idle');
    try {
      const result = await approvePlan(toApprove);
      approvedPlanId.current = result.plan_id;
      approvedBlockIds.current = new Set(toApprove);
      // Mark selected blocks as Approved locally
      setLocallyApproved((prev) => {
        const next = new Set(prev);
        for (const id of toApprove) next.add(id);
        return next;
      });
      setSelectedIds(new Set());
      setApprovalStatus('pending_undo');
      setUndoCountdown(UNDO_SECONDS);

      countdownRef.current = setInterval(() => {
        setUndoCountdown((prev) => {
          if (prev <= 1) {
            clearCountdown();
            setApprovalStatus('idle');
            approvedPlanId.current = null;
            approvedBlockIds.current = new Set();
            return UNDO_SECONDS;
          }
          return prev - 1;
        });
      }, 1000);
    } catch {
      setApprovalStatus('error');
      setTimeout(() => setApprovalStatus('idle'), 3000);
    } finally {
      setApproving(false);
    }
  };

  const handleUndo = async () => {
    clearCountdown();
    const planId = approvedPlanId.current;
    const revertedIds = [...approvedBlockIds.current];
    if (!planId) return;
    try {
      await revertPlan(planId, revertedIds);
      // Remove approved status from reverted blocks
      setLocallyApproved((prev) => {
        const next = new Set(prev);
        for (const id of revertedIds) next.delete(id);
        return next;
      });
      setApprovalStatus('reverted');
      setTimeout(() => setApprovalStatus('idle'), 3000);
    } catch {
      setApprovalStatus('error');
      setTimeout(() => setApprovalStatus('idle'), 3000);
    }
    approvedPlanId.current = null;
    approvedBlockIds.current = new Set();
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-64 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 space-y-3">
            {[1,2,3].map(i => <div key={i} className="h-40 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse" />)}
          </div>
          <div className="h-64 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Generated Block Plan</h2>
        <div className="flex items-center gap-2">
          {approvalStatus === 'pending_undo' && (
            <div className="flex items-center gap-3 bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded-lg px-4 py-2">
              <div className="flex items-center gap-2">
                <div className="relative w-8 h-8">
                  <svg className="w-8 h-8 -rotate-90" viewBox="0 0 36 36">
                    <circle cx="18" cy="18" r="14" fill="none" stroke="#e5e7eb" strokeWidth="3" />
                    <circle
                      cx="18" cy="18" r="14" fill="none" stroke="#f59e0b" strokeWidth="3"
                      strokeDasharray={`${(undoCountdown / UNDO_SECONDS) * 88} 88`}
                      strokeLinecap="round"
                      className="transition-all duration-1000 ease-linear"
                    />
                  </svg>
                  <span className="absolute inset-0 flex items-center justify-center text-xs font-bold text-amber-700 dark:text-amber-300">
                    {undoCountdown}
                  </span>
                </div>
                <span className="text-sm text-amber-800 dark:text-amber-200 font-medium">Plan approved</span>
              </div>
              <button
                onClick={handleUndo}
                className="px-3 py-1 bg-amber-600 text-white text-sm font-medium rounded-md hover:bg-amber-700 transition-colors"
              >
                Undo
              </button>
            </div>
          )}
          {approvalStatus === 'reverted' && (
            <span className="text-sm text-gray-600 dark:text-gray-400 font-medium">↩ Plan reverted</span>
          )}
          {approvalStatus === 'error' && (
            <span className="text-sm text-red-600 dark:text-red-400 font-medium">
              {selectedIds.size === 0 ? 'Select blocks to approve' : 'Failed to approve plan'}
            </span>
          )}
          {approvalStatus !== 'pending_undo' && canApprove && selectedIds.size > 0 && (
            <button onClick={handleApprove} disabled={approving}
              className="px-4 py-2 rounded-lg text-sm font-medium bg-green-600 text-white hover:bg-green-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed">
              {approving ? 'Approving...' : `Approve ${selectedIds.size} Block${selectedIds.size > 1 ? 's' : ''}`}
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-3">
          {blocks.length === 0 ? (
            <div className="bg-white dark:bg-gray-800 rounded-lg p-8 border border-gray-200 dark:border-gray-700 text-center text-gray-400 dark:text-gray-300">
              No blocks generated yet. Run the optimizer first.
            </div>
          ) : (
            <>
              {/* Select All bar */}
              {allSelectableIds.length > 0 && (
                <div className="flex items-center gap-3 px-4 py-2 bg-gray-50 dark:bg-gray-700/40 rounded-lg border border-gray-200 dark:border-gray-700">
                  <label className="flex items-center gap-2 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={toggleSelectAll}
                      className="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-green-600 dark:text-green-400 focus:ring-green-500"
                    />
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Select all ({allSelectableIds.length} unapproved)
                    </span>
                  </label>
                  {selectedIds.size > 0 && (
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      {selectedIds.size} selected
                    </span>
                  )}
                </div>
              )}

              {blocks.map((block) => {
                const isApproved = locallyApproved.has(block.block_id);
                const isSelected = selectedIds.has(block.block_id);
                const blockTasks = block.assigned_tasks.map(getTaskById).filter(Boolean) as MaintenanceTask[];
                return (
                  <div key={block.block_id}
                    className={`bg-white dark:bg-gray-800 rounded-lg border p-4 transition-all ${
                      selectedBlock === block.block_id
                        ? 'border-slate-500 ring-2 ring-slate-200 dark:ring-slate-600'
                        : isApproved
                          ? 'border-green-200 dark:border-green-500/30 bg-green-50 dark:bg-green-500/10/30'
                          : isSelected
                            ? 'border-green-400 ring-1 ring-green-200 dark:border-green-500 dark:ring-green-500/30 bg-green-50 dark:bg-green-500/10/20'
                            : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:border-gray-600 dark:hover:border-gray-600'
                    }`}>
                    <div className="flex items-center gap-3 mb-3">
                      {!isApproved && (
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelect(block.block_id)}
                          onClick={(e) => e.stopPropagation()}
                          className="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-green-600 dark:text-green-400 focus:ring-green-500 shrink-0"
                        />
                      )}
                      <div className="flex-1 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <h3
                            className="font-bold text-gray-900 dark:text-gray-100 cursor-pointer hover:text-slate-700 dark:text-slate-300"
                            onClick={() => setSelectedBlock(selectedBlock === block.block_id ? null : block.block_id)}
                          >
                            {block.block_id}
                          </h3>
                          {isApproved && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300 border border-green-200 dark:border-green-500/30">
                              ✓ Approved
                            </span>
                          )}
                          <p className="text-xs text-gray-500 dark:text-gray-400">Corridor: {block.corridor_id} · {block.block_type}</p>
                        </div>
                        <div className="text-right">
                          <div className="text-lg font-bold text-gray-900 dark:text-gray-100">{block.start_time} → {block.end_time}</div>
                          <div className="text-xs text-gray-500 dark:text-gray-400">{block.duration_minutes} minutes</div>
                        </div>
                      </div>
                    </div>
                    <div className="flex gap-2 mb-3 ml-7">
                      {block.departments.map((dept) => (
                        <span key={dept} className={`px-2 py-0.5 rounded-full text-xs font-medium border ${getDeptColor(dept)}`}>{dept}</span>
                      ))}
                    </div>
                    <div className="space-y-1 ml-7">
                      {blockTasks.slice(0, 3).map((task) => (
                        <div key={task.task_id} className="flex items-center gap-2 text-sm">
                          <span className="text-gray-400 dark:text-gray-300">•</span>
                          <span className="font-medium text-gray-700 dark:text-gray-300">{task.task_id}</span>
                          <span className="text-gray-500 dark:text-gray-400">—</span>
                          <span className="text-gray-600 dark:text-gray-400">{task.task_type}</span>
                          <span className="text-gray-400 dark:text-gray-300">({task.estimated_duration_minutes}min)</span>
                        </div>
                      ))}
                      {blockTasks.length > 3 && <div className="text-xs text-gray-400 dark:text-gray-300 ml-4">+{blockTasks.length - 3} more tasks</div>}
                    </div>
                    <div className="flex items-center gap-4 mt-3 pt-3 border-t border-gray-100 dark:border-gray-700/60 text-xs ml-7">
                      <div><span className="text-gray-500 dark:text-gray-400">Utilization: </span>
                        <span className={`font-medium ${block.utilization >= 70 ? 'text-green-600 dark:text-green-400' : 'text-amber-600 dark:text-amber-300'}`}>{block.utilization}%</span></div>
                      <div><span className="text-gray-500 dark:text-gray-400">Train Impact: </span>
                        <span className={`font-medium ${block.train_impact <= 30 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>{block.train_impact}%</span></div>
                      <div>
                        {isApproved ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-green-50 dark:bg-green-500/10 text-green-700 dark:text-green-300 border border-green-200 dark:border-green-500/30">
                            ✓ Approved
                          </span>
                        ) : (
                          <span><span className="text-gray-500 dark:text-gray-400">Status: </span>
                            <span className="font-medium text-slate-700 dark:text-slate-300">{block.status}</span></span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </>
          )}
        </div>

        <div className="space-y-4">
          {selectedBlock ? (() => {
            const block = blocks.find((b) => b.block_id === selectedBlock);
            if (!block) return null;
            const blockTasks = block.assigned_tasks.map(getTaskById).filter(Boolean) as MaintenanceTask[];
            return (
              <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-5 sticky top-4">
                <h3 className="font-bold text-gray-900 dark:text-gray-100 mb-3">Block Explanation</h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">{block.explanation}</p>
                <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Assigned Tasks</h4>
                <div className="space-y-2">
                  {blockTasks.map((task) => (
                    <div key={task.task_id} className="p-2 bg-gray-50 dark:bg-gray-700/40 rounded-lg">
                      <div className="text-sm font-medium text-gray-700 dark:text-gray-300">{task.task_id}</div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">Priority: {task.priority_score.toFixed(0)} · Criticality: {task.criticality} · {task.estimated_duration_minutes}min</div>
                    </div>
                  ))}
                </div>
                <div className="mt-4 pt-3 border-t border-gray-100 dark:border-gray-700/60">
                  <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Coordination Benefit</h4>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    {block.departments.length} departments combined in 1 block.
                    Without coordination, {blockTasks.length} separate blocks would be needed,
                    causing {blockTasks.length * 60} minutes of total downtime vs {block.duration_minutes} minutes.
                  </p>
                </div>
              </div>
            );
          })() : (
            <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-8 text-center text-gray-400 dark:text-gray-300">
              Click a block name to see its explanation
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
