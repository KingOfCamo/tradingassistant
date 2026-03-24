import { useState, useCallback, useEffect } from 'react';

interface User {
  id: string;
  username: string;
}

interface AuthState {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

let memoryToken: string | null = null;

export function useAuth() {
  const [state, setState] = useState<AuthState>({
    token: memoryToken,
    user: null,
    isAuthenticated: !!memoryToken,
    isLoading: true,
  });

  const setToken = useCallback((token: string | null, user: User | null) => {
    memoryToken = token;
    setState({
      token,
      user,
      isAuthenticated: !!token,
      isLoading: false,
    });
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Login failed' }));
      throw new Error(err.detail ?? 'Login failed');
    }
    const data = await res.json();
    setToken(data.access_token, { id: '', username });
    return data;
  }, [setToken]);

  const logout = useCallback(async () => {
    try {
      await fetch('/api/auth/logout', {
        method: 'POST',
        headers: memoryToken ? { Authorization: `Bearer ${memoryToken}` } : {},
        credentials: 'include',
      });
    } catch {
      // best-effort
    }
    setToken(null, null);
  }, [setToken]);

  const refresh = useCallback(async () => {
    try {
      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) {
        setToken(null, null);
        return;
      }
      const res = await fetch('/api/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!res.ok) {
        setToken(null, null);
        localStorage.removeItem('refresh_token');
        return;
      }
      const data = await res.json();
      setToken(data.access_token, { id: '', username: 'user' });
      localStorage.setItem('refresh_token', data.refresh_token);
    } catch {
      setToken(null, null);
    }
  }, [setToken]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return {
    ...state,
    login: async (username: string, password: string) => {
      const data = await login(username, password);
      // Store refresh token for session persistence
      if (data.refresh_token) {
        localStorage.setItem('refresh_token', data.refresh_token);
      }
      return data;
    },
    logout,
    refresh,
  };
}

export function getToken(): string | null {
  return memoryToken;
}
