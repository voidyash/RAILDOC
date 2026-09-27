import { useState, useEffect, useCallback } from 'react';
import { getAuditLogs, getAuditEventTypes, getAuditStats } from '../api/client';
import type { AuditEntry } from '../api/client';

const EVENT_TYPE_LABELS: Record<string, string> = {
  user_login: 'Login',
  user_logout: 'Logout',
  plan_created: 'Plan Created',
  plan_approved: 'Plan Approved',
  plan_rejected: 'Plan Rejected',
  plan_modified: 'Plan Modified',
  weights_updated: 'Weights Updated',
  data_regenerated: 'Data Regenerated',
  optimization_run: 'Optimization Run',
  simulation_run: 'Simulation Run',
  task_priority_calculated: 'Priority Calc',
  block_assigned: 'Block Assigned',
  config_changed: 'Config Changed',
  unauthorized_access: 'Unauthorized',
  rate_limit_exceeded: 'Rate Limited',
};

const EVENT_COLORS: Record<string, string> = {
  user_login: 'bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300',
  user_logout: 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400',
  plan_approved: 'bg-slate-100 text-slate-700 dark:text-slate-300 dark:bg-slate-500/15 dark:text-slate-300',
  plan_created: 'bg-slate-100 text-slate-700 dark:text-slate-300 dark:bg-slate-500/15 dark:text-slate-300',
  optimization_run: 'bg-purple-100 text-purple-700 dark:bg-purple-500/15 dark:text-purple-300',
  simulation_run: 'bg-purple-100 text-purple-700 dark:bg-purple-500/15 dark:text-purple-300',
  weights_updated: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
  config_changed: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
  unauthorized_access: 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300',
  rate_limit_exceeded: 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300',
};

export default function AuditLog() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [eventTypes, setEventTypes] = useState<string[]>([]);

  const [filterType, setFilterType] = useState('');
  const [filterUser, setFilterUser] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterDate, setFilterDate] = useState('');

  const [stats, setStats] = useState<{
    total: number;
    event_counts: Record<string, number>;
    user_counts: Record<string, number>;
    status_counts: Record<string, number>;
  } | null>(null);

  const loadLogs = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = { limit: 300 };
      if (filterType) params.event_type = filterType;
      if (filterUser) params.username = filterUser;
      if (filterStatus) params.status = filterStatus;
      if (filterDate) params.date = filterDate;
      const data = await getAuditLogs(params);
      setEntries(data.entries);
      setTotal(data.total);
    } catch (err) {
      console.error('Failed to load audit logs:', err);
    } finally {
      setLoading(false);
    }
  }, [filterType, filterUser, filterStatus, filterDate]);

  const loadStats = useCallback(async () => {
    try {
      const s = await getAuditStats(filterDate ? { date: filterDate } : {});
      setStats(s);
    } catch {
      // stats are non-critical — silently skip
    }
  }, [filterDate]);

  useEffect(() => {
    getAuditEventTypes()
      .then((d) => setEventTypes(d.event_types))
      .catch(() => {});
  }, []);

  // Fetch on mount / filter change. State updates are confined to async
  // callbacks (react-hooks/set-state-in-effect); the manual Refresh button
  // uses loadLogs/loadStats instead.
  useEffect(() => {
    let active = true;
    const params: Record<string, any> = { limit: 300 };
    if (filterType) params.event_type = filterType;
    if (filterUser) params.username = filterUser;
    if (filterStatus) params.status = filterStatus;
    if (filterDate) params.date = filterDate;
    getAuditLogs(params)
      .then((data) => {
        if (active) {
          setEntries(data.entries);
          setTotal(data.total);
        }
      })
      .catch((err) => console.error('Failed to load audit logs:', err))
      .finally(() => {
        if (active) setLoading(false);
      });
    getAuditStats(filterDate ? { date: filterDate } : {})
      .then((s) => {
        if (active) setStats(s);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [filterType, filterUser, filterStatus, filterDate]);

  const formatTimestamp = (ts: string) => {
    try {
      const d = new Date(ts);
      return d.toLocaleString();
    } catch {
      return ts;
    }
  };

  const clearFilters = () => {
    setFilterType('');
    setFilterUser('');
    setFilterStatus('');
    setFilterDate('');
  };

  const hasFilters = filterType || filterUser || filterStatus || filterDate;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Audit Log</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Security and operation audit trail — admin access only
          </p>
        </div>
        {hasFilters && (
          <button
            onClick={clearFilters}
            className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
          >
            Clear Filters
          </button>
        )}
      </div>

      {stats && (
        <div className="grid grid-cols-4 gap-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <p className="text-sm text-gray-500 dark:text-gray-400">Total Events</p>
            <p className="text-3xl font-bold text-gray-900 dark:text-gray-100 mt-1">{stats.total}</p>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <p className="text-sm text-gray-500 dark:text-gray-400">Successful</p>
            <p className="text-3xl font-bold text-green-600 dark:text-green-400 mt-1">
              {stats.status_counts.success ?? 0}
            </p>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <p className="text-sm text-gray-500 dark:text-gray-400">Failed</p>
            <p className="text-3xl font-bold text-red-600 dark:text-red-400 mt-1">
              {stats.status_counts.failure ?? 0}
            </p>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <p className="text-sm text-gray-500 dark:text-gray-400">Unique Users</p>
            <p className="text-3xl font-bold text-slate-700 dark:text-slate-300 mt-1">
              {Object.keys(stats.user_counts).length}
            </p>
          </div>
        </div>
      )}

      {stats && Object.keys(stats.event_counts).length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-5">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Event Breakdown</h3>
          <div className="flex flex-wrap gap-3">
            {Object.entries(stats.event_counts).map(([type, count]) => (
              <div key={type} className="flex items-center gap-2 text-sm">
                <span
                  className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    EVENT_COLORS[type] || 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
                  }`}
                >
                  {EVENT_TYPE_LABELS[type] || type}
                </span>
                <span className="font-medium text-gray-700 dark:text-gray-300">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500 dark:text-gray-400">Event Type</label>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
            >
              <option value="">All Events</option>
              {eventTypes.map((t) => (
                <option key={t} value={t}>
                  {EVENT_TYPE_LABELS[t] || t}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500 dark:text-gray-400">Username</label>
            <input
              type="text"
              value={filterUser}
              onChange={(e) => setFilterUser(e.target.value)}
              placeholder="e.g. admin"
              className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg w-32"
            />
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500 dark:text-gray-400">Status</label>
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
            >
              <option value="">All</option>
              <option value="success">Success</option>
              <option value="failure">Failure</option>
            </select>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500 dark:text-gray-400">Date</label>
            <input
              type="date"
              value={filterDate}
              onChange={(e) => setFilterDate(e.target.value)}
              className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg"
            />
          </div>
        </div>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/40 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
            Log Entries ({entries.length} of {total})
          </h3>
          <button
            onClick={() => { loadLogs(); loadStats(); }}
            className="text-xs text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:text-slate-200 font-medium"
          >
            ↻ Refresh
          </button>
        </div>

        {loading ? (
          <div className="p-8 text-center text-gray-400 dark:text-gray-300 text-sm">Loading audit logs…</div>
        ) : entries.length === 0 ? (
          <div className="p-8 text-center text-gray-400 dark:text-gray-300 text-sm">
            {hasFilters ? 'No entries match the current filters.' : 'No audit log entries yet.'}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-700/40 border-b border-gray-200 dark:border-gray-700">
                <tr>
                  <th className="text-left px-4 py-2.5 font-medium text-gray-600 dark:text-gray-400">Timestamp</th>
                  <th className="text-left px-4 py-2.5 font-medium text-gray-600 dark:text-gray-400">Event</th>
                  <th className="text-left px-4 py-2.5 font-medium text-gray-600 dark:text-gray-400">User</th>
                  <th className="text-left px-4 py-2.5 font-medium text-gray-600 dark:text-gray-400">Resource</th>
                  <th className="text-left px-4 py-2.5 font-medium text-gray-600 dark:text-gray-400">Action</th>
                  <th className="text-left px-4 py-2.5 font-medium text-gray-600 dark:text-gray-400">Status</th>
                  <th className="text-left px-4 py-2.5 font-medium text-gray-600 dark:text-gray-400">Details</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry, i) => (
                  <tr
                    key={`${entry.timestamp}-${i}`}
                    className="border-b border-gray-100 dark:border-gray-700/60 hover:bg-gray-50 dark:hover:bg-gray-700/50"
                  >
                    <td className="px-4 py-2.5 text-gray-600 dark:text-gray-400 whitespace-nowrap">
                      {formatTimestamp(entry.timestamp)}
                    </td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          EVENT_COLORS[entry.event_type] || 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
                        }`}
                      >
                        {EVENT_TYPE_LABELS[entry.event_type] || entry.event_type}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 font-medium text-gray-800 dark:text-gray-200">{entry.username}</td>
                    <td className="px-4 py-2.5 text-gray-600 dark:text-gray-400 text-xs">
                      {entry.resource_type
                        ? `${entry.resource_type}${entry.resource_id ? `: ${entry.resource_id}` : ''}`
                        : '—'}
                    </td>
                    <td className="px-4 py-2.5 text-gray-600 dark:text-gray-400 text-xs">{entry.action ?? '—'}</td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          entry.status === 'success'
                            ? 'bg-green-100 text-green-700 dark:bg-green-500/15 dark:text-green-300'
                            : 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300'
                        }`}
                      >
                        {entry.status}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-gray-500 dark:text-gray-400 text-xs max-w-48 truncate">
                      {entry.error_message || (entry.details ? JSON.stringify(entry.details) : '—')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
