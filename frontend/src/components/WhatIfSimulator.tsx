import { useState } from 'react';
import { useData } from '../api/DataContext';
import { runSimulation } from '../api/client';

export default function WhatIfSimulator() {
  const { loading: ctxLoading } = useData();
  const [scenarioName, setScenarioName] = useState('Custom Scenario');
  const [blockDuration, setBlockDuration] = useState(60);
  const [trafficChange, setTrafficChange] = useState(0);
  const [resourceChange, setResourceChange] = useState(0);
  const [result, setResult] = useState<any>(null);
  const [baseline, setBaseline] = useState<any>(null);
  const [running, setRunning] = useState(false);

  const runScenario = async () => {
    setRunning(true);
    try {
      const data = await runSimulation({
        scenario_name: scenarioName,
        block_duration_override: blockDuration,
        // Units differ by backend contract: traffic is a FRACTION of current
        // trains (backend multiplies the count directly), resource is a
        // PERCENT (backend computes 1 + change/100). Dividing resource by 100
        // here turned the "Resource Shortage" -30% preset into -0.3%.
        traffic_forecast_change: trafficChange / 100,
        resource_availability_change: resourceChange,
      });
      setResult(data);
    } catch (err) { console.error('Simulation failed:', err); }
    finally { setRunning(false); }
  };

  const loadBaseline = async () => {
    try { setBaseline(await runSimulation({})); }
    catch (err) { console.error(err); }
  };

  const presets = [
    { name: 'Extended Block Duration', blockDuration: 90, trafficChange: 0, resourceChange: 0, description: 'Increase block window from 60 to 90 minutes' },
    { name: 'Heavy Freight Traffic', blockDuration: 60, trafficChange: 20, resourceChange: 0, description: '20% increase in goods train movements' },
    { name: 'Resource Shortage', blockDuration: 60, trafficChange: 0, resourceChange: -30, description: '30% reduction in available maintenance resources' },
    { name: 'Combined Stress', blockDuration: 45, trafficChange: 30, resourceChange: -20, description: 'Shorter blocks, more traffic, fewer resources' },
  ];

  if (ctxLoading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-64 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
        <div className="grid grid-cols-3 gap-6">
          <div className="h-96 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse" />
          <div className="col-span-2 h-96 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">What-If Simulator</h2>
        <button onClick={loadBaseline} className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 text-sm font-medium">Load Baseline</button>
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="space-y-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-5">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Scenario Parameters</h3>
            <div className="space-y-4">
              <div>
                <label className="text-xs text-gray-500 dark:text-gray-400 block mb-1">Scenario Name</label>
                <input type="text" value={scenarioName} onChange={(e) => setScenarioName(e.target.value)} className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg" />
              </div>
              <div>
                <label className="text-xs text-gray-500 dark:text-gray-400 block mb-1">Block Duration: {blockDuration} min</label>
                <input type="range" min={30} max={180} step={15} value={blockDuration} onChange={(e) => setBlockDuration(Number(e.target.value))} className="w-full" />
                <div className="flex justify-between text-xs text-gray-400 dark:text-gray-300"><span>30min</span><span>180min</span></div>
              </div>
              <div>
                <label className="text-xs text-gray-500 dark:text-gray-400 block mb-1">Traffic Forecast: {trafficChange > 0 ? '+' : ''}{trafficChange}%</label>
                <input type="range" min={-50} max={50} step={5} value={trafficChange} onChange={(e) => setTrafficChange(Number(e.target.value))} className="w-full" />
                <div className="flex justify-between text-xs text-gray-400 dark:text-gray-300"><span>-50%</span><span>+50%</span></div>
              </div>
              <div>
                <label className="text-xs text-gray-500 dark:text-gray-400 block mb-1">Resource Availability: {resourceChange > 0 ? '+' : ''}{resourceChange}%</label>
                <input type="range" min={-50} max={50} step={5} value={resourceChange} onChange={(e) => setResourceChange(Number(e.target.value))} className="w-full" />
                <div className="flex justify-between text-xs text-gray-400 dark:text-gray-300"><span>-50%</span><span>+50%</span></div>
              </div>
              <button onClick={runScenario} disabled={running}
                className="w-full px-4 py-2 bg-slate-600 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50 text-sm font-medium">
                {running ? 'Running...' : 'Run Scenario'}
              </button>
            </div>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-5">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Quick Presets</h3>
            <div className="space-y-2">
              {presets.map((p) => (
                <button key={p.name} onClick={() => { setBlockDuration(p.blockDuration); setTrafficChange(p.trafficChange); setResourceChange(p.resourceChange); setScenarioName(p.name); }}
                  className="w-full text-left p-2 rounded-lg bg-gray-50 dark:bg-gray-700/40 hover:bg-gray-100 dark:hover:bg-gray-700/50 transition-colors">
                  <div className="text-sm font-medium text-gray-700 dark:text-gray-300">{p.name}</div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">{p.description}</div>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="col-span-2 space-y-4">
          {result ? (
            <>
              {baseline && (
                <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-5">
                  <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Baseline vs Scenario</h3>
                  <div className="grid grid-cols-4 gap-4">
                    {[
                      { label: 'Planned Blocks', baseline: baseline.metrics.planned_blocks, scenario: result.metrics.planned_blocks },
                      { label: 'Train Conflicts', baseline: baseline.metrics.train_conflicts, scenario: result.metrics.train_conflicts },
                      { label: 'Block Utilization', baseline: baseline.metrics.block_utilization, scenario: result.metrics.block_utilization, suffix: '%' },
                      { label: 'Downtime (min)', baseline: baseline.metrics.total_downtime_minutes, scenario: result.metrics.total_downtime_minutes },
                    ].map((item) => {
                      const diff = item.scenario - item.baseline;
                      const improved = item.label === 'Block Utilization' ? diff > 0 : diff < 0;
                      return (
                        <div key={item.label} className="text-center">
                          <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">{item.label}</div>
                          <div className="text-lg font-bold text-gray-900 dark:text-gray-100">{item.baseline}{item.suffix||''} → {item.scenario}{item.suffix||''}</div>
                          <div className={`text-xs font-medium ${improved ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>{diff > 0 ? '+' : ''}{diff.toFixed(1)}{item.suffix||''}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
              <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-5">
                <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Scenario Results: {scenarioName}</h3>
                <div className="grid grid-cols-4 gap-4">
                  <div className="bg-slate-100 rounded-lg dark:bg-slate-700/60 p-3 text-center"><div className="text-2xl font-bold text-slate-700 dark:text-slate-300">{result.metrics.planned_blocks}</div><div className="text-xs text-gray-500 dark:text-gray-400">Blocks</div></div>
                  <div className="bg-green-50 dark:bg-green-500/10 rounded-lg p-3 text-center"><div className="text-2xl font-bold text-green-600 dark:text-green-400">{result.metrics.block_utilization}%</div><div className="text-xs text-gray-500 dark:text-gray-400">Utilization</div></div>
                  <div className="bg-amber-50 dark:bg-amber-500/10 rounded-lg p-3 text-center"><div className="text-2xl font-bold text-amber-600">{result.metrics.train_conflicts}</div><div className="text-xs text-gray-500 dark:text-gray-400">Conflicts</div></div>
                  <div className="bg-purple-50 dark:bg-purple-500/10 rounded-lg p-3 text-center"><div className="text-2xl font-bold text-purple-600">{result.metrics.multi_dept_blocks}</div><div className="text-xs text-gray-500 dark:text-gray-400">Multi-Dept</div></div>
                </div>
              </div>
              <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-5">
                <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Generated Blocks ({result.blocks.length})</h3>
                <div className="space-y-2 max-h-80 overflow-y-auto">
                  {result.blocks.map((block: any) => (
                    <div key={block.block_id} className="p-3 bg-gray-50 dark:bg-gray-700/40 rounded-lg">
                      <div className="flex items-center justify-between">
                        <div><span className="font-medium text-gray-900 dark:text-gray-100">{block.block_id}</span><span className="text-xs text-gray-500 dark:text-gray-400 ml-2">{block.corridor_id}</span></div>
                        <div className="text-sm text-gray-600 dark:text-gray-400">{block.start_time} - {block.end_time}</div>
                      </div>
                      <div className="flex items-center gap-2 mt-1 text-xs text-gray-500 dark:text-gray-400">
                        <span>{block.departments.join(' + ')}</span><span>·</span><span>{block.assigned_tasks.length} tasks</span><span>·</span><span>{block.utilization}% utilized</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-12 text-center text-gray-400 dark:text-gray-300">
              <p>Adjust parameters and run a scenario to see results</p>
              <p className="text-sm mt-2">Compare against baseline to see the impact of your changes</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
