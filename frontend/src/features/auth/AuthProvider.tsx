"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { forgetPushOnLogout } from "@/features/parent/push";
import { api, refreshSession } from "@/lib/api/client";
import { onAuthLost, setAccessToken } from "@/lib/api/token";
import type { User } from "@/lib/api/types";

type Status = "loading" | "anonymous" | "authenticated";

interface AuthContextValue {
  status: Status;
  user: User | null;
  /** Called after login/registration with the backend response. */
  setSession: (access: string, user: User) => void;
  /** Replace the cached user after a profile update. */
  setUser: (user: User) => void;
  reloadUser: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<Status>("loading");
  const [user, setUserState] = useState<User | null>(null);
  const queryClient = useQueryClient();
  const bootstrapped = useRef(false);

  useEffect(() => {
    if (bootstrapped.current) return;
    bootstrapped.current = true;
    refreshSession().then((outcome) => {
      if (outcome.status === "ok") {
        setUserState(outcome.session.user);
        setStatus("authenticated");
      } else {
        // "unauthenticated" or a transient error: show the public entry; nothing to clear yet.
        setStatus("anonymous");
      }
    });
  }, []);

  useEffect(
    () =>
      onAuthLost(() => {
        setUserState(null);
        setStatus("anonymous");
        queryClient.clear();
      }),
    [queryClient],
  );

  const setSession = useCallback(
    (access: string, nextUser: User) => {
      // A different child may log in on the same device: never show the previous user's cache.
      queryClient.clear();
      setAccessToken(access);
      setUserState(nextUser);
      setStatus("authenticated");
    },
    [queryClient],
  );

  const setUser = useCallback((nextUser: User) => setUserState(nextUser), []);

  const reloadUser = useCallback(async () => {
    const me = await api<User>("/api/v1/auth/me/");
    setUserState(me);
  }, []);

  const logout = useCallback(async () => {
    // A shared phone must stop receiving this parent's push notifications; it needs the session, so it goes first.
    if (user?.role === "parent") await forgetPushOnLogout();
    try {
      await api<void>("/api/v1/auth/logout/", { method: "POST", auth: false });
    } finally {
      setAccessToken(null);
      setUserState(null);
      setStatus("anonymous");
      queryClient.clear();
    }
  }, [queryClient, user]);

  const value = useMemo(
    () => ({ status, user, setSession, setUser, reloadUser, logout }),
    [status, user, setSession, setUser, reloadUser, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
