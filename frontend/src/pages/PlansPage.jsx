import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useAuth } from '../auth/AuthProvider';
import { useAppHistory } from '../navigation/AppHistoryProvider.jsx';
import { TopBar } from '../components/TopBar';

const PLANS = [
  { key: 'trial', name: 'Trial', price: 1, credits: 20, blurb: 'Quick test run' },
  { key: 'entry', name: 'Entry', price: 29, credits: 7250, blurb: 'For light usage' },
  { key: 'pro', name: 'Pro', price: 79, credits: 26000, blurb: 'For consistent outreach' },
  { key: 'business', name: 'Business', price: 199, credits: 80000, blurb: 'For teams and scale' },
  { key: 'agency', name: 'Agency', price: 499, credits: 249000, blurb: 'For agencies and heavy usage' },
];

export function PlansPage() {
  const { signOut, user, session, isReady } = useAuth();
  const { back, forward, canBack, canForward } = useAppHistory();
  const [me, setMe] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [navHint, setNavHint] = useState(null);
  const [couponCode, setCouponCode] = useState('');
  const [topupCredits, setTopupCredits] = useState(5000);
  const [isBusy, setIsBusy] = useState(false);

  const currentPlanKey = me?.subscription?.plan_key || null;
  const canTopup = ['business', 'agency'].includes((currentPlanKey || '').toLowerCase());
  const accessToken = session?.access_token || null;
  const authHeaders = accessToken ? { Authorization: `Bearer ${accessToken}` } : {};

  useEffect(() => {
    if (!isReady) return;
    if (!user) return;
    if (!accessToken) {
      setError(null);
      return;
    }
    let isMounted = true;
    setIsLoading(true);
    axios.get('/api/me', { headers: authHeaders })
      .then((res) => {
        if (!isMounted) return;
        setMe(res.data);
      })
      .catch((err) => {
        if (!isMounted) return;
        const status = err?.response?.status;
        if (status === 401) return;
        setError(err?.response?.data?.detail || err?.message || 'Failed to load account');
      })
      .finally(() => {
        if (!isMounted) return;
        setIsLoading(false);
      });
    return () => { isMounted = false; };
  }, [isReady, user?.id, accessToken]);

  useEffect(() => {
    if (accessToken) setError(null);
  }, [accessToken]);

  const handleSubscribe = async (planKey) => {
    setError(null);
    setIsBusy(true);
    try {
      const res = await axios.post('/api/billing/checkout/session', { plan_key: planKey }, { headers: authHeaders });
      const url = res?.data?.url;
      if (!url) throw new Error('Missing checkout URL');
      window.location.href = url;
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to start checkout');
    } finally {
      setIsBusy(false);
    }
  };

  const handleTopup = async () => {
    setError(null);
    setIsBusy(true);
    try {
      const res = await axios.post('/api/billing/topup/session', { credits: Number(topupCredits) }, { headers: authHeaders });
      const url = res?.data?.url;
      if (!url) throw new Error('Missing checkout URL');
      window.location.href = url;
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to start top-up checkout');
    } finally {
      setIsBusy(false);
    }
  };

  const handleRedeem = async () => {
    setError(null);
    setIsBusy(true);
    try {
      await axios.post('/api/coupons/redeem', { code: couponCode }, { headers: authHeaders });
      const refreshed = await axios.get('/api/me', { headers: authHeaders });
      setMe(refreshed.data);
      setCouponCode('');
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to redeem coupon');
    } finally {
      setIsBusy(false);
    }
  };

  const creditsText = useMemo(() => {
    const balance = me?.credits_balance;
    if (typeof balance !== 'number') return '—';
    return String(balance);
  }, [me]);

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <TopBar
        left={
          <div className="flex items-center gap-2 min-w-0">
            <div className="flex items-center gap-1">
              <button
                type="button"
                className={'mac-btn px-2 py-2 text-xs ' + (!canBack ? 'opacity-50 cursor-not-allowed' : '')}
                onClick={() => {
                  if (!back()) setNavHint('No previous page.');
                }}
                aria-label="Back"
                title="Back"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                type="button"
                className={'mac-btn px-2 py-2 text-xs ' + (!canForward ? 'opacity-50 cursor-not-allowed' : '')}
                onClick={() => {
                  if (!forward()) setNavHint('No next page.');
                }}
                aria-label="Forward"
                title="Forward"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
            <div className="min-w-0">
              <div className="text-sm sm:text-base font-semibold tracking-tight truncate">localcontacts.biz</div>
            </div>
          </div>
        }
        menuTitle="Plans"
        menuItems={({ close }) => (
          <>
            <div className="mac-card p-3 text-xs">
              <div className="mac-muted">Signed in</div>
              <div className="pt-1 font-semibold truncate">{user?.email || '—'}</div>
              <div className="pt-2 mac-muted">
                Credits: <span className="text-[var(--text)]">{creditsText}</span>
              </div>
            </div>
            <Link className="mac-btn px-3 py-2 text-xs text-center w-full" to="/" onClick={close}>
              Back to app
            </Link>
            <button
              type="button"
              className="mac-btn mac-btn-primary px-3 py-2 text-xs w-full"
              onClick={async () => {
                close();
                await signOut();
              }}
            >
              Sign out
            </button>
          </>
        )}
      />

      <main className="max-w-5xl mx-auto px-5 sm:px-6 lg:px-8 py-10 space-y-8">
        {navHint && (
          <div className="mac-panel p-3 text-xs mac-muted">{navHint}</div>
        )}
        <div className="flex items-center justify-between">
          <div>
            <div className="text-2xl font-semibold">Plans</div>
            <div className="text-sm mac-muted pt-1">Credits reset monthly and expire at period end.</div>
          </div>
          <Link className="mac-link text-sm" to="/">Back to app</Link>
        </div>

        {error && <div className="mac-panel p-3 text-sm text-[color:var(--danger)]">{error}</div>}

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {PLANS.map((p) => (
            <div key={p.key} className="mac-panel p-5 space-y-3">
              <div className="flex items-center justify-between">
                <div className="text-lg font-semibold">{p.name}</div>
                {currentPlanKey && currentPlanKey.toLowerCase() === p.key ? (
                  <div className="text-xs mac-muted mac-badge">Current</div>
                ) : null}
              </div>
              <div className="text-sm mac-muted">{p.blurb}</div>
              <div className="pt-2">
                <div className="text-3xl font-semibold">${p.price}</div>
                <div className="text-xs mac-muted">per month</div>
              </div>
              <div className="text-sm">
                <span className="font-semibold">{p.credits}</span> companies / month
              </div>
              <button
                className="w-full mac-btn mac-btn-primary px-4 py-2 text-sm"
                onClick={() => handleSubscribe(p.key)}
                disabled={isBusy || isLoading}
              >
                Checkout
              </button>
            </div>
          ))}
        </div>

        <div className="mac-panel p-5 space-y-3">
          <div className="text-lg font-semibold">How it works</div>
          <div className="text-sm mac-muted">
            - Monthly plan company credits expire at the end of your billing month.<br />
            - Top-ups are available on Business and Agency and expire 90 days from purchase.<br />
            - Credits are consumed per company processed.
          </div>
        </div>

        <div className="mac-panel p-5 space-y-3">
          <div className="text-lg font-semibold">Top up</div>
          <div className="text-sm mac-muted">Business and Agency only.</div>
          <div className="flex items-center gap-3">
            <input
              type="number"
              min={1}
              value={topupCredits}
              onChange={(e) => setTopupCredits(Number(e.target.value))}
              className="w-40 mac-input px-3 py-2 text-sm"
            />
            <button className="mac-btn mac-btn-primary px-4 py-2 text-sm" disabled={!canTopup || isBusy} onClick={handleTopup}>
              Buy top-up company credits
            </button>
            {!canTopup && <div className="text-xs mac-muted">Upgrade to Business or Agency to top up.</div>}
          </div>
        </div>

        <div className="mac-panel p-5 space-y-3">
          <div className="text-lg font-semibold">Redeem coupon</div>
          <div className="flex items-center gap-3">
            <input
              value={couponCode}
              onChange={(e) => setCouponCode(e.target.value)}
              placeholder="Enter code"
              className="w-64 mac-input px-3 py-2 text-sm"
            />
            <button className="mac-btn mac-btn-primary px-4 py-2 text-sm" onClick={handleRedeem} disabled={isBusy || !couponCode.trim()}>
              Redeem
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
