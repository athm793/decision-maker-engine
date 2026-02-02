import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { supabase } from '../supabaseClient';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [isReady, setIsReady] = useState(false);

  const applyAxiosAuth = (nextSession) => {
    const token = nextSession?.access_token;
    if (token) {
      axios.defaults.headers.common.Authorization = `Bearer ${token}`;
    } else {
      delete axios.defaults.headers.common.Authorization;
    }
  };

  useEffect(() => {
    let isMounted = true;
    const failSafe = setTimeout(() => {
      if (!isMounted) return;
      setIsReady(true);
    }, 6000);

    supabase.auth.getSession().then(({ data }) => {
      if (!isMounted) return;
      const nextSession = data.session || null;
      applyAxiosAuth(nextSession);
      setSession(nextSession);
      setIsReady(true);
      clearTimeout(failSafe);
    });

    const { data: sub } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      const normalized = nextSession || null;
      applyAxiosAuth(normalized);
      setSession(normalized);
      setIsReady(true);
      clearTimeout(failSafe);
    });

    return () => {
      isMounted = false;
      clearTimeout(failSafe);
      sub?.subscription?.unsubscribe?.();
    };
  }, []);

  const value = useMemo(() => {
    return {
      session,
      user: session?.user || null,
      isReady,
      signOut: async () => {
        await supabase.auth.signOut();
      },
    };
  }, [session, isReady]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
