import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import * as api from './client';
import type { AuthUser } from '../types';

interface AuthContextType {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  // Loading only while a saved token is being validated by /auth/me — no
  // token must resolve IMMEDIATELY to the Login screen. (An earlier version
  // had this inverted: fresh visitors started isLoading=true and the mount
  // effect's early return left it there forever — eternal "Loading…".)
  const [isLoading, setIsLoading] = useState(() => !!api.loadAuthTokens().accessToken);

  useEffect(() => {
    const { accessToken } = api.loadAuthTokens();
    if (!accessToken) return;
    // Hard cap on the loading state: if /auth/me stalls (proxy hiccup, slept
    // machine, etc.) we clear the stale token and show the Login screen
    // instead of spinning on "Loading…" forever.
    const failSafe = window.setTimeout(() => setIsLoading(false), 8000);
    api
      .getCurrentUser()
      .then((u) => setUser(u))
      .catch(() => {
        api.clearAuthTokens();
      })
      .finally(() => {
        window.clearTimeout(failSafe);
        setIsLoading(false);
      });
    return () => window.clearTimeout(failSafe);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await api.login(username, password);
    api.setAuthTokens(res.access_token, res.refresh_token);
    const me = await api.getCurrentUser();
    setUser(me);
  }, []);

  const logout = useCallback(() => {
    api.clearAuthTokens();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
