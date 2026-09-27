import { useState } from 'react';
import { useAuth } from '../api/AuthContext';

export default function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username, password);
    } catch (err: any) {
      // `detail` may be a string, an object (500 shape) or a 422 error
      // array — only strings are valid React children.
      const d = err?.response?.data?.detail;
      setError(
        typeof d === 'string'
          ? d
          : Array.isArray(d)
            ? d.map((x: any) => x?.msg ?? JSON.stringify(x)).join('; ')
            : d && typeof d === 'object'
              ? String(d.message ?? JSON.stringify(d))
              : 'Login failed. Check credentials.'
      );
    } finally {
      setLoading(false);
    }
  };

  const DEMO_USERS = [
    { user: 'admin', pass: 'admin123', role: 'Admin (full access)' },
    { user: 'planner', pass: 'planner123', role: 'Planner' },
    { user: 'operations', pass: 'operations123', role: 'Operations' },
    { user: 'engineer', pass: 'engineer123', role: 'Engineer' },
  ];

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-700/40 dark:bg-gray-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md border border-gray-200 dark:border-gray-700 p-8">
          <div className="text-center mb-8">
            <div className="w-14 h-14 bg-slate-600 rounded-lg flex items-center justify-center text-white font-bold text-xl mx-auto mb-4">
              RD
            </div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">RailDoc</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Railway Maintenance Planning & Scheduling</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
                {error}
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
                className="w-full px-4 py-2.5 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-slate-500 focus:border-slate-500 transition"
                placeholder="e.g. admin"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-4 py-2.5 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-slate-500 focus:border-slate-500 transition"
                placeholder="Enter password"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-slate-600 hover:bg-slate-700 disabled:bg-slate-400 text-white font-medium py-2.5 rounded-lg text-sm transition-colors"
            >
              {loading ? 'Signing in…' : 'Sign In'}
            </button>
          </form>

          <div className="mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
            <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-3">Demo Credentials</p>
            <div className="space-y-2">
              {DEMO_USERS.map((d) => (
                <button
                  key={d.user}
                  onClick={() => {
                    setUsername(d.user);
                    setPassword(d.pass);
                    setError('');
                  }}
                  className="w-full flex items-center justify-between text-left px-3 py-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700/50 border border-gray-100 dark:border-gray-700/60 transition-colors group"
                >
                  <div>
                    <span className="text-sm font-medium text-gray-800 dark:text-gray-200 group-hover:text-slate-700 dark:group-hover:text-slate-300">{d.user}</span>
                    <span className="text-xs text-gray-400 dark:text-gray-300 ml-2">/ {d.pass}</span>
                  </div>
                  <span className="text-xs text-gray-500 dark:text-gray-400">{d.role}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        <p className="text-center text-xs text-gray-400 dark:text-gray-300 mt-4">
          Indian Railways · Decision Support System
        </p>
      </div>
    </div>
  );
}
