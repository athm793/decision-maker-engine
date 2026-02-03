import { useEffect, useState } from 'react';
import axios from 'axios';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthProvider';

export function RequireAdmin({ children }) {
  const { user, isReady } = useAuth();
  const location = useLocation();
  const [isAdmin, setIsAdmin] = useState(null);

  useEffect(() => {
    let isMounted = true;
    if (!isReady || !user) {
      setIsAdmin(null);
      return () => {
        isMounted = false;
      };
    }

    (async () => {
      try {
        const res = await axios.get('/api/me', { timeout: 10000 });
        const role = String(res?.data?.role || '').toLowerCase();
        if (isMounted) setIsAdmin(role === 'admin');
      } catch {
        if (isMounted) setIsAdmin(false);
      }
    })();

    return () => {
      isMounted = false;
    };
  }, [isReady, user]);

  if (!isReady) {
    return (
      <div className="min-h-screen flex items-center justify-center px-6">
        <div className="mac-panel p-4 text-sm mac-muted">Loading…</div>
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;

  if (isAdmin === null) {
    return (
      <div className="min-h-screen flex items-center justify-center px-6">
        <div className="mac-panel p-4 text-sm mac-muted">Checking access…</div>
      </div>
    );
  }

  if (!isAdmin) return <Navigate to="/" replace />;

  return children;
}

