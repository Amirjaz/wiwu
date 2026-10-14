import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { get, post, isApiError, type ApiError } from '../lib/api';
import type { User } from './types';

interface Session {
  user: User | null;
  ready: boolean;
  signIn: (username: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  expired: () => void;
}

const Context = createContext<Session | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    get<{ user: User | null }>('/api/panel/session/')
      .then((s) => setUser(s.user))
      .catch(() => setUser(null))
      .finally(() => setReady(true));
  }, []);

  const signIn = useCallback(async (username: string, password: string) => {
    const s = await post<{ user: User }>('/api/panel/login/', { username, password });
    setUser(s.user);
  }, []);
  const signOut = useCallback(async () => {
    await post('/api/panel/logout/').catch(() => undefined);
    setUser(null);
  }, []);
  const expired = useCallback(() => setUser(null), []);

  return <Context.Provider value={{ user, ready, signIn, signOut, expired }}>{children}</Context.Provider>;
}

export function useSession(): Session {
  const value = useContext(Context);
  if (!value) throw new Error('SessionProvider missing');
  return value;
}

/** Loads a panel URL; reload() fetches again. A 401 signs the panel out. */
export function useLoad<T>(url: string | null) {
  const { expired } = useSession();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    if (!url) return;
    setLoading(true);
    try {
      setData(await get<T>(url));
      setError(null);
    } catch (err) {
      if (isApiError(err)) {
        if (err.status === 401) expired();
        setError(err);
      }
    } finally {
      setLoading(false);
    }
  }, [url, expired]);
  useEffect(() => {
    load();
  }, [load]);
  return { data, setData, error, loading, reload: load };
}
