import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

const AppHistoryContext = createContext(null);

function normalizeLocation(location) {
  return { pathname: location.pathname, search: location.search };
}

function sameLocation(a, b) {
  return a?.pathname === b?.pathname && a?.search === b?.search;
}

export function AppHistoryProvider({ children }) {
  const navigate = useNavigate();
  const location = useLocation();
  const stackRef = useRef([normalizeLocation(location)]);
  const indexRef = useRef(0);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    const nextLoc = normalizeLocation(location);
    const stack = stackRef.current;
    const idx = indexRef.current;
    if (sameLocation(stack[idx], nextLoc)) return;
    if (idx + 1 < stack.length && sameLocation(stack[idx + 1], nextLoc)) {
      indexRef.current = idx + 1;
      setVersion((v) => v + 1);
      return;
    }
    if (idx - 1 >= 0 && sameLocation(stack[idx - 1], nextLoc)) {
      indexRef.current = idx - 1;
      setVersion((v) => v + 1);
      return;
    }

    const capped = [...stack.slice(0, idx + 1), nextLoc];
    stackRef.current = capped.length > 50 ? capped.slice(capped.length - 50) : capped;
    indexRef.current = stackRef.current.length - 1;
    setVersion((v) => v + 1);
  }, [location.pathname, location.search]);

  const api = useMemo(() => {
    const getCanBack = () => indexRef.current > 0;
    const getCanForward = () => indexRef.current < stackRef.current.length - 1;
    return {
      get canBack() {
        return getCanBack();
      },
      get canForward() {
        return getCanForward();
      },
      back: () => {
        if (!getCanBack()) return false;
        const nextIdx = indexRef.current - 1;
        const target = stackRef.current[nextIdx];
        indexRef.current = nextIdx;
        setVersion((v) => v + 1);
        navigate(target.pathname + target.search);
        return true;
      },
      forward: () => {
        if (!getCanForward()) return false;
        const nextIdx = indexRef.current + 1;
        const target = stackRef.current[nextIdx];
        indexRef.current = nextIdx;
        setVersion((v) => v + 1);
        navigate(target.pathname + target.search);
        return true;
      },
    };
  }, [navigate, version]);

  return <AppHistoryContext.Provider value={api}>{children}</AppHistoryContext.Provider>;
}

export function useAppHistory() {
  const ctx = useContext(AppHistoryContext);
  if (!ctx) throw new Error('useAppHistory must be used within AppHistoryProvider');
  return ctx;
}

