import { useState } from 'react';
import type { Detection } from '../types';
import {
  defectDisplayName,
  getMaintenanceRecommendation,
} from '../data/maintenanceRecommendations';

/**
 * Maintenance Recommendation card — a separate recommendation layer on top of
 * the YOLO detection (the detection itself is untouched; confidence stays in
 * app state but is never shown here).
 *
 * Human-in-the-loop flow: the AI mapping generates tools + estimated time;
 * the operator can rename/remove/add tools and correct the time. Edits are
 * stored in a separate "human verified" state so the original AI
 * recommendation is never destroyed.
 */

interface Recommendation {
  tools: string[];
  estimatedTime: string;
}

function clone(rec: Recommendation | null): Recommendation {
  return { tools: rec ? [...rec.tools] : [], estimatedTime: rec?.estimatedTime ?? '' };
}

export default function MaintenanceRecommendationCard({
  detection,
  corridorId,
  location,
}: {
  detection: Detection;
  corridorId: string;
  location: string;
}) {
  const ai = getMaintenanceRecommendation(detection.defect_type, detection.label);

  // Human-verified layer — null until the operator edits something.
  const [verified, setVerified] = useState<Recommendation | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Recommendation>({ tools: [], estimatedTime: '' });
  const [editingTool, setEditingTool] = useState<number | null>(null);
  const [toolDraft, setToolDraft] = useState('');
  // Per-detection reset is handled by the parent keying this component with
  // the analysis_id (key-based reset — no state-reset effect needed).

  /** The currently displayed (human-verified, else AI, else empty) rec. */
  const current: Recommendation = verified ?? (ai ? { tools: [...ai.tools], estimatedTime: ai.estimatedTime } : { tools: [], estimatedTime: '' });

  const startEdit = () => {
    setDraft(clone(current));
    setEditingTool(null);
    setEditing(true);
  };

  const cancelEdit = () => {
    setEditing(false);
    setEditingTool(null);
  };

  const saveEdit = () => {
    const tools = draft.tools.map((t) => t.trim()).filter(Boolean);
    const time = draft.estimatedTime.trim();
    setVerified({
      tools,
      estimatedTime: time || (ai?.estimatedTime ?? ''),
    });
    setEditing(false);
    setEditingTool(null);
  };

  /** Inline per-tool edit (rename / remove) outside full edit mode. */
  const applyToolEdit = (index: number, name: string) => {
    const trimmed = name.trim();
    const base = clone(current);
    if (trimmed) {
      base.tools[index] = trimmed;
    } else {
      base.tools.splice(index, 1); // cleared name = removed tool
    }
    setVerified(base);
    setEditingTool(null);
  };

  const removeTool = (index: number) => {
    const base = clone(current);
    base.tools.splice(index, 1);
    setVerified(base);
  };

  /** Edit mode only: an empty draft row, typed into and saved with the draft. */
  const addTool = () => {
    setDraft((d) => ({ ...d, tools: [...d.tools, ''] }));
  };

  const setTime = (value: string) => {
    const base = clone(current);
    base.estimatedTime = value;
    setVerified(base);
  };

  const isVerified = verified !== null;
  const unknownClass = ai === null;

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-[10px] font-medium uppercase tracking-wider text-gray-400 dark:text-gray-300">
            {isVerified ? 'Human Verified Recommendation' : 'AI Maintenance Recommendation'}
          </span>
          {isVerified ? (
            <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300 whitespace-nowrap">
              ✓ Verified
            </span>
          ) : (
            <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300 whitespace-nowrap">
              Requires Human Verification
            </span>
          )}
        </div>
      </div>

      {/* Defect */}
      <p className="text-sm font-semibold text-gray-900 dark:text-gray-100 mt-2.5">
        {defectDisplayName(detection.defect_type)}
      </p>
      <p className="text-[11px] text-gray-400 dark:text-gray-300 mt-0.5">
        {detection.asset_type} · {corridorId} · {location}
      </p>

      {unknownClass && !isVerified && (
        <div className="bg-gray-50 dark:bg-gray-700/40 border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-2.5 mt-3">
          <p className="text-xs font-medium text-gray-700 dark:text-gray-200">
            Maintenance recommendation unavailable
          </p>
          <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-0.5">
            Unknown defect class — add tools and estimated time manually.
          </p>
        </div>
      )}

      {/* ── Edit mode ─────────────────────────────────────────────── */}
      {editing ? (
        <div className="mt-3 space-y-3">
          <div>
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5">Required Tools</p>
            <div className="space-y-1.5">
              {draft.tools.map((tool, i) => (
                <div key={i} className="flex items-center gap-1.5">
                  <input
                    value={tool}
                    onChange={(e) => {
                      const tools = [...draft.tools];
                      tools[i] = e.target.value;
                      setDraft({ ...draft, tools });
                    }}
                    placeholder="Tool name"
                    className="flex-1 border border-gray-300 dark:border-gray-600 rounded-lg px-2.5 py-1.5 text-xs bg-transparent"
                  />
                  <button
                    onClick={() => {
                      const tools = [...draft.tools];
                      tools.splice(i, 1);
                      setDraft({ ...draft, tools });
                    }}
                    title="Remove tool"
                    className="px-2 py-1.5 rounded-lg text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10"
                  >
                    ✕
                  </button>
                </div>
              ))}
              {draft.tools.length === 0 && (
                <p className="text-[11px] text-gray-400 dark:text-gray-300">No tools yet — add the first one.</p>
              )}
            </div>
            <button
              onClick={addTool}
              className="mt-2 px-2.5 py-1 border border-gray-300 dark:border-gray-600 rounded-lg text-xs text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700/50"
            >
              + Add Tool
            </button>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5">
              Estimated Repair Time
            </label>
            <input
              value={draft.estimatedTime}
              onChange={(e) => setDraft({ ...draft, estimatedTime: e.target.value })}
              placeholder="e.g. 2 hr 30 min"
              className="w-40 border border-gray-300 dark:border-gray-600 rounded-lg px-2.5 py-1.5 text-xs bg-transparent"
            />
          </div>

          <div className="flex gap-2 pt-1">
            <button
              onClick={saveEdit}
              className="flex-1 px-3 py-2 bg-slate-600 text-white rounded-lg text-xs font-medium hover:bg-slate-700"
            >
              Save Recommendations
            </button>
            <button
              onClick={cancelEdit}
              className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-xs font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700/50"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        /* ── Display mode ─────────────────────────────────────────── */
        <div className="mt-3 space-y-3">
          <div>
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5">Required Tools</p>
            {current.tools.length === 0 ? (
              <p className="text-xs text-gray-400 dark:text-gray-300">
                No tools recorded — use Edit Recommendations to add them.
              </p>
            ) : (
              <ul className="space-y-1">
                {current.tools.map((tool, i) => (
                  <li key={i} className="flex items-center justify-between gap-2 text-xs text-gray-800 dark:text-gray-200">
                    {editingTool === i ? (
                      <span className="flex items-center gap-1.5 flex-1">
                        <input
                          autoFocus
                          value={toolDraft}
                          onChange={(e) => setToolDraft(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') applyToolEdit(i, toolDraft);
                            if (e.key === 'Escape') {
                              // Aborting an unsaved new tool removes it.
                              if (!current.tools[i]?.trim()) removeTool(i);
                              setEditingTool(null);
                            }
                          }}
                          className="flex-1 border border-gray-300 dark:border-gray-600 rounded-lg px-2 py-1 text-xs bg-transparent"
                        />
                        <button
                          onClick={() => applyToolEdit(i, toolDraft)}
                          title="Save tool name"
                          className="px-1.5 py-1 rounded text-green-600 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-500/10"
                        >
                          ✓
                        </button>
                      </span>
                    ) : (
                      <>
                        <span>• {tool}</span>
                        <button
                          onClick={() => {
                            setEditingTool(i);
                            setToolDraft(tool);
                          }}
                          className="text-[11px] px-2 py-0.5 border border-gray-200 dark:border-gray-700 rounded text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700/50"
                        >
                          Edit
                        </button>
                      </>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Estimated Repair Time</p>
              {!isVerified ? (
                current.estimatedTime ? (
                  <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">{current.estimatedTime}</p>
                ) : (
                  <p className="text-xs text-gray-400 dark:text-gray-300">Not set — add it via Edit Recommendations.</p>
                )
              ) : (
                <input
                  value={current.estimatedTime}
                  onChange={(e) => setTime(e.target.value)}
                  placeholder="e.g. 2 hr 30 min"
                  className="mt-0.5 w-36 border border-gray-300 dark:border-gray-600 rounded-lg px-2 py-1 text-sm bg-transparent"
                />
              )}
            </div>
            <button
              onClick={startEdit}
              className="px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg text-xs font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700/50"
            >
              Edit Recommendations
            </button>
          </div>

          {/* Original AI recommendation preserved below the verified one */}
          {isVerified && ai && (
            <details className="text-xs text-gray-500 dark:text-gray-400">
              <summary className="cursor-pointer select-none font-medium">AI Recommendation (original)</summary>
              <ul className="mt-1.5 space-y-0.5 pl-3">
                {ai.tools.map((t, i) => (
                  <li key={i}>• {t}</li>
                ))}
              </ul>
              <p className="mt-1 pl-3">Estimated Time: {ai.estimatedTime}</p>
            </details>
          )}
        </div>
      )}
    </div>
  );
}