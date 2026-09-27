import { useState, useEffect } from 'react';
import { useAuth, AuthProvider } from './api/AuthContext';
import { useTheme } from './ThemeContext';
import { DataProvider } from './api/DataContext';
import Dashboard from './components/Dashboard';
import MaintenanceQueue from './components/MaintenanceQueue';
import CorridorTimeline from './components/CorridorTimeline';
import BlockPlan from './components/BlockPlan';
import Explainability from './components/Explainability';
import WhatIfSimulator from './components/WhatIfSimulator';
import BeforeAfter from './components/BeforeAfter';
import UserManagement from './components/UserManagement';
import AuditLog from './components/AuditLog';
import Inspection from './components/Inspection';
import RailMap from './components/RailMap';
import ModelInfo from './components/ModelInfo';
import NotFound from './components/NotFound';
import Login from './components/Login';

type Screen = | 'dashboard' | 'inspection' | 'map' | 'models' | 'queue' | 'timeline' | 'blocks' | 'explain' | 'simulate' | 'comparison' | 'users' | 'audit';

function hasRole(userRoles: string[], ...required: string[]): boolean {
  return required.some((r) => userRoles.includes(r));
}

const SCREEN_IDS: Screen[] = ['dashboard', 'inspection', 'map', 'models', 'queue', 'timeline', 'blocks', 'explain', 'simulate', 'comparison', 'users', 'audit'];

const NAV_ITEMS: { id: Screen; label: string; minRole?: string[] }[] = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'inspection', label: 'Defect Inspection' },
  { id: 'map', label: 'Map View' },
  { id: 'models', label: 'Model Info' },
  { id: 'queue', label: 'Maintenance Queue' },
  { id: 'timeline', label: 'Corridor Timeline' },
  { id: 'blocks', label: 'Block Plan' },
  { id: 'explain', label: 'Explainability' },
  { id: 'simulate', label: 'What-If Simulator', minRole: ['planner', 'admin', 'operations', 'engineer'] },
  { id: 'comparison', label: 'Before/After' },
  { id: 'users', label: 'User Management', minRole: ['admin'] },
  { id: 'audit', label: 'Audit Log', minRole: ['admin'] },
];

function AppContent() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const userRoles = user?.roles ?? [];
  const [screen, setScreen] = useState<Screen>('dashboard');
  const [currentTime, setCurrentTime] = useState(new Date());

  const formattedTime = new Intl.DateTimeFormat('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    timeZone: 'Asia/Kolkata',
  }).format(currentTime);

  const formattedDate = new Intl.DateTimeFormat('en-IN', {
    weekday: 'short',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: 'Asia/Kolkata',
  }).format(currentTime);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => window.clearInterval(timer);
  }, []);
  useEffect(() => {
    const handler = (e: Event) => {
      const customEvent = e as CustomEvent;
      if (customEvent.detail?.screen) {
        setScreen(customEvent.detail.screen);
      }
    };
    window.addEventListener('app:navigate', handler);
    return () => window.removeEventListener('app:navigate', handler);
  }, []);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-slate-600 rounded-lg flex items-center justify-center text-white font-bold text-sm">
              RD
            </div>
            <div>
              <h1 className="text-lg font-bold text-gray-900 dark:text-gray-100">
                RailDoc
              </h1>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Railway Maintenance Planning & Scheduling
              </p>
            </div>
          </div>
          <div className="flex items-center gap-5">

            {/* Live Clock */}
            <div
              className="hidden sm:block text-right border-r border-gray-200 dark:border-gray-700 pr-5"
              aria-label="Current date and time"
            >
              <p className="text-sm font-semibold text-gray-900 dark:text-gray-100 tabular-nums">
                {formattedTime}
              </p>

              <p className="text-[11px] text-gray-500 dark:text-gray-400">
                {formattedDate} • IST
              </p>
            </div>

            {/* Theme Toggle */}
            <button
              onClick={toggleTheme}
              title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
              aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
              className="w-9 h-9 flex items-center justify-center text-base border border-gray-200 dark:border-gray-700 rounded-lg text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
            >
              {theme === 'dark' ? '☀️' : '🌙'}
            </button>

            {/* User */}
            <div className="text-right">
              <p className="text-sm font-medium text-gray-800 dark:text-gray-200">
                {user?.username}
              </p>

              <p className="text-xs text-gray-500 dark:text-gray-400">
                {user?.roles[0]}
              </p>
            </div>

            {/* Sign Out */}
            <button
              onClick={logout}
              className="text-xs text-gray-500 dark:text-gray-400 hover:text-red-600 dark:hover:text-red-400 border border-gray-200 dark:border-gray-700 hover:border-red-200 dark:hover:border-red-500/40 px-3 py-1.5 rounded-lg transition-colors"
            >
              Sign Out
            </button>

          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto flex">
        <nav className="w-56 min-h-[calc(100vh-56px)] bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 p-3">
          <div className="space-y-1">
            {NAV_ITEMS.filter((item) => !item.minRole || hasRole(userRoles, ...item.minRole)).map((item) => (
              <button
                key={item.id}
                onClick={() => setScreen(item.id)}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${screen === item.id
                    ? 'bg-slate-100 text-slate-900 dark:bg-slate-700/60 dark:text-slate-100 font-medium'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700/50'
                  }`}
              >
                {item.label}
              </button>
            ))}
          </div>

          <div className="mt-4 px-3">
            <p className="text-[10px] font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-1.5">Your Roles</p>
            <div className="flex flex-wrap gap-1">
              {userRoles.map((role) => (
                <span
                  key={role}
                  className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${role === 'admin' ? 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300' :
                      role === 'planner' ? 'bg-slate-100 text-slate-700 dark:bg-slate-500/15 dark:text-slate-300' :
                        role === 'operations' ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300' :
                          role === 'engineer' ? 'bg-purple-100 text-purple-700 dark:bg-purple-500/15 dark:text-purple-300' :
                            'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
                    }`}
                >
                  {role}
                </span>
              ))}
            </div>
          </div>

          <div className="mt-6 p-3 bg-amber-50 rounded-lg border border-amber-200 dark:bg-amber-500/10 dark:border-amber-500/30">
            <p className="text-xs text-amber-800 dark:text-amber-200 font-medium">Demo Mode</p>
            <p className="text-xs text-amber-600 dark:text-amber-300 mt-1">
              Using synthetic data for 3 departments, 150 assets, 300 tasks
            </p>
          </div>
        </nav>

        <main className="flex-1 p-6 overflow-auto" style={{ maxHeight: 'calc(100vh - 56px)' }}>
          {screen === 'dashboard' && <Dashboard />}
          {screen === 'inspection' && <Inspection />}
          {screen === 'map' && <RailMap />}
          {screen === 'models' && <ModelInfo />}
          {screen === 'queue' && <MaintenanceQueue />}
          {screen === 'timeline' && <CorridorTimeline />}
          {screen === 'blocks' && <BlockPlan />}
          {screen === 'explain' && <Explainability />}
          {screen === 'simulate' && hasRole(userRoles, 'planner', 'admin', 'operations', 'engineer') && <WhatIfSimulator />}
          {screen === 'comparison' && <BeforeAfter />}
          {screen === 'users' && hasRole(userRoles, 'admin') && <UserManagement />}
          {screen === 'audit' && hasRole(userRoles, 'admin') && <AuditLog />}
          {!SCREEN_IDS.includes(screen) && <NotFound />}
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppGate />
    </AuthProvider>
  );
}

function AppGate() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-10 h-10 bg-slate-600 rounded-lg flex items-center justify-center text-white font-bold text-sm mx-auto mb-3 animate-pulse">
            RD
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400">Loading…</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Login />;
  }

  return (
    <DataProvider>
      <AppContent />
    </DataProvider>
  );
}
