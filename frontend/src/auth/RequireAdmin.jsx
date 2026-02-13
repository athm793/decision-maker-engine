import { useEffect, useState } from 'react';
import axios from 'axios';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthProvider';

export function RequireAdmin({ children }) {
  const { user, isReady } = useAuth();
  const location = useLocation();
  const [isAdmin, setIsAdmin] = useState(null);
  const [diagText, setDiagText] = useState(null);
  const [isDiagLoading, setIsDiagLoading] = useState(false);
  const [diagError, setDiagError] = useState(null);

  useEffect(() => {
    let isMounted = true;
    if (!isReady || !user) {
      setIsAdmin(null);
      setDiagText(null);
      setDiagError(null);
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

  const fetchDiagnostics = async () => {
    if (isDiagLoading) return;
    setDiagError(null);
    setIsDiagLoading(true);
    try {
      const res = await axios.get('/api/me/diagnostics', { timeout: 15000 });
      const text = JSON.stringify(res?.data || {}, null, 2);
      setDiagText(text);
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      }
    } catch (err) {
      setDiagError(err?.response?.data?.detail || err?.message || 'Failed to fetch diagnostics');
    } finally {
      setIsDiagLoading(false);
    }
  };

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

  if (!isAdmin) {
    return (
      <div className="min-h-screen flex items-center justify-center px-6 py-10">
        <div className="w-full max-w-2xl mac-card p-5 space-y-3">
          <div className="text-lg font-semibold">Admin access required</div>
          <div className="text-sm mac-muted">
            This account is authenticated, but it is not recognized as an admin by the API.
          </div>
          {diagError && <div className="text-sm text-[color:var(--danger)]">{diagError}</div>}
          <div className="flex flex-wrap gap-2">
            <button type="button" className="mac-btn px-3 py-2 text-sm" onClick={fetchDiagnostics}>
              {isDiagLoading ? 'Checking…' : 'Copy diagnostics'}
            </button>
            {diagText ? <div className="text-sm mac-muted px-3 py-2">Diagnostics copied</div> : null}
          </div>
          {diagText && (
            <textarea
              className="mac-input w-full px-3 py-2 text-xs font-mono"
              rows={10}
              readOnly
              value={diagText}
            />
          )}
        </div>
      </div>
    );
  }

  return children;
}
