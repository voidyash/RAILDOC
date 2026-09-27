import { useState, useEffect } from 'react';
import { listUsers, createUser } from '../api/client';
import type { AuthUser } from '../types';

const ALL_ROLES = ['admin', 'planner', 'operations', 'engineer'];

/** Axios errors carry FastAPI's `detail` as a string, an object (our 500
 * shape) or an array of field errors (422). Only strings are valid React
 * children, so coerce everything else — an array used to crash the page. */
const errMsg = (err: any, fallback: string): string => {
  const d = err?.response?.data?.detail;
  if (typeof d === 'string') return d;
  if (Array.isArray(d)) {
    return d.map((x: any) => (typeof x?.msg === 'string' ? x.msg : JSON.stringify(x))).join('; ');
  }
  if (d && typeof d === 'object') return String(d.message ?? JSON.stringify(d));
  return fallback;
};

const ROLE_BADGE_COLORS: Record<string, string> = {
  admin: 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300',
  planner: 'bg-slate-100 text-slate-700 dark:text-slate-300 dark:bg-slate-500/15 dark:text-slate-300',
  operations: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
  engineer: 'bg-purple-100 text-purple-700 dark:bg-purple-500/15 dark:text-purple-300',
  viewer: 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400',
};

export default function UserManagement() {
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRoles, setNewRoles] = useState<string[]>([]);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const loadUsers = async () => {
    try {
      const data = await listUsers();
      setUsers(data);
    } catch (err: any) {
      setError(errMsg(err, 'Failed to load users'));
    } finally {
      setLoading(false);
    }
  };

  // Initial load: state updates happen in async callbacks, not synchronously
  // in the effect body (react-hooks/set-state-in-effect). loadUsers is kept
  // for the create-user flow below.
  useEffect(() => {
    let active = true;
    listUsers()
      .then((data) => {
        if (active) setUsers(data);
      })
      .catch((err: any) => {
        if (active) setError(errMsg(err, 'Failed to load users'));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setCreating(true);
    try {
      await createUser({ username: newUsername, password: newPassword, roles: newRoles });
      setSuccess(`User "${newUsername}" created successfully`);
      setNewUsername('');
      setNewPassword('');
      setNewRoles([]);
      setShowCreate(false);
      await loadUsers();
    } catch (err: any) {
      setError(errMsg(err, 'Failed to create user'));
    } finally {
      setCreating(false);
    }
  };

  const toggleRole = (role: string) => {
    setNewRoles((prev) =>
      prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role]
    );
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-64 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
        <div className="h-10 w-full bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">User Management</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Manage user accounts and role-based access control
          </p>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-4 py-2 bg-slate-600 text-white rounded-lg hover:bg-slate-700 text-sm font-medium transition-colors"
        >
          {showCreate ? 'Cancel' : '+ Create User'}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-500/10 border border-red-200 text-red-700 dark:text-red-300 text-sm rounded-lg px-4 py-3">
          {error}
        </div>
      )}
      {success && (
        <div className="bg-green-50 dark:bg-green-500/10 border border-green-200 text-green-700 dark:text-green-300 text-sm rounded-lg px-4 py-3">
          {success}
        </div>
      )}

      {showCreate && (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
          <h3 className="text-lg font-bold text-gray-900 dark:text-gray-100 mb-4">Create New User</h3>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Username</label>
                <input
                  type="text"
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  required
                  minLength={3}
                  pattern="^[a-zA-Z0-9_-]+$"
                  className="w-full px-4 py-2.5 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-slate-500 focus:border-slate-500"
                  placeholder="e.g. new_planner"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Password</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  minLength={8}
                  className="w-full px-4 py-2.5 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-slate-500 focus:border-slate-500"
                  placeholder="Min 8 characters"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Roles</label>
              <div className="flex flex-wrap gap-2">
                {ALL_ROLES.map((role) => (
                  <button
                    key={role}
                    type="button"
                    onClick={() => toggleRole(role)}
                    className={`px-3 py-1.5 rounded-full text-sm font-medium border transition-colors ${
                      newRoles.includes(role)
                        ? `${ROLE_BADGE_COLORS[role]} border-current`
                        : 'bg-gray-50 dark:bg-gray-700/40 text-gray-500 dark:text-gray-400 border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-700/50'
                    }`}
                  >
                    {role}
                  </button>
                ))}
              </div>
              <p className="text-xs text-gray-400 dark:text-gray-300 mt-2">
                Select one or more roles. Users also receive viewer access with limited permissions automatically.
              </p>
            </div>

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={creating || newRoles.length === 0}
                className="px-6 py-2.5 bg-slate-600 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50 text-sm font-medium transition-colors"
              >
                {creating ? 'Creating...' : 'Create User'}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-5">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Role Permissions</h3>
        <div className="grid grid-cols-4 gap-3 text-xs">            {ALL_ROLES.map((role) => {
            const perms =
              role === 'admin'
                ? ['All access', 'User management', 'Optimize', 'Approve']
                : role === 'planner'
                ? ['View data', 'Optimize', 'Approve', 'Simulate']
                : role === 'operations'
                ? ['View data', 'Optimize', 'Approve']
                : role === 'engineer'
                ? ['View data', 'Optimize']
                : ['View data only'];  // viewer (auto-assigned)
            return (
              <div key={role} className="p-3 bg-gray-50 dark:bg-gray-700/40 rounded-lg">
                <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${ROLE_BADGE_COLORS[role]} mb-2`}>
                  {role}
                </span>
                <ul className="space-y-1 text-gray-600 dark:text-gray-400">
                  {perms.map((p) => (
                    <li key={p} className="flex items-center gap-1">
                      <span className="text-green-500 dark:text-green-400">✓</span> {p}
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/40">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
            Registered Users ({users.length})
          </h3>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-700/40 border-b border-gray-200 dark:border-gray-700">
            <tr>
              <th className="text-left px-5 py-3 font-medium text-gray-600 dark:text-gray-400">Username</th>
              <th className="text-left px-5 py-3 font-medium text-gray-600 dark:text-gray-400">Roles</th>
              <th className="text-left px-5 py-3 font-medium text-gray-600 dark:text-gray-400">Status</th>
              <th className="text-left px-5 py-3 font-medium text-gray-600 dark:text-gray-400">Created</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.username} className="border-b border-gray-100 dark:border-gray-700/60 hover:bg-gray-50 dark:hover:bg-gray-700/50">
                <td className="px-5 py-3">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center dark:bg-slate-700/60 text-slate-700 dark:text-slate-300 font-bold text-xs uppercase">
                      {u.username.charAt(0)}
                    </div>
                    <span className="font-medium text-gray-900 dark:text-gray-100">{u.username}</span>
                  </div>
                </td>
                <td className="px-5 py-3">
                  <div className="flex flex-wrap gap-1">
                    {u.roles.map((role) => (
                      <span
                        key={role}
                        className={`px-2 py-0.5 rounded-full text-xs font-medium ${ROLE_BADGE_COLORS[role] || 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'}`}
                      >
                        {role}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-5 py-3">
                  <span
                    className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      u.is_active ? 'bg-green-100 text-green-700 dark:text-green-300' : 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300'
                    }`}
                  >
                    {u.is_active ? 'Active' : 'Disabled'}
                  </span>
                </td>
                <td className="px-5 py-3 text-gray-500 dark:text-gray-400">
                  {new Date(u.created_at).toLocaleDateString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
