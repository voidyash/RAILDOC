import { useState, useRef, useEffect } from 'react';
import { useData } from '../api/DataContext';

const HOURS = Array.from({ length: 24 }, (_, i) => i);
const HOUR_WIDTH = 50;
const DEPT_COLORS: Record<string, string> = {
  Engineering: '#64748b',
  'S&T': '#a855f7',
  Traction: '#f59e0b',
};

interface PopoverData {
  type: 'dept' | 'maintenance';
  label: string;
  x: number;
  y: number;
  tasks: any[];
  criticalCount: number;
  totalDuration: number;
  departments?: string[];
  blockId?: string;
  timeRange?: string;
  utilization?: number;
}

export default function CorridorTimeline() {
  const { tasks, trains, blockWindows, blocks, loading } = useData();
  const [selectedCorridor, setSelectedCorridor] = useState('C-07');
  const [popover, setPopover] = useState<PopoverData | null>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setPopover(null);
      }
    };
    if (popover) document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [popover]);

  const timeToX = (time: string): number => {
    const [h, m] = time.split(':').map(Number);
    return (h + m / 60) * HOUR_WIDTH;
  };

  const durationWidth = (start: string, end: string): number => timeToX(end) - timeToX(start);

  const corridorTrains = trains.filter((t) => t.corridor_id === selectedCorridor);
  const corridorWindows = blockWindows.filter((w) => w.corridor_id === selectedCorridor);
  const corridorBlocks = blocks.filter((b) => b.corridor_id === selectedCorridor);
  const corridorTaskIds = new Set(corridorBlocks.flatMap((b) => b.assigned_tasks));
  const corridorTasks = tasks.filter((t) => corridorTaskIds.has(t.task_id));

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-64 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
        <div className="h-64 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Corridor Timeline</h2>
        <select value={selectedCorridor} onChange={(e) => setSelectedCorridor(e.target.value)}
          className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800">
          <option value="C-07">C-07 Delhi-Mumbai</option>
          <option value="C-12">C-12 Howrah-Delhi</option>
          <option value="C-19">C-19 Chennai-Mumbai</option>
        </select>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-x-auto">
        <div className="flex border-b border-gray-200 dark:border-gray-700 sticky top-0 bg-white dark:bg-gray-800 z-10">
          <div className="w-32 shrink-0 px-3 py-2 text-xs font-medium text-gray-500 dark:text-gray-400 border-r border-gray-200 dark:border-gray-700">Category</div>
          <div className="flex" style={{ minWidth: 24 * HOUR_WIDTH }}>
            {HOURS.map((h) => (
              <div key={h} className="text-xs text-gray-400 dark:text-gray-300 py-2 border-r border-gray-100 dark:border-gray-700/60" style={{ width: HOUR_WIDTH }}>
                {h.toString().padStart(2, '0')}:00
              </div>
            ))}
          </div>
        </div>

        <div className="flex border-b border-gray-100 dark:border-gray-700/60">
          <div className="w-32 shrink-0 px-3 py-2 text-xs font-medium text-gray-500 dark:text-gray-400 border-r border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/40">Available Windows</div>
          <div className="relative" style={{ minWidth: 24 * HOUR_WIDTH, height: 32 }}>
            {corridorWindows.map((w) => (
              <div key={w.window_id} className="absolute top-1 bg-green-100 border border-green-300 rounded text-[10px] text-green-700 dark:text-green-300 dark:bg-green-500/20 dark:border-green-500/40 px-1 flex items-center"
                style={{ left: timeToX(w.start_time), width: Math.max(durationWidth(w.start_time, w.end_time), 40), height: 24 }}>
                {w.start_time}-{w.end_time}
              </div>
            ))}
          </div>
        </div>

        <div className="flex border-b border-gray-100 dark:border-gray-700/60">
          <div className="w-32 shrink-0 px-3 py-2 text-xs font-medium text-gray-500 dark:text-gray-400 border-r border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/40">Trains ({corridorTrains.length})</div>
          <div className="relative" style={{ minWidth: 24 * HOUR_WIDTH, height: 32 }}>
            {corridorTrains.slice(0, 20).map((t) => (
              <div key={t.train_id} className="absolute top-1 bg-gray-200 dark:bg-gray-700 rounded text-[10px] text-gray-600 dark:text-gray-400 px-1 flex items-center"
                style={{ left: timeToX(t.scheduled_time), width: 30, height: 24 }}
                title={`${t.train_id} (${t.train_type})`}>
                {t.direction === 'Up' ? '↑' : '↓'}
              </div>
            ))}
          </div>
        </div>

        <div className="flex border-b border-gray-100 dark:border-gray-700/60">
          <div className="w-32 shrink-0 px-3 py-2 text-xs font-medium text-gray-500 dark:text-gray-400 border-r border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/40">Maintenance Blocks</div>
          <div className="relative" style={{ minWidth: 24 * HOUR_WIDTH, height: 36 }}>
            {corridorBlocks.map((b) => (
              <div key={b.block_id} className="absolute top-1 bg-slate-500 border border-slate-600 rounded text-[10px] text-white px-1 flex items-center cursor-pointer hover:bg-slate-600"
                style={{ left: timeToX(b.start_time), width: Math.max(durationWidth(b.start_time, b.end_time), 50), height: 28 }}
                title={`${b.block_id}: ${b.assigned_tasks.join(', ')}`}
                onClick={(e) => {
                  e.stopPropagation();
                  setPopover({
                    type: 'maintenance',
                    label: b.block_id,
                    x: e.clientX,
                    y: e.clientY,
                    tasks: [],
                    criticalCount: 0,
                    totalDuration: b.duration_minutes,
                    departments: b.departments,
                    blockId: b.block_id,
                    timeRange: `${b.start_time} - ${b.end_time}`,
                    utilization: b.utilization,
                  });
                }}>
                {b.block_id}
              </div>
            ))}
          </div>
        </div>

        {(['Engineering', 'S&T', 'Traction'] as const).map((dept) => {
          const deptTasks = corridorTasks.filter((t) => t.department === dept);
          const criticalCount = deptTasks.filter((t) => t.priority_score >= 70).length;
          const totalDuration = deptTasks.reduce((s, t) => s + t.estimated_duration_minutes, 0);
          return (
            <div key={dept} className="flex border-b border-gray-100 dark:border-gray-700/60">
              <div className="w-32 shrink-0 px-3 py-2 text-xs font-medium border-r border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/40 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700/50 transition-colors"
                style={{ color: DEPT_COLORS[dept] }}
                onClick={(e) => {
                  e.stopPropagation();
                  setPopover({
                    type: 'dept',
                    label: dept,
                    x: e.clientX,
                    y: e.clientY,
                    tasks: deptTasks.slice(0, 8),
                    criticalCount,
                    totalDuration,
                  });
                }}>
                {dept} ({deptTasks.length})
              </div>
              <div className="relative" style={{ minWidth: 24 * HOUR_WIDTH, height: 36 }}>
                {deptTasks.slice(0, 10).map((t) => {
                  const startHour = 2 + Math.abs(t.task_id.charCodeAt(t.task_id.length - 1) % 20);
                  const startTime = `${startHour.toString().padStart(2, '0')}:00`;
                  const endMin = t.estimated_duration_minutes;
                  const endHour = startHour + Math.floor(endMin / 60);
                  const endMinute = endMin % 60;
                  const endTime = `${endHour.toString().padStart(2, '0')}:${endMinute.toString().padStart(2, '0')}`;
                  return (
                    <div key={t.task_id} className="absolute top-1 rounded text-[10px] text-white px-1 flex items-center opacity-80 hover:opacity-100 cursor-pointer"
                      style={{ left: timeToX(startTime), width: Math.max(durationWidth(startTime, endTime), 20), height: 28, backgroundColor: DEPT_COLORS[dept] }}
                      title={`${t.task_id}: ${t.task_type}`}>
                      {t.task_id}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex gap-4 text-xs text-gray-500 dark:text-gray-400">
        <div className="flex items-center gap-1"><div className="w-3 h-3 bg-green-200 border border-green-300 rounded" />Available Windows</div>
        <div className="flex items-center gap-1"><div className="w-3 h-3 bg-slate-500 rounded" />Maintenance Blocks</div>
        <div className="flex items-center gap-1"><div className="w-3 h-3 bg-gray-200 dark:bg-gray-700 rounded" />Train Movements</div>
        <div className="flex items-center gap-1"><div className="w-3 h-3 rounded" style={{ backgroundColor: DEPT_COLORS.Engineering }} />Engineering</div>
        <div className="flex items-center gap-1"><div className="w-3 h-3 rounded" style={{ backgroundColor: DEPT_COLORS['S&T'] }} />S&T</div>
        <div className="flex items-center gap-1"><div className="w-3 h-3 rounded" style={{ backgroundColor: DEPT_COLORS.Traction }} />Traction</div>
      </div>

      {popover && (
        <div ref={popoverRef}
          className="fixed z-50 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 p-4 w-72"
          style={{ left: Math.min(popover.x + 10, window.innerWidth - 300), top: Math.min(popover.y - 10, window.innerHeight - 300) }}>
          <div className="flex items-center justify-between mb-3">
            <h4 className="font-bold text-gray-900 dark:text-gray-100 text-sm">
              {popover.type === 'dept' ? popover.label : popover.blockId}
            </h4>
            <button onClick={() => setPopover(null)} className="text-gray-400 dark:text-gray-300 hover:text-gray-600 dark:text-gray-400 text-lg leading-none">×</button>
          </div>

          {popover.type === 'dept' ? (
            <>
              <div className="grid grid-cols-2 gap-2 mb-3">
                <div className="bg-gray-50 dark:bg-gray-700/40 rounded-lg p-2 text-center">
                  <div className="text-lg font-bold" style={{ color: DEPT_COLORS[popover.label] }}>{popover.tasks.length}</div>
                  <div className="text-[10px] text-gray-500 dark:text-gray-400">Tasks Shown</div>
                </div>
                <div className="bg-gray-50 dark:bg-gray-700/40 rounded-lg p-2 text-center">
                  <div className="text-lg font-bold text-red-600 dark:text-red-400">{popover.criticalCount}</div>
                  <div className="text-[10px] text-gray-500 dark:text-gray-400">Critical</div>
                </div>
              </div>
              <div className="text-[10px] text-gray-500 dark:text-gray-400 mb-2">
                Total Duration: {popover.totalDuration} min
              </div>
              {popover.tasks.length > 0 && (
                <div className="space-y-1 mb-3 max-h-32 overflow-y-auto">
                  {popover.tasks.map((t: any) => (
                    <div key={t.task_id} className="flex items-center justify-between text-[10px] p-1.5 bg-gray-50 dark:bg-gray-700/40 rounded">
                      <span className="font-medium text-gray-700 dark:text-gray-300">{t.task_id}</span>
                      <span className="text-gray-500 dark:text-gray-400">{t.task_type} · {t.estimated_duration_minutes}min</span>
                    </div>
                  ))}
                </div>
              )}
              <button onClick={() => { window.dispatchEvent(new CustomEvent('app:navigate', { detail: { screen: 'queue' } })); setPopover(null); }}
                className="w-full px-3 py-1.5 text-xs font-medium rounded-lg text-white transition-colors"
                style={{ backgroundColor: DEPT_COLORS[popover.label] }}>
                View Full Queue →
              </button>
            </>
          ) : (
            <>
              {popover.departments && (
                <div className="flex gap-1.5 mb-3 flex-wrap">
                  {popover.departments.map((d) => (
                    <span key={d} className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 text-slate-700 dark:text-slate-300 dark:bg-slate-500/15 dark:text-slate-300">{d}</span>
                  ))}
                </div>
              )}
              <div className="grid grid-cols-2 gap-2 mb-3 text-[10px]">
                <div className="bg-gray-50 dark:bg-gray-700/40 rounded-lg p-2"><span className="text-gray-500 dark:text-gray-400">Time:</span> <span className="font-medium text-gray-700 dark:text-gray-300">{popover.timeRange}</span></div>
                <div className="bg-gray-50 dark:bg-gray-700/40 rounded-lg p-2"><span className="text-gray-500 dark:text-gray-400">Duration:</span> <span className="font-medium text-gray-700 dark:text-gray-300">{popover.totalDuration}min</span></div>
                <div className="bg-gray-50 dark:bg-gray-700/40 rounded-lg p-2"><span className="text-gray-500 dark:text-gray-400">Utilization:</span> <span className="font-medium text-gray-700 dark:text-gray-300">{popover.utilization}%</span></div>
                <div className="bg-gray-50 dark:bg-gray-700/40 rounded-lg p-2"><span className="text-gray-500 dark:text-gray-400">Corridor:</span> <span className="font-medium text-gray-700 dark:text-gray-300">{selectedCorridor}</span></div>
              </div>
              <button onClick={() => { window.dispatchEvent(new CustomEvent('app:navigate', { detail: { screen: 'blocks' } })); setPopover(null); }}
                className="w-full px-3 py-1.5 bg-slate-800 text-white text-xs font-medium rounded-lg hover:bg-slate-700 transition-colors">
                View Full Block Plan →
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
