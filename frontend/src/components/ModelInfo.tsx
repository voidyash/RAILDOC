import { useEffect, useState } from 'react';
import {
  getModelInfo,
  getSamplePredictions,
  type ModelTrainingInfo,
  type SamplePrediction,
} from '../api/client';

const MODEL_LABELS: Record<string, string> = {
  raildoc_detector: 'Rail Infrastructure Detector',
};

const METRIC_LABELS: Record<string, string> = {
  mAP50: 'mAP @ 50',
  mAP50_95: 'mAP @ 50-95',
  precision: 'Precision',
  recall: 'Recall',
};

// Fallback architecture when the backend doesn't report one; normally the
// kind comes from /api/inspection/models or the args.yaml base model.
const ARCH_LABELS: Record<string, string> = {
  raildoc_detector: 'YOLO26n-det',
};

function pct(v: number | null | undefined): string {
  if (v == null) return '—';
  return v <= 1 ? `${(v * 100).toFixed(1)}%` : v.toFixed(3);
}

/** Prefer the backend-reported kind, then args.yaml base model, then fallback. */
function archLabel(key: string, kind: string | undefined, baseModel: unknown): string {
  const raw = (typeof kind === 'string' && kind
    ? kind
    : typeof baseModel === 'string' && baseModel
      ? baseModel.replace(/\.pt$/i, '')
      : ARCH_LABELS[key] ?? '')
    .replace(/\.pt$/i, '');
  return raw.replace(/^yolo/i, 'YOLO');
}

export default function ModelInfo() {
  const [info, setInfo] = useState<Record<string, { available: boolean; error: string | null; kind?: string; training?: ModelTrainingInfo }> | null>(null);
  const [samples, setSamples] = useState<SamplePrediction[]>([]);
  const [artifacts, setArtifacts] = useState<{ key: string; name: string; label: string }[]>([]);
  const [loadingSamples, setLoadingSamples] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getModelInfo()
      .then((d) => {
        setInfo(d);
        // collect available artifact images
        const arts: { key: string; name: string; label: string }[] = [];
        for (const [key, m] of Object.entries(d)) {
          if (!m.training?.artifacts) continue;
          if (m.training.artifacts.results_png) {
            arts.push({ key, name: 'results.png', label: `${MODEL_LABELS[key] ?? key} — training curves` });
          }
          if (m.training.artifacts.confusion_matrix) {
            arts.push({ key, name: 'confusion_matrix.png', label: `${MODEL_LABELS[key] ?? key} — confusion matrix` });
          }
        }
        setArtifacts(arts);
      })
      .catch(() => setError('Failed to load model info'));
  }, []);

  const loadSamples = () => {
    setLoadingSamples(true);
    setError(null);
    getSamplePredictions()
      .then((d) => setSamples(d.samples))
      .catch(() => setError('Sample inference failed — is the model available?'))
      .finally(() => setLoadingSamples(false));
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">Model Info</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Locally-trained Ultralytics YOLO26 unified detector (light_pole + tracks_fault) — training metrics, configuration, and live sample predictions.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">{error}</div>
      )}

      {/* Model cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {info && Object.entries(info).map(([key, m]) => {
          const t = m.training;
          return (
            <div key={key} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{MODEL_LABELS[key] ?? key}</h3>
                  <span
                    title={typeof t?.config?.base_model === 'string' ? `Trained from ${t.config.base_model}` : 'Model architecture'}
                    className="px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-slate-100 text-slate-600 dark:bg-slate-500/20 dark:text-slate-300 whitespace-nowrap"
                  >
                    {archLabel(key, m.kind, t?.config?.base_model)}
                  </span>
                </div>
                <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium whitespace-nowrap ${m.available ? 'bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300' : 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300'}`}>
                  {m.available ? 'Ready' : 'Not loaded'}
                </span>
              </div>

              {t?.metrics && (
                <dl className="grid grid-cols-3 gap-3 mt-4">
                  {Object.entries(t.metrics).map(([k, v]) => (
                    <div key={k} className="bg-gray-50 dark:bg-gray-700/40 rounded-lg px-3 py-2">
                      <dt className="text-[10px] text-gray-400 dark:text-gray-300 uppercase tracking-wide">{METRIC_LABELS[k] ?? k}</dt>
                      <dd className="text-lg font-bold text-gray-900 dark:text-gray-100">{pct(v as number)}</dd>
                    </div>
                  ))}
                </dl>
              )}

              {t?.config && (
                <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-3">
                  {String(t.config.epochs ?? '')} epochs · imgsz {String(t.config.imgsz ?? '')}
                  {t.epochs_trained != null && ` · ${t.epochs_trained} epochs completed`}
                  {t.best_epoch != null && ` · best epoch ${t.best_epoch}`}
                </p>
              )}
              {t?.config?.dataset != null && (
                <p className="text-[11px] text-gray-400 dark:text-gray-300 mt-0.5">dataset: {String(t.config.dataset)}</p>
              )}
              {!m.available && m.error && (
                <p className="text-[11px] text-red-500 dark:text-red-400 mt-2">{m.error}</p>
              )}
            </div>
          );
        })}
      </div>

      {/* Training artifacts */}
      {artifacts.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
          <p className="text-xs font-medium text-gray-400 dark:text-gray-300 uppercase tracking-wider mb-3">Training Artifacts</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {artifacts.map((a) => (
              <figure key={`${a.key}-${a.name}`}>
                <img
                  src={`/api/inspection/models/${a.key}/artifact/${a.name}`}
                  alt={a.label}
                  className="w-full rounded-lg border border-gray-100 dark:border-gray-700/60"
                />
                <figcaption className="text-[11px] text-gray-500 dark:text-gray-400 mt-1">{a.label}</figcaption>
              </figure>
            ))}
          </div>
        </div>
      )}

      {/* Live sample predictions */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs font-medium text-gray-400 dark:text-gray-300 uppercase tracking-wider">Live Sample Predictions</p>
          <button
            onClick={loadSamples}
            disabled={loadingSamples}
            className="px-3 py-1.5 bg-slate-600 text-white rounded-lg text-xs font-medium hover:bg-slate-700 disabled:opacity-50"
          >
            {loadingSamples ? 'Running inference…' : 'Run sample inference'}
          </button>
        </div>
        {samples.length === 0 && !loadingSamples && (
          <p className="text-xs text-gray-400 dark:text-gray-300">Runs the unified detector on bundled dataset frames — takes a few seconds.</p>
        )}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-2">
          {samples.map((s, i) => (
            <div key={i} className="border border-gray-100 dark:border-gray-700/60 rounded-lg overflow-hidden">
              {s.annotated_image_b64 ? (
                <img src={`data:image/jpeg;base64,${s.annotated_image_b64}`} alt={s.source} className="w-full" />
              ) : (
                <div className="h-40 bg-gray-50 dark:bg-gray-700/40 flex items-center justify-center text-xs text-gray-400 dark:text-gray-300">
                  {s.error ? 'inference error' : 'no visualization'}
                </div>
              )}
              <div className="p-3">
                <p className="text-[11px] font-mono text-gray-500 dark:text-gray-400 truncate">{s.source}</p>
                {s.detections && s.detections.length > 0 ? (
                  s.detections.map((d, j) => (
                    <p key={j} className="text-xs mt-1">
                      <span className="font-semibold text-gray-800 dark:text-gray-200">{d.defect_type.replace(/_/g, ' ')}</span>{' '}
                      <span className="text-gray-500 dark:text-gray-400">{(d.confidence * 100).toFixed(0)}% · {d.severity}</span>
                    </p>
                  ))
                ) : (
                  <p className="text-xs mt-1 text-green-600 dark:text-green-400 font-medium">✓ nothing detected</p>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
