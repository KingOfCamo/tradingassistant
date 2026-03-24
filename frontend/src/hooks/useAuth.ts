import { useState, useCallback, useEffect } from 'react';

interface User {
  id: string;
  email: string;
  name: string;
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

  const login = useCallback(async (email: string, password: string) => {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ message: 'Login failed' }));
      throw new Error(err.message ?? 'Login failed');
    }
    const data = await res.json();
    setToken(data.accessToken, data.user);
    return data;
  }, [setToken]);

  const logout = useCallback(async () => {
    try {
      await fetch('/api/auth/logout', {
        method: 'POST',
        credentials: 'include',
      });
    } catch {
      // best-effort
    }
    setToken(null, null);
  }, [setToken]);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch('/api/auth/refresh', {
        method: 'POST',
        credentials: 'include',
      });
      if (!res.ok) {
        setToken(null, null);
        return;
      }
      const data = await res.json();
      setToken(data.accessToken, data.user);
    } catch {
      setToken(null, null);
    }
  }, [setToken]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return {
    ...state,
    login,
    logout,
    refresh,
  };
}

export function getToken(): string | null {
  return memoryToken;
}
