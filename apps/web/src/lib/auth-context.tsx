"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { apiCall, ApiError } from "@/lib/api";
import type { Business, RegisterResponse, TokenResponse, User } from "@/lib/types";

const STORAGE_KEY = "ai-receptionist.auth";

interface StoredSession {
  accessToken: string;
  refreshToken: string;
}

interface RegisterInput {
  email: string;
  password: string;
  full_name: string;
  business_name: string;
}

interface AuthContextValue {
  isLoading: boolean;
  user: User | null;
  businesses: Business[];
  business: Business | null;
  login: (email: string, password: string) => Promise<void>;
  register: (data: RegisterInput) => Promise<void>;
  logout: () => Promise<void>;
  apiFetch: <T>(path: string, options?: Omit<RequestInit, "body"> & { body?: unknown }) => Promise<T>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function loadSession(): StoredSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as StoredSession) : null;
  } catch {
    return null;
  }
}

function saveSession(session: StoredSession | null) {
  if (typeof window === "undefined") return;
  if (session) {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  } else {
    window.localStorage.removeItem(STORAGE_KEY);
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  // Both start at their SSR-safe default (no window access during render),
  // so the server render and the first client render match exactly — the
  // real localStorage read happens after mount, in the effect below. Doing
  // that read inside a useState initializer instead would make the first
  // client render differ from the server's and trigger a hydration mismatch.
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  const [businesses, setBusinesses] = useState<Business[]>([]);
  // Tokens live in a ref (not state) so apiFetch's retry-after-refresh path
  // always reads the latest value instead of one captured in a stale render.
  const sessionRef = useRef<StoredSession | null>(null);

  const setSession = useCallback((session: StoredSession | null) => {
    sessionRef.current = session;
    saveSession(session);
  }, []);

  const authedCall = useCallback(
    async <T,>(
      path: string,
      options: Omit<RequestInit, "body"> & { body?: unknown } = {},
      accessToken: string
    ): Promise<T> =>
      apiCall<T>(path, {
        ...options,
        headers: { ...options.headers, Authorization: `Bearer ${accessToken}` },
      }),
    []
  );

  const refresh = useCallback(async (): Promise<string> => {
    const current = sessionRef.current;
    if (!current) throw new ApiError(401, "No hay sesión");
    const tokens = await apiCall<TokenResponse>("/api/v1/auth/refresh", {
      method: "POST",
      body: { refresh_token: current.refreshToken },
    });
    setSession({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token });
    return tokens.access_token;
  }, [setSession]);

  const apiFetch = useCallback(
    async <T,>(
      path: string,
      options: Omit<RequestInit, "body"> & { body?: unknown } = {}
    ): Promise<T> => {
      const current = sessionRef.current;
      if (!current) throw new ApiError(401, "No hay sesión");
      try {
        return await authedCall<T>(path, options, current.accessToken);
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          const newAccessToken = await refresh();
          return authedCall<T>(path, options, newAccessToken);
        }
        throw error;
      }
    },
    [authedCall, refresh]
  );

  const loadUserAndBusinesses = useCallback(async () => {
    const [me, biz] = await Promise.all([
      apiFetch<User>("/api/v1/auth/me"),
      apiFetch<Business[]>("/api/v1/businesses"),
    ]);
    setUser(me);
    setBusinesses(biz);
  }, [apiFetch]);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      const stored = loadSession();
      sessionRef.current = stored;
      if (!stored) {
        if (!cancelled) setIsLoading(false);
        return;
      }
      try {
        await loadUserAndBusinesses();
      } catch {
        if (!cancelled) {
          setSession(null);
          setUser(null);
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }
    void bootstrap();

    return () => {
      cancelled = true;
    };
    // Only run once on mount — loadUserAndBusinesses/setSession are stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const tokens = await apiCall<TokenResponse>("/api/v1/auth/login", {
        method: "POST",
        body: { email, password },
      });
      setSession({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token });
      await loadUserAndBusinesses();
    },
    [loadUserAndBusinesses, setSession]
  );

  const register = useCallback(
    async (data: RegisterInput) => {
      const result = await apiCall<RegisterResponse>("/api/v1/auth/register", {
        method: "POST",
        body: data,
      });
      setSession({ accessToken: result.access_token, refreshToken: result.refresh_token });
      setUser(result.user);
      const biz = await authedCall<Business[]>("/api/v1/businesses", {}, result.access_token);
      setBusinesses(biz);
    },
    [authedCall, setSession]
  );

  const logout = useCallback(async () => {
    const current = sessionRef.current;
    setSession(null);
    setUser(null);
    setBusinesses([]);
    if (current) {
      try {
        await apiCall("/api/v1/auth/logout", {
          method: "POST",
          body: { refresh_token: current.refreshToken },
        });
      } catch {
        // Already logging out client-side regardless of whether the server
        // call to revoke the refresh token succeeds.
      }
    }
  }, [setSession]);

  return (
    <AuthContext.Provider
      value={{
        isLoading,
        user,
        businesses,
        business: businesses[0] ?? null,
        login,
        register,
        logout,
        apiFetch,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  return ctx;
}
