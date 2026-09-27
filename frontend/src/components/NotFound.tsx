export default function NotFound() {
  const goHome = () =>
    window.dispatchEvent(new CustomEvent('app:navigate', { detail: { screen: 'dashboard' } }));

  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center text-center px-4">
      <p className="text-6xl font-bold text-gray-200 dark:text-gray-600 tracking-tight">404</p>
      <h2 className="text-xl font-semibold text-gray-700 dark:text-gray-300 mt-4">Page not found</h2>
      <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 max-w-sm">
        The page you are looking for does not exist or may have been moved.
      </p>
      <button
        onClick={goHome}
        className="mt-6 px-4 py-2 bg-slate-600 text-white rounded-lg hover:bg-slate-700 text-sm font-medium transition-colors"
      >
        Back to Dashboard
      </button>
    </div>
  );
}
