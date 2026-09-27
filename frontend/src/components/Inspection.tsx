import { useEffect, useRef, useState } from 'react';
import type { AgentWorkflow, Detection, InspectionAnalysis } from '../types';
import {
  analyzeImage,
  commitWorkflow,
  createTicket,
  getCorridors,
  runWorkflow,
} from '../api/client';
import MaintenanceRecommendationCard from './MaintenanceRecommendationCard';

type Stage = 'upload' | 'analyzing' | 'result' | 'workflow';

const SEVERITY_STYLES: Record<string, string> = {
  critical: 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300 border-red-200 dark:border-red-500/30',
  high: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300 border-amber-200 dark:border-amber-500/30',
  medium: 'bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-500/15 dark:text-blue-300 dark:border-blue-500/30',
  low: 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 dark:bg-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-700',
};

const AGENT_LABELS: Record<string, string> = {
  detection_agent: 'Detection Agent',
  admin_agent: 'Admin Agent',
  engineer_agent: 'Engineer Agent',
  planner_agent: 'Planner Agent',
  operations_agent: 'Operations Agent',
  optimization_engine: 'Optimization Engine',
};

function minutesToTime(mins: number): string {
  const h = Math.floor(mins / 60) % 24;
  const m = mins % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

/** Backend reports the backbone as e.g. 'yolo26n-det' — render it readably. */
function modelKindLabel(kind?: string): string {
  if (!kind) return 'unknown';
  return kind.replace(/^yolo/i, 'YOLO');
}

export default function Inspection() {
  const [stage, setStage] = useState<Stage>('upload');
  const [assetType, setAssetType] = useState('track');
  const [corridors, setCorridors] = useState<string[]>([]);
  const [corridorId, setCorridorId] = useState('');
  const [location, setLocation] = useState('KM 241.7');
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<InspectionAnalysis | null>(null);
  const [ticketId, setTicketId] = useState<string | null>(null);
  const [ticketCreated, setTicketCreated] = useState(false);
  const [workflow, setWorkflow] = useState<AgentWorkflow | null>(null);
  const [decision, setDecision] = useState<'pending' | 'approved' | 'rejected' | null>(null);
  const [commitResult, setCommitResult] = useState<{ block_id?: string; message: string } | null>(null);
  const [committing, setCommitting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [naturalDims, setNaturalDims] = useState<{ w: number; h: number } | null>(null);

  useEffect(() => {
    getCorridors()
      .then((cs: Array<{ corridor_id: string }>) => {
        const ids = cs.map((c) => c.corridor_id);
        setCorridors(ids);
        setCorridorId((prev) => prev || ids[0] || '');
      })
      .catch(() => setCorridors([]));
  }, []);

  const handleFile = (f: File) => {
    setFile(f);
    setAnalysis(null);
    setTicketCreated(false);
    setWorkflow(null);
    setStage('upload');
    const reader = new FileReader();
    reader.onload = () => setPreview(reader.result as string);
    reader.readAsDataURL(f);
  };

  const handleImgLoad = () => {
    const el = imgRef.current;
    if (el && el.naturalWidth) {
      setNaturalDims({ w: el.naturalWidth, h: el.naturalHeight });
    }
  };

  const runAnalysis = async () => {
    if (!file) return;
    setStage('analyzing');
    setError(null);
    try {
      const result = await analyzeImage(file, assetType);
      setAnalysis(result);
      setStage('result');
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: { message?: string } | string } } };
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'object' ? detail?.message ?? 'Model unavailable' : detail ?? 'Analysis failed');
      setStage('upload');
    }
  };

  const handleCreateTicket = async () => {
    if (!analysis || analysis.detections.length === 0 || !corridorId) return;
    try {
      const res = await createTicket(analysis.detections[0], corridorId, location);
      setTicketId(res.ticket_id);
      setTicketCreated(true);
    } catch {
      setError('Failed to create maintenance ticket');
    }
  };

  const handleRunWorkflow = async () => {
    if (!analysis || analysis.detections.length === 0 || !ticketId || !corridorId) return;
    setStage('workflow');
    setError(null);
    setDecision(null);
    setCommitResult(null);
    try {
      const wf = await runWorkflow(ticketId, analysis.detections[0], corridorId, location);
      setWorkflow(wf);
    } catch {
      setError('Workflow failed');
      setStage('result');
    }
  };

  const handleDecision = async (choice: 'approve' | 'reject') => {
    if (!workflow) return;
    setCommitting(true);
    setError(null);
    try {
      const res = await commitWorkflow(workflow.workflow_id, choice);
      setDecision(choice === 'approve' ? 'approved' : 'rejected');
      setCommitResult({ block_id: res.block_id, message: res.message });
    } catch {
      setError('Commit failed — the workflow may already be decided.');
    } finally {
      setCommitting(false);
    }
  };

  const reset = () => {
    setStage('upload');
    setAnalysis(null);
    setPreview(null);
    setWorkflow(null);
    setTicketCreated(false);
    setTicketId(null);
    setFile(null);
    setDecision(null);
    setCommitResult(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">Defect Inspection</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Upload an inspection image — the Detection Agent runs local CV models
          to classify and localize defects.
        </p>
      </div>

      {/* Controls */}
      {stage !== 'workflow' && (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 flex flex-wrap items-end gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Asset Type</label>
            <select
              value={assetType}
              onChange={(e) => { setAssetType(e.target.value); setAnalysis(null); setTicketCreated(false); }}
              className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm"
            >
              <option value="track">Track</option>
              <option value="light_pole">Light Pole</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Corridor</label>
            <select
              value={corridorId}
              onChange={(e) => setCorridorId(e.target.value)}
              className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm"
            >
              {corridors.length === 0 && <option value="">Loading…</option>}
              {corridors.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Location</label>
            <input
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm w-36"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Inspection Image</label>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
              className="text-sm file:mr-3 file:px-3 file:py-1.5 file:rounded-lg file:border-0 file:bg-slate-600 file:text-white file:text-xs file:cursor-pointer"
            />
          </div>
          <button
            onClick={runAnalysis}
            disabled={!file || stage === 'analyzing'}
            className="px-4 py-2 bg-slate-600 text-white rounded-lg text-sm font-medium hover:bg-slate-700 disabled:opacity-40"
          >
            {stage === 'analyzing' ? 'Analyzing…' : 'Run Detection'}
          </button>
        </div>
      )}

      {error && (
        <div className="bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 text-red-700 rounded-lg px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {/* Image + results */}
      {(stage === 'analyzing' || stage === 'result') && preview && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
            <p className="text-xs font-medium text-gray-400 dark:text-gray-300 uppercase tracking-wider mb-3">
              Inspection Image
            </p>
            <div className="relative inline-block w-full">
              <img
                src={preview}
                alt="inspection"
                className="w-full rounded-lg"
                ref={(el) => { imgRef.current = el; }}
                onLoad={handleImgLoad}
              />
              {analysis && naturalDims && analysis.detections.map((d, i) => (
                <BBox key={i} detection={{ ...d, natural_width: naturalDims.w, natural_height: naturalDims.h }} />
              ))}
            </div>
          </div>

          <div className="space-y-4">
            {analysis && (
              <>
                <div className={`rounded-xl border p-4 ${analysis.is_defective ? 'bg-red-50 dark:bg-red-500/10 border-red-200 dark:border-red-500/30' : 'bg-green-50 dark:bg-green-500/10 border-green-200 dark:border-green-500/30'}`}>
                  <p className="text-sm font-semibold">
                    {analysis.is_defective ? '⚠ Defect Detected' : '✓ No Defect Detected'}
                  </p>
                  <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                    Model: {modelKindLabel(analysis.model_info.kind)} · Inference: {analysis.inference_ms} ms
                  </p>
                </div>

                {analysis.detections.map((d, i) => (
                  <div key={i} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">{d.defect_type.replace('_', ' ')}</span>
                      <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium border ${SEVERITY_STYLES[d.severity] ?? SEVERITY_STYLES.low}`}>
                        {d.severity}
                      </span>
                    </div>
                    <dl className="grid grid-cols-2 gap-x-4 gap-y-2 mt-3 text-xs">
                      <div><dt className="text-gray-400 dark:text-gray-300">Asset</dt><dd className="font-semibold text-gray-800 dark:text-gray-200">{d.asset_type}</dd></div>
                      <div><dt className="text-gray-400 dark:text-gray-300">Corridor</dt><dd className="font-semibold text-gray-800 dark:text-gray-200">{corridorId}</dd></div>
                      <div><dt className="text-gray-400 dark:text-gray-300">Location</dt><dd className="font-semibold text-gray-800 dark:text-gray-200">{location}</dd></div>
                    </dl>
                    <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-700">
                      {/* Keyed by analysis_id: a new analysis remounts the card,
                          resetting its AI→verified edit state cleanly. */}
                      <MaintenanceRecommendationCard
                        key={analysis.analysis_id}
                        detection={d}
                        corridorId={corridorId}
                        location={location}
                      />
                    </div>
                  </div>
                ))}

                {analysis.is_defective && (
                  <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 space-y-3">
                    {!ticketCreated ? (
                      <button
                        onClick={handleCreateTicket}
                        disabled={!corridorId}
                        title={corridorId ? undefined : 'Waiting for corridor selection'}
                        className="w-full px-4 py-2 bg-slate-600 text-white rounded-lg text-sm font-medium hover:bg-slate-700 disabled:opacity-40"
                      >
                        Create Maintenance Request
                      </button>
                    ) : (
                      <>
                        <p className="text-xs text-green-700 dark:text-green-300 bg-green-50 dark:bg-green-500/10 border border-green-200 dark:border-green-500/30 rounded-lg px-3 py-2">
                          ✓ Ticket <span className="font-mono font-semibold">{ticketId}</span> created and queued
                        </p>
                        <button
                          onClick={handleRunWorkflow}
                          disabled={!corridorId}
                          className="w-full px-4 py-2 bg-slate-600 text-white rounded-lg text-sm font-medium hover:bg-slate-700 disabled:opacity-40"
                        >
                          Run Multi-Agent Planning Workflow →
                        </button>
                      </>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* Agent workflow monitor */}
      {stage === 'workflow' && workflow && (
        <AgentWorkflowView
          workflow={workflow}
          onBack={reset}
          decision={decision}
          commitResult={commitResult}
          committing={committing}
          onDecide={handleDecision}
        />
      )}
      {stage === 'workflow' && !workflow && (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-10 text-center text-sm text-gray-500 dark:text-gray-400">
          Agents are working…
        </div>
      )}
    </div>
  );
}

/** Bounding-box overlay. Positions in % of the image's natural size. */
function BBox({ detection }: { detection: Detection }) {
  const [x1, y1, x2, y2] = detection.bbox;
  const color = detection.severity === 'critical' ? '#dc2626' : detection.severity === 'high' ? '#d97706' : '#2563eb';

  return (
    <div
      className="absolute border-2 rounded pointer-events-none"
      style={{
        borderColor: color,
        left: `${(x1 / (detection.natural_width ?? 1)) * 100}%`,
        top: `${(y1 / (detection.natural_height ?? 1)) * 100}%`,
        width: `${((x2 - x1) / (detection.natural_width ?? 1)) * 100}%`,
        height: `${((y2 - y1) / (detection.natural_height ?? 1)) * 100}%`,
      }}
    >
      <span
        className="absolute -top-5 left-0 text-[10px] font-semibold text-white px-1.5 py-0.5 rounded whitespace-nowrap"
        style={{ background: color }}
      >
        {detection.defect_type.replace('_', ' ')}
      </span>
    </div>
  );
}

function AgentWorkflowView({
  workflow,
  onBack,
  decision,
  commitResult,
  committing,
  onDecide,
}: {
  workflow: AgentWorkflow;
  onBack: () => void;
  decision: 'pending' | 'approved' | 'rejected' | null;
  commitResult: { block_id?: string; message: string } | null;
  committing: boolean;
  onDecide: (choice: 'approve' | 'reject') => void;
}) {
  const sel = workflow.selected;
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">Multi-Agent Planning Workflow</h2>
          <p className="text-xs text-gray-500 dark:text-gray-400 font-mono mt-0.5">{workflow.workflow_id}</p>
        </div>
        <button onClick={onBack} className="text-xs px-3 py-1.5 border border-gray-200 dark:border-gray-700 rounded-lg text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700/50">
          New Inspection
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Agent timeline */}
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
          <p className="text-xs font-medium text-gray-400 dark:text-gray-300 uppercase tracking-wider mb-4">Agent Monitor</p>
          <ol className="space-y-0">
            {workflow.log.map((ev) => (
              <li key={ev.seq} className="flex gap-3">
                <div className="flex flex-col items-center">
                  <span className={`w-2.5 h-2.5 rounded-full mt-1.5 ${ev.status === 'error' ? 'bg-red-50 dark:bg-red-500/100' : 'bg-green-50 dark:bg-green-500/100'}`} />
                  {ev.seq < workflow.log.length && <span className="w-px flex-1 bg-gray-200 dark:bg-gray-700" />}
                </div>
                <div className="pb-4">
                  <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                    {AGENT_LABELS[ev.agent] ?? ev.agent}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{ev.message}</p>
                </div>
              </li>
            ))}
            <li className="flex gap-3">
              <div className="flex flex-col items-center">
                <span className="w-2.5 h-2.5 rounded-full mt-1.5 bg-amber-400 animate-pulse" />
              </div>
              <div>
                <p className="text-sm font-medium text-amber-700 dark:text-amber-300">Human Approval Required</p>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Review the recommended block before committing.</p>
              </div>
            </li>
          </ol>
        </div>

        {/* Candidates */}
        <div className="space-y-4">
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
            <p className="text-xs font-medium text-gray-400 dark:text-gray-300 uppercase tracking-wider mb-3">
              Candidate Plans ({workflow.candidates.length})
            </p>
            <div className="space-y-2">
              {workflow.candidates.slice(0, 6).map((c) => (
                <div
                  key={c.plan_id}
                  className={`rounded-lg border px-3 py-2.5 text-xs ${sel?.plan_id === c.plan_id ? 'border-green-300 bg-green-50 dark:bg-green-500/10 dark:border-green-500/40' : 'border-gray-200 dark:border-gray-700'}`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-gray-800 dark:text-gray-200">
                      {minutesToTime(c.block_start_min)}–{minutesToTime(c.block_end_min)} · {c.strategy}
                    </span>
                    <span className="font-mono font-semibold text-gray-700 dark:text-gray-300">U={c.utility}</span>
                  </div>
                  <p className="text-gray-500 dark:text-gray-400 mt-1">
                    impact: {c.operational_impact} · freight: {c.freight_conflicts} · utilization: {(c.utilization * 100).toFixed(0)}%
                    {sel?.plan_id === c.plan_id && <span className="text-green-700 dark:text-green-300 font-medium"> · ★ selected</span>}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {sel && (
            <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
              <p className="text-xs font-medium text-gray-400 dark:text-gray-300 uppercase tracking-wider mb-3">Why this block?</p>
              <ul className="space-y-1.5 text-xs text-gray-700 dark:text-gray-300">
                <li>✓ {workflow.planner.compatible_tasks.length} compatible task(s) in corridor {workflow.planner.corridor_id}</li>
                <li>✓ Departments: {sel.departments.join(', ')}</li>
                <li>✓ Operational impact: {sel.operational_impact.toLowerCase()} ({sel.freight_conflicts} freight conflicts)</li>
                <li>✓ Block utilization: {(sel.utilization * 100).toFixed(0)}%</li>
                <li>✓ Safety constraints satisfied by {sel.strategy} strategy</li>
              </ul>
              <div className="mt-4">
                {decision === null && (
                  <div className="bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30 rounded-lg px-3 py-2.5">
                    <p className="text-xs text-amber-800 dark:text-amber-200 font-medium">Awaiting human approval</p>
                    <p className="text-[11px] text-amber-600 dark:text-amber-300 mt-0.5">
                      Block {minutesToTime(sel.block_start_min)}–{minutesToTime(sel.block_end_min)} · tasks {workflow.tasks_created.join(', ')}
                    </p>
                    <div className="flex gap-2 mt-3">
                      <button
                        onClick={() => onDecide('approve')}
                        disabled={committing}
                        className="flex-1 px-3 py-2 bg-green-600 text-white rounded-lg text-xs font-medium hover:bg-green-700 disabled:opacity-50"
                      >
                        {committing ? 'Committing…' : 'Approve & Commit Block'}
                      </button>
                      <button
                        onClick={() => onDecide('reject')}
                        disabled={committing}
                        className="flex-1 px-3 py-2 border border-red-200 dark:border-red-500/30 text-red-600 dark:text-red-400 rounded-lg text-xs font-medium hover:bg-red-50 dark:hover:bg-red-500/10 disabled:opacity-50"
                      >
                        Reject
                      </button>
                    </div>
                  </div>
                )}
                {decision === 'approved' && (
                  <div className="bg-green-50 dark:bg-green-500/10 border border-green-200 dark:border-green-500/30 rounded-lg px-3 py-2.5">
                    <p className="text-xs text-green-800 dark:text-green-200 font-medium">✓ Plan approved and committed</p>
                    <p className="text-[11px] text-green-700 dark:text-green-300 mt-0.5">{commitResult?.message}</p>
                    {commitResult?.block_id && (
                      <p className="text-[11px] text-green-700 dark:text-green-300 mt-1">
                        Block <span className="font-mono font-semibold">{commitResult.block_id}</span> is now on the{' '}
                        <button
                          onClick={() => window.dispatchEvent(new CustomEvent('app:navigate', { detail: { screen: 'timeline' } }))}
                          className="underline font-medium"
                        >
                          Corridor Timeline
                        </button>
                      </p>
                    )}
                  </div>
                )}
                {decision === 'rejected' && (
                  <div className="bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 rounded-lg px-3 py-2.5">
                    <p className="text-xs text-red-800 dark:text-red-200 font-medium">✗ Plan rejected</p>
                    <p className="text-[11px] text-red-600 dark:text-red-400 mt-0.5">{commitResult?.message}</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
