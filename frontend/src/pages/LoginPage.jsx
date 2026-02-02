import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Link } from 'react-router-dom';
import { getSupabaseClient, loadSupabaseConfig } from '../supabaseClient';
import logoUrl from '../assets/logo.svg';

export function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [mode, setMode] = useState('login');
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [isBusy, setIsBusy] = useState(false);
  const [authStatus, setAuthStatus] = useState({ ready: false, configured: false, source: 'unknown' });

  useEffect(() => {
    let mounted = true;
    (async () => {
      const cfg = await loadSupabaseConfig();
      if (!mounted) return;
      setAuthStatus({ ready: true, configured: !!(cfg.url && cfg.anonKey), source: cfg.source || 'unknown' });
    })();
    return () => {
      mounted = false;
    };
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setIsBusy(true);
    try {
      const supabase = await getSupabaseClient();
      if (!supabase) throw new Error('Auth is not configured');
      if (mode === 'signup') {
        const { data, error: signUpError } = await supabase.auth.signUp({ email, password });
        if (signUpError) throw signUpError;
        if (data?.session) {
          navigate('/');
        } else {
          setNotice('Check your email to confirm your account, then sign in.');
          setMode('login');
        }
      } else {
        const { error: signInError } = await supabase.auth.signInWithPassword({ email, password });
        if (signInError) throw signInError;
        navigate('/');
      }
    } catch (err) {
      setError(err?.message || 'Login failed');
    } finally {
      setIsBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <Link to="/" className="fixed top-4 left-4 z-20 flex items-center gap-2" aria-label="Home" title="Home">
        <img src={logoUrl} alt="" className="w-9 h-9 rounded-xl" />
      </Link>
      <div className="w-full max-w-md mac-panel p-6">
        <div className="flex items-center justify-between">
          <div className="text-lg font-semibold">localcontacts.biz</div>
        </div>
        <div className="text-sm mac-muted pt-1">
          {mode === 'signup' ? 'Create your account' : 'Sign in to continue'}
        </div>

        {authStatus.ready && !authStatus.configured && (
          <div className="pt-6 space-y-3">
            <div className="mac-panel p-4 text-sm">
              <div className="font-semibold">Auth is not configured</div>
              <div className="pt-1 mac-muted">
                Set <span className="font-mono">VITE_SUPABASE_URL</span> and <span className="font-mono">VITE_SUPABASE_ANON_KEY</span> at build time, or set backend <span className="font-mono">SUPABASE_URL</span> and <span className="font-mono">SUPABASE_ANON_KEY</span>.
              </div>
            </div>
          </div>
        )}

        <form className="pt-6 space-y-3" onSubmit={handleSubmit}>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Email"
            className="w-full mac-input px-3 py-2 text-sm"
            required
            autoComplete="email"
            disabled={isBusy || !authStatus.ready || !authStatus.configured}
          />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
            className="w-full mac-input px-3 py-2 text-sm"
            required
            autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
            disabled={isBusy || !authStatus.ready || !authStatus.configured}
          />
          {notice && <div className="text-sm mac-muted">{notice}</div>}
          {error && <div className="text-sm text-[color:var(--danger)]">{error}</div>}
          <button
            type="submit"
            disabled={isBusy || !authStatus.ready || !authStatus.configured}
            className="w-full mac-btn mac-btn-primary px-4 py-2 text-sm"
          >
            {isBusy ? 'Please wait…' : (mode === 'signup' ? 'Create account' : 'Sign in')}
          </button>
        </form>

        <div className="pt-4 text-sm">
          {mode === 'signup' ? (
            <button className="mac-link" onClick={() => setMode('login')}>
              Already have an account? Sign in
            </button>
          ) : (
            <button className="mac-link" onClick={() => setMode('signup')}>
              New here? Create an account
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
