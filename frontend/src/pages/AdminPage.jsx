import { useEffect, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useAuth } from '../auth/AuthProvider';
import { useAppHistory } from '../navigation/AppHistoryProvider.jsx';
import { TopBar } from '../components/TopBar';

const PRICING_TIERS = [
  { key: 'trial', name: 'Trial', price: 1, credits: 20 },
  { key: 'entry', name: 'Entry', price: 29, credits: 7250 },
  { key: 'pro', name: 'Pro', price: 79, credits: 26000 },
  { key: 'business', name: 'Business', price: 199, credits: 80000 },
  { key: 'agency', name: 'Agency', price: 499, credits: 249000 },
];

export function AdminPage() {
  const { signOut, user, session, isReady } = useAuth();
  const { back, forward, canBack, canForward } = useAppHistory();
  const [me, setMe] = useState(null);
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [coupons, setCoupons] = useState([]);
  const [error, setError] = useState(null);
  const [navHint, setNavHint] = useState(null);
  const [isBusy, setIsBusy] = useState(false);
  const [userSortKey, setUserSortKey] = useState('email');
  const [userSortDir, setUserSortDir] = useState('asc');
  const [adminJobs, setAdminJobs] = useState([]);
  const [jobsUserId, setJobsUserId] = useState('');
  const [jobsQuery, setJobsQuery] = useState('');
  const [isJobsLoading, setIsJobsLoading] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [jobResults, setJobResults] = useState([]);
  const [jobResultsTotal, setJobResultsTotal] = useState(0);
  const [jobResultsQuery, setJobResultsQuery] = useState('');
  const [jobResultsLimit, setJobResultsLimit] = useState(25);
  const [jobResultsOffset, setJobResultsOffset] = useState(0);
  const [isJobResultsLoading, setIsJobResultsLoading] = useState(false);
  const [cellModal, setCellModal] = useState(null);
  const [simPlanKey, setSimPlanKey] = useState('entry');
  const [simMonthlyPrice, setSimMonthlyPrice] = useState(29);
  const [simIncludedCredits, setSimIncludedCredits] = useState(7250);
  const [simTargetMarginPct, setSimTargetMarginPct] = useState(70);
  const [simCogsPerCredit, setSimCogsPerCredit] = useState(0.00105);
  const [simCreditsPerCompany, setSimCreditsPerCompany] = useState(1);
  const [simContactsPerCompany, setSimContactsPerCompany] = useState(1);
  const [simJobId, setSimJobId] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');

  const [adjustUserId, setAdjustUserId] = useState('');
  const [adjustDelta, setAdjustDelta] = useState(0);
  const [adjustSetBalance, setAdjustSetBalance] = useState(0);
  const [adjustReason, setAdjustReason] = useState('');
  const [adjustExpiresDays, setAdjustExpiresDays] = useState('');

  const [newCouponCode, setNewCouponCode] = useState('');
  const [newCouponCredits, setNewCouponCredits] = useState(0);
  const [assignCouponCode, setAssignCouponCode] = useState('');
  const [assignUserId, setAssignUserId] = useState('');

  const accessToken = session?.access_token || null;
  const authHeaders = accessToken ? { Authorization: `Bearer ${accessToken}` } : {};

  const refreshAll = async () => {
    if (!isReady) return;
    if (!user) return;
    if (!accessToken) {
      setError(null);
      return;
    }
    setError(null);
    setIsBusy(true);
    try {
      const meRes = await axios.get('/api/me', { headers: authHeaders });
      setMe(meRes.data);
      const role = (meRes?.data?.role || '').toLowerCase();
      if (role !== 'admin') {
        setStats(null);
        setUsers([]);
        setCoupons([]);
        return;
      }

      const statsRes = await axios.get('/api/admin/stats', { headers: authHeaders });
      setStats(statsRes.data);
      const usersRes = await axios.get('/api/admin/users', { headers: authHeaders });
      setUsers(usersRes.data || []);
      const couponsRes = await axios.get('/api/admin/coupons', { headers: authHeaders });
      setCoupons(couponsRes.data || []);
    } catch (err) {
      const status = err?.response?.status;
      if (status === 403) {
        setStats(null);
        setUsers([]);
        setCoupons([]);
        return;
      }
      if (status === 401) {
        return;
      }
      setError(err?.response?.data?.detail || err?.message || 'Failed to load admin');
    } finally {
      setIsBusy(false);
    }
  };

  useEffect(() => {
    refreshAll();
  }, [isReady, user?.id, accessToken]);

  useEffect(() => {
    if (!isReady || !user) {
      setError(null);
      setMe(null);
      setStats(null);
      setUsers([]);
      setCoupons([]);
    }
  }, [isReady, user?.id]);

  useEffect(() => {
    if (accessToken) setError(null);
  }, [accessToken]);

  const hasMe = !!me;
  const isAdmin = (me?.role || '').toLowerCase() === 'admin';

  const toggleUserSort = (key) => {
    setUserSortKey((prevKey) => {
      if (prevKey === key) {
        setUserSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
        return prevKey;
      }
      setUserSortDir('asc');
      return key;
    });
  };

  const sortedUsers = (() => {
    const dir = userSortDir === 'desc' ? -1 : 1;
    const list = Array.isArray(users) ? [...users] : [];
    const key = userSortKey;
    list.sort((a, b) => {
      const av = a?.[key];
      const bv = b?.[key];
      if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * dir;
      const as = String(av ?? '').toLowerCase();
      const bs = String(bv ?? '').toLowerCase();
      if (as < bs) return -1 * dir;
      if (as > bs) return 1 * dir;
      return 0;
    });
    return list;
  })();

  const handleAdjust = async () => {
    setError(null);
    setIsBusy(true);
    try {
      await axios.post(
        `/api/admin/users/${adjustUserId}/credits/adjust`,
        {
          delta: Number(adjustDelta),
          reason: adjustReason || null,
          expires_days: adjustExpiresDays ? Number(adjustExpiresDays) : null,
        },
        { headers: authHeaders }
      );
      await refreshAll();
      setAdjustDelta(0);
      setAdjustReason('');
      setAdjustExpiresDays('');
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to adjust credits');
    } finally {
      setIsBusy(false);
    }
  };

  const handleSetBalance = async () => {
    setError(null);
    setIsBusy(true);
    try {
      await axios.post(
        `/api/admin/users/${adjustUserId}/credits/set`,
        {
          balance: Number(adjustSetBalance),
          reason: adjustReason || null,
          expires_days: adjustExpiresDays ? Number(adjustExpiresDays) : null,
        },
        { headers: authHeaders }
      );
      await refreshAll();
      setAdjustReason('');
      setAdjustExpiresDays('');
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to set credits');
    } finally {
      setIsBusy(false);
    }
  };

  const handleCreateCoupon = async () => {
    setError(null);
    setIsBusy(true);
    try {
      await axios.post(
        '/api/admin/coupons',
        {
          code: newCouponCode,
          coupon_type: 'credit_grant',
          credits: Number(newCouponCredits),
          active: true,
        },
        { headers: authHeaders }
      );
      await refreshAll();
      setNewCouponCode('');
      setNewCouponCredits(0);
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to create coupon');
    } finally {
      setIsBusy(false);
    }
  };

  const handleDeleteCoupon = async (code) => {
    setError(null);
    setIsBusy(true);
    try {
      await axios.delete(`/api/admin/coupons/${encodeURIComponent(code)}`, { headers: authHeaders });
      await refreshAll();
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to delete coupon');
    } finally {
      setIsBusy(false);
    }
  };

  const handleAssign = async (mode) => {
    setError(null);
    setIsBusy(true);
    try {
      await axios.post(
        `/api/admin/coupons/${encodeURIComponent(assignCouponCode)}/${mode}`,
        { user_id: assignUserId },
        { headers: authHeaders }
      );
      await refreshAll();
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to update assignment');
    } finally {
      setIsBusy(false);
    }
  };

  const loadAdminJobs = async (options = {}) => {
    if (!accessToken) {
      setError('Not authenticated.');
      return;
    }
    const ignoreFilters = Boolean(options.ignoreFilters);
    const userId = ignoreFilters ? '' : (options.userId ?? jobsUserId);
    const q = ignoreFilters ? '' : (options.q ?? jobsQuery);
    setError(null);
    setIsJobsLoading(true);
    try {
      const res = await axios.get('/api/admin/jobs', {
        headers: authHeaders,
        params: {
          user_id: userId || undefined,
          q: q || undefined,
          limit: 200,
          offset: 0,
        },
      });
      setAdminJobs(res.data || []);
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to load jobs');
    } finally {
      setIsJobsLoading(false);
    }
  };

  const loadAdminJobResults = async (jobId, nextOffset = 0, nextLimit = jobResultsLimit, nextQuery = jobResultsQuery) => {
    if (!accessToken) return;
    if (!jobId) return;
    setError(null);
    setIsJobResultsLoading(true);
    try {
      const res = await axios.get(`/api/admin/jobs/${jobId}/results/paged`, {
        headers: authHeaders,
        params: {
          q: nextQuery || undefined,
          limit: nextLimit,
          offset: nextOffset,
        },
      });
      setJobResults(res?.data?.items || []);
      setJobResultsTotal(Number(res?.data?.total || 0));
      setJobResultsOffset(Number(res?.data?.offset || nextOffset));
      setJobResultsLimit(Number(res?.data?.limit || nextLimit));
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to load job results');
    } finally {
      setIsJobResultsLoading(false);
    }
  };

  const downloadAdminJobCsv = async (jobId) => {
    if (!accessToken) return;
    if (!jobId) return;
    setError(null);
    setIsBusy(true);
    try {
      const res = await axios.get(`/api/admin/jobs/${jobId}/results.csv`, {
        headers: authHeaders,
        params: { q: jobResultsQuery || undefined },
        responseType: 'blob',
      });
      const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `admin-job-${jobId}-results.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to download CSV');
    } finally {
      setIsBusy(false);
    }
  };

  const downloadAdminJobsCsv = async () => {
    if (!accessToken) return;
    setError(null);
    setIsBusy(true);
    try {
      const res = await axios.get('/api/admin/jobs.csv', {
        headers: authHeaders,
        params: {
          user_id: jobsUserId || undefined,
          q: jobsQuery || undefined,
          limit: 5000,
          offset: 0,
        },
        responseType: 'blob',
      });
      const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'admin-jobs.csv';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to download jobs CSV');
    } finally {
      setIsBusy(false);
    }
  };

  const clip = (raw, maxLen = 180) => {
    const s = raw == null ? '' : String(raw);
    if (s.length <= maxLen) return s;
    return s.slice(0, maxLen) + '…';
  };

  const fmtUsd = (raw, digits = 4) => {
    const n = Number(raw);
    if (!Number.isFinite(n)) return '—';
    return `$${n.toFixed(digits)}`;
  };

  const fmtUsdCompact = (raw) => {
    const n = Number(raw);
    if (!Number.isFinite(n)) return '—';
    return `$${n.toFixed(4)}`;
  };

  const fmtTs = (raw) => {
    if (!raw) return '—';
    const d = new Date(raw);
    if (Number.isNaN(d.getTime())) return '—';
    return d.toLocaleString();
  };

  const tabClass = (key) => {
    const base = 'mac-btn px-4 py-2 text-sm';
    if (activeTab === key) return base + ' mac-btn-primary';
    return base;
  };

  const computeCreditsAtTargetMargin = (price) => {
    const p = Number(price);
    const cogs = Number(simCogsPerCredit);
    const marginPct = Number(simTargetMarginPct);
    if (!Number.isFinite(p) || !Number.isFinite(cogs) || !Number.isFinite(marginPct)) return 0;
    if (p <= 0 || cogs <= 0) return 0;
    const m = Math.min(0.99, Math.max(0, marginPct / 100));
    const budget = p * (1 - m);
    return Math.max(0, Math.floor(budget / cogs));
  };

  const useSelectedJobCogs = () => {
    const job = (adminJobs || []).find((j) => j?.id === simJobId);
    if (!job) return;
    const credits = Number(job.credits_spent);
    const totalCost = Number(job.total_cost_usd);
    if (!Number.isFinite(credits) || credits <= 0) return;
    if (!Number.isFinite(totalCost) || totalCost <= 0) return;
    setSimCogsPerCredit(totalCost / credits);
  };

  const computeMarginPctForCredits = (price, credits) => {
    const p = Number(price);
    const c = Number(credits);
    const unit = Number(simCogsPerCredit);
    if (!Number.isFinite(p) || !Number.isFinite(c) || !Number.isFinite(unit)) return null;
    if (p <= 0 || c <= 0 || unit <= 0) return null;
    const margin = 1 - (c * unit) / p;
    return Math.max(-999, Math.min(0.999, margin)) * 100;
  };

  const includedCompanies = (() => {
    const credits = Number(simIncludedCredits);
    const cpc = Number(simCreditsPerCompany);
    if (!Number.isFinite(credits) || !Number.isFinite(cpc) || credits <= 0 || cpc <= 0) return 0;
    return Math.floor(credits / cpc);
  })();

  const includedContactsEstimate = (() => {
    const cpc = Number(simContactsPerCompany);
    if (!Number.isFinite(cpc) || cpc <= 0) return 0;
    return includedCompanies * Math.floor(cpc);
  })();

  const impliedMarginPct = computeMarginPctForCredits(simMonthlyPrice, simIncludedCredits);

  const applyPlan = (key) => {
    const tier = PRICING_TIERS.find((t) => t.key === key) || null;
    setSimPlanKey(key);
    if (tier) {
      setSimMonthlyPrice(tier.price);
      setSimIncludedCredits(tier.credits);
    }
  };

  useEffect(() => {
    if (!accessToken) return;
    if (activeTab !== 'jobs' && activeTab !== 'pricing') return;
    if ((adminJobs || []).length > 0) return;
    if (isJobsLoading) return;
    loadAdminJobs({ ignoreFilters: activeTab === 'pricing' });
  }, [activeTab, accessToken]);

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
              <div className="text-sm sm:text-base font-semibold tracking-tight truncate">Admin</div>
            </div>
          </div>
        }
        menuTitle="Admin"
        menuItems={({ close }) => (
          <>
            <div className="mac-card p-3 text-xs">
              <div className="mac-muted">Signed in</div>
              <div className="pt-1 font-semibold truncate">{user?.email || '—'}</div>
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

      <main className="max-w-6xl mx-auto px-5 sm:px-6 lg:px-8 py-10 space-y-6">
        {cellModal && (
          <div
            className="fixed inset-0 z-50 mac-overlay flex items-center justify-center p-4"
            onClick={() => setCellModal(null)}
          >
            <div
              className="mac-card mac-appear w-full max-w-4xl p-4 space-y-3"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-semibold truncate">{cellModal.title}</div>
                <button className="mac-btn px-3 py-2 text-xs" onClick={() => setCellModal(null)}>
                  Close
                </button>
              </div>
              <textarea
                className="mac-input w-full px-3 py-2 text-xs font-mono"
                rows={16}
                readOnly
                value={cellModal.content || ''}
              />
              <div className="text-xs mac-muted">Select and copy any text from the box above.</div>
            </div>
          </div>
        )}
        {navHint && (
          <div className="mac-panel p-3 text-xs mac-muted">{navHint}</div>
        )}
        <div className="flex items-center justify-between">
          <div>
            <div className="text-2xl font-semibold">Admin panel</div>
            <div className="text-sm mac-muted pt-1">Manage credits and coupons.</div>
          </div>
          <Link className="mac-link text-sm" to="/">Back to app</Link>
        </div>

        {error && <div className="mac-panel p-3 text-sm text-[color:var(--danger)]">{error}</div>}

        {hasMe && !isAdmin && (
          <div className="mac-panel p-5">
            <div className="text-sm text-[color:var(--danger)]">Admin access required.</div>
          </div>
        )}

        {isAdmin && (
          <>
            <div className="mac-card p-3 flex flex-wrap items-center gap-2">
              <button type="button" className={tabClass('overview')} onClick={() => setActiveTab('overview')}>
                Overview
              </button>
              <button type="button" className={tabClass('users')} onClick={() => setActiveTab('users')}>
                Users
              </button>
              <button type="button" className={tabClass('coupons')} onClick={() => setActiveTab('coupons')}>
                Coupons
              </button>
              <button type="button" className={tabClass('jobs')} onClick={() => setActiveTab('jobs')}>
                Jobs & traces
              </button>
              <button type="button" className={tabClass('pricing')} onClick={() => setActiveTab('pricing')}>
                Pricing
              </button>
            </div>

            {activeTab === 'overview' && (
              <div className="mac-panel p-5 space-y-3">
                <div className="text-lg font-semibold">Global stats</div>
                <div className="grid grid-cols-2 sm:grid-cols-6 gap-3 text-sm">
                  <div className="mac-card p-3">
                    <div className="text-xs mac-muted">Users</div>
                    <div className="text-lg font-semibold">{stats?.users ?? '—'}</div>
                  </div>
                  <div className="mac-card p-3">
                    <div className="text-xs mac-muted">Jobs</div>
                    <div className="text-lg font-semibold">{stats?.jobs ?? '—'}</div>
                  </div>
                  <div className="mac-card p-3">
                    <div className="text-xs mac-muted">Results</div>
                    <div className="text-lg font-semibold">{stats?.results ?? '—'}</div>
                  </div>
                  <div className="mac-card p-3">
                    <div className="text-xs mac-muted">Credits spent</div>
                    <div className="text-lg font-semibold">{stats?.credits_spent ?? '—'}</div>
                  </div>
                  <div className="mac-card p-3">
                    <div className="text-xs mac-muted">LLM calls started</div>
                    <div className="text-lg font-semibold">{stats?.llm_calls_started ?? '—'}</div>
                  </div>
                  <div className="mac-card p-3">
                    <div className="text-xs mac-muted">LLM calls succeeded</div>
                    <div className="text-lg font-semibold">{stats?.llm_calls_succeeded ?? '—'}</div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'users' && (
              <>
                <div className="mac-panel p-5 space-y-3">
                  <div className="text-lg font-semibold">Adjust user credits</div>
                  <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
                    <input value={adjustUserId} onChange={(e) => setAdjustUserId(e.target.value)} placeholder="User ID" className="mac-input px-3 py-2 text-sm" />
                    <input type="number" value={adjustDelta} onChange={(e) => setAdjustDelta(Number(e.target.value))} placeholder="Delta" className="mac-input px-3 py-2 text-sm" />
                    <input
                      type="number"
                      value={adjustSetBalance}
                      onChange={(e) => setAdjustSetBalance(Number(e.target.value))}
                      placeholder="Set balance to"
                      className="mac-input px-3 py-2 text-sm"
                    />
                    <input value={adjustExpiresDays} onChange={(e) => setAdjustExpiresDays(e.target.value)} placeholder="Expires days (optional)" className="mac-input px-3 py-2 text-sm" />
                    <input value={adjustReason} onChange={(e) => setAdjustReason(e.target.value)} placeholder="Reason" className="mac-input px-3 py-2 text-sm" />
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button className="mac-btn mac-btn-primary px-4 py-2 text-sm" disabled={isBusy || !adjustUserId.trim() || !adjustDelta} onClick={handleAdjust}>
                      Apply delta
                    </button>
                    <button
                      className="mac-btn px-4 py-2 text-sm"
                      disabled={isBusy || !adjustUserId.trim() || !Number.isFinite(Number(adjustSetBalance))}
                      onClick={handleSetBalance}
                    >
                      Set balance
                    </button>
                  </div>
                </div>

                <div className="mac-panel p-5 space-y-3">
                  <div className="text-lg font-semibold">Users</div>
                  <div className="mac-card overflow-hidden">
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm text-left">
                        <thead className="text-[10px] mac-muted uppercase bg-[color:var(--surface2)]">
                          <tr>
                            <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold">
                              <button type="button" className="mac-link" onClick={() => toggleUserSort('email')}>
                                Email {userSortKey === 'email' ? (userSortDir === 'asc' ? '▲' : '▼') : ''}
                              </button>
                            </th>
                            <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold">
                              <button type="button" className="mac-link" onClick={() => toggleUserSort('id')}>
                                User ID {userSortKey === 'id' ? (userSortDir === 'asc' ? '▲' : '▼') : ''}
                              </button>
                            </th>
                            <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold">
                              <button type="button" className="mac-link" onClick={() => toggleUserSort('role')}>
                                Role {userSortKey === 'role' ? (userSortDir === 'asc' ? '▲' : '▼') : ''}
                              </button>
                            </th>
                            <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold">
                              <button type="button" className="mac-link" onClick={() => toggleUserSort('subscription_plan')}>
                                Subscription {userSortKey === 'subscription_plan' ? (userSortDir === 'asc' ? '▲' : '▼') : ''}
                              </button>
                            </th>
                            <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold">
                              Signup IP
                            </th>
                            <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold">
                              Last IP
                            </th>
                            <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold text-right">
                              <button type="button" className="mac-link" onClick={() => toggleUserSort('user_total_cost_usd')}>
                                User cost {userSortKey === 'user_total_cost_usd' ? (userSortDir === 'asc' ? '▲' : '▼') : ''}
                              </button>
                            </th>
                            <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold text-right">
                              <button type="button" className="mac-link" onClick={() => toggleUserSort('credits_balance')}>
                                Credits {userSortKey === 'credits_balance' ? (userSortDir === 'asc' ? '▲' : '▼') : ''}
                              </button>
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {sortedUsers.map((u) => (
                            <tr
                              key={u.id}
                              className="border-b border-[color:var(--border)] hover:bg-[color:var(--surface2)]/60 cursor-pointer"
                              onClick={() => setAdjustUserId(u.id)}
                            >
                              <td className="px-4 py-3">
                                <div className="font-semibold truncate max-w-[320px]">{u.email || '—'}</div>
                              </td>
                              <td className="px-4 py-3">
                                <div className="text-xs mac-muted truncate max-w-[420px]">{u.id}</div>
                              </td>
                              <td className="px-4 py-3">
                                <div className="text-xs mac-muted">{u.role}</div>
                              </td>
                              <td className="px-4 py-3">
                                <div className="text-xs mac-muted">{u.subscription_plan || 'free'}</div>
                              </td>
                              <td className="px-4 py-3">
                                <div className="text-xs mac-muted truncate max-w-[160px]">{u.signup_ip || '—'}</div>
                              </td>
                              <td className="px-4 py-3">
                                <div className="text-xs mac-muted truncate max-w-[160px]">{u.last_ip || '—'}</div>
                              </td>
                              <td className="px-4 py-3 text-right">
                                <div className="font-semibold">{fmtUsdCompact(u.user_total_cost_usd)}</div>
                              </td>
                              <td className="px-4 py-3 text-right">
                                <div className="font-semibold">{u.credits_balance}</div>
                              </td>
                            </tr>
                          ))}
                          {sortedUsers.length === 0 && (
                            <tr>
                              <td className="px-4 py-6 mac-muted text-sm" colSpan={8}>
                                No users found.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </>
            )}

            {activeTab === 'coupons' && (
              <div className="mac-panel p-5 space-y-3">
                <div className="text-lg font-semibold">Coupons</div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <input value={newCouponCode} onChange={(e) => setNewCouponCode(e.target.value)} placeholder="New coupon code" className="mac-input px-3 py-2 text-sm" />
                  <input type="number" value={newCouponCredits} onChange={(e) => setNewCouponCredits(Number(e.target.value))} placeholder="Credits" className="mac-input px-3 py-2 text-sm" />
                  <button className="mac-btn mac-btn-primary px-4 py-2 text-sm" disabled={isBusy || !newCouponCode.trim()} onClick={handleCreateCoupon}>
                    Create coupon
                  </button>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
                  <input value={assignCouponCode} onChange={(e) => setAssignCouponCode(e.target.value)} placeholder="Coupon code" className="mac-input px-3 py-2 text-sm" />
                  <input value={assignUserId} onChange={(e) => setAssignUserId(e.target.value)} placeholder="User ID" className="mac-input px-3 py-2 text-sm" />
                  <div className="flex gap-2">
                    <button className="mac-btn mac-btn-primary px-4 py-2 text-sm" disabled={isBusy || !assignCouponCode.trim() || !assignUserId.trim()} onClick={() => handleAssign('assign')}>
                      Assign
                    </button>
                    <button className="mac-btn px-4 py-2 text-sm" disabled={isBusy || !assignCouponCode.trim() || !assignUserId.trim()} onClick={() => handleAssign('unassign')}>
                      Unassign
                    </button>
                  </div>
                </div>

                <div className="pt-3 space-y-2">
                  {(coupons || []).map((c) => (
                    <div key={c.code} className="mac-card p-3 flex items-center justify-between text-sm">
                      <div className="flex items-center gap-3">
                        <div className="font-semibold">{c.code}</div>
                        <div className="mac-muted">{c.credits} credits</div>
                        {!c.active && <div className="text-xs mac-muted mac-badge">Inactive</div>}
                      </div>
                      <button className="mac-btn px-3 py-2 text-xs" disabled={isBusy} onClick={() => handleDeleteCoupon(c.code)}>
                        Delete
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeTab === 'jobs' && (
              <div className="mac-panel p-5 space-y-3">
                <div className="text-lg font-semibold">Jobs & traces</div>
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
                <select value={jobsUserId} onChange={(e) => setJobsUserId(e.target.value)} className="mac-input px-3 py-2 text-sm">
                  <option value="">All users</option>
                  {(sortedUsers || []).map((u) => (
                    <option key={u.id} value={u.id}>
                      {(u.email || '—') + ' — ' + u.id}
                    </option>
                  ))}
                </select>
                <input value={jobsQuery} onChange={(e) => setJobsQuery(e.target.value)} placeholder="Search jobs by filename" className="mac-input px-3 py-2 text-sm" />
                <button className="mac-btn mac-btn-primary px-4 py-2 text-sm" disabled={isBusy || isJobsLoading} onClick={loadAdminJobs}>
                  {isJobsLoading ? 'Loading…' : 'Load jobs'}
                </button>
                <button className="mac-btn px-4 py-2 text-sm" disabled={isBusy || isJobsLoading} onClick={downloadAdminJobsCsv}>
                  Download jobs CSV
                </button>
              </div>

              <div className="mac-card overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm text-left">
                    <thead className="text-[10px] mac-muted uppercase bg-[color:var(--surface2)]">
                      <tr>
                        <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold">Job</th>
                        <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold">Job ID</th>
                        <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold">User</th>
                        <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold">Filename</th>
                        <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold">Status</th>
                        <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold text-right">LLM API Calls</th>
                        <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold text-right">Serper API Calls</th>
                        <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold text-right">LLM Cost</th>
                        <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold text-right">Serper Cost</th>
                        <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold text-right">Total Cost</th>
                        <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold text-right">Cost / Contact</th>
                        <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold text-right">Found</th>
                        <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold text-right">Credits</th>
                        <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {(adminJobs || []).map((j) => (
                        <tr key={j.id} className="border-b border-[color:var(--border)] hover:bg-[color:var(--surface2)]/60">
                          <td className="px-4 py-3 font-semibold">{j.id}</td>
                          <td className="px-4 py-3 text-xs mac-muted whitespace-nowrap">{j.support_id || '—'}</td>
                          <td className="px-4 py-3 text-xs mac-muted truncate max-w-[240px]">{j.user_id || '—'}</td>
                          <td className="px-4 py-3 truncate max-w-[320px]">{j.filename || '—'}</td>
                          <td className="px-4 py-3 text-xs mac-muted">{j.status}</td>
                          <td className="px-4 py-3 text-right">{j.llm_calls_started ?? 0}</td>
                          <td className="px-4 py-3 text-right">{j.serper_calls ?? 0}</td>
                          <td className="px-4 py-3 text-right">{fmtUsd(j.llm_cost_usd, 4)}</td>
                          <td className="px-4 py-3 text-right">{fmtUsd(j.serper_cost_usd, 4)}</td>
                          <td className="px-4 py-3 text-right">{fmtUsd(j.total_cost_usd, 4)}</td>
                          <td className="px-4 py-3 text-right">{fmtUsd(j.cost_per_contact_usd, 5)}</td>
                          <td className="px-4 py-3 text-right">{j.decision_makers_found ?? '—'}</td>
                          <td className="px-4 py-3 text-right">{j.credits_spent ?? '—'}</td>
                          <td className="px-4 py-3 text-right">
                            <button
                              className="mac-btn px-3 py-2 text-xs"
                              disabled={isJobResultsLoading}
                              onClick={async () => {
                                setSelectedJobId(j.id);
                                setJobResultsOffset(0);
                                await loadAdminJobResults(j.id, 0, jobResultsLimit, jobResultsQuery);
                              }}
                            >
                              View results
                            </button>
                          </td>
                        </tr>
                      ))}
                      {(adminJobs || []).length === 0 && (
                        <tr>
                          <td className="px-4 py-6 mac-muted text-sm" colSpan={14}>
                            No jobs loaded.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {selectedJobId && (
                <div className="mac-card p-4 space-y-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-semibold">Job {selectedJobId} results</div>
                    <div className="flex items-center gap-2">
                      <button className="mac-btn px-3 py-2 text-xs" disabled={isBusy} onClick={() => downloadAdminJobCsv(selectedJobId)}>
                        Download CSV
                      </button>
                      <button className="mac-btn px-3 py-2 text-xs" onClick={() => setSelectedJobId(null)}>
                        Close
                      </button>
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <input value={jobResultsQuery} onChange={(e) => setJobResultsQuery(e.target.value)} placeholder="Search results" className="mac-input px-3 py-2 text-sm" />
                    <select value={jobResultsLimit} onChange={(e) => setJobResultsLimit(Number(e.target.value))} className="mac-input px-3 py-2 text-sm">
                      {[10, 25, 50, 100].map((n) => (
                        <option key={n} value={n}>
                          {n} / page
                        </option>
                      ))}
                    </select>
                    <button
                      className="mac-btn mac-btn-primary px-4 py-2 text-sm"
                      disabled={isJobResultsLoading}
                      onClick={() => loadAdminJobResults(selectedJobId, 0, jobResultsLimit, jobResultsQuery)}
                    >
                      {isJobResultsLoading ? 'Loading…' : 'Search'}
                    </button>
                  </div>

                  <div className="mac-card overflow-hidden">
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm text-left">
                        <thead className="text-[10px] mac-muted uppercase bg-[color:var(--surface2)]">
                          <tr>
                            <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold">Company</th>
                            <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold">Contact</th>
                            <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold">Title</th>
                            <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold">Platform</th>
                            <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold">LLM Call Timestamp</th>
                            <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold">Serper Call Timestamp</th>
                            <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold">LLM Input</th>
                            <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold">Serper Queries</th>
                            <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold">LLM Output</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(jobResults || []).map((r) => (
                            <tr key={r.id} className="border-b border-[color:var(--border)] hover:bg-[color:var(--surface2)]/60 align-top">
                              <td className="px-4 py-3 whitespace-nowrap font-semibold">{r.company_name || '—'}</td>
                              <td className="px-4 py-3 whitespace-nowrap">{r.name || '—'}</td>
                              <td className="px-4 py-3 whitespace-nowrap mac-muted">{r.title || '—'}</td>
                              <td className="px-4 py-3 whitespace-nowrap mac-muted">{r.platform || '—'}</td>
                              <td className="px-4 py-3 whitespace-nowrap text-xs mac-muted">{fmtTs(r.llm_call_timestamp)}</td>
                              <td className="px-4 py-3 whitespace-nowrap text-xs mac-muted">{fmtTs(r.serper_call_timestamp)}</td>
                              <td className="px-4 py-3 text-xs mac-muted max-w-[420px]">
                                <button
                                  type="button"
                                  className="mac-link text-left w-full truncate"
                                  title="Click to open"
                                  onClick={() => setCellModal({ title: `LLM Input (result ${r.id})`, content: r.llm_input || '' })}
                                >
                                  {clip(r.llm_input)}
                                </button>
                              </td>
                              <td className="px-4 py-3 text-xs mac-muted max-w-[320px]">
                                <button
                                  type="button"
                                  className="mac-link text-left w-full truncate"
                                  title="Click to open"
                                  onClick={() => setCellModal({ title: `Serper Queries (result ${r.id})`, content: r.serper_queries || '' })}
                                >
                                  {clip(r.serper_queries)}
                                </button>
                              </td>
                              <td className="px-4 py-3 text-xs mac-muted max-w-[420px]">
                                <button
                                  type="button"
                                  className="mac-link text-left w-full truncate"
                                  title="Click to open"
                                  onClick={() => setCellModal({ title: `LLM Output (result ${r.id})`, content: r.llm_output || '' })}
                                >
                                  {clip(r.llm_output)}
                                </button>
                              </td>
                            </tr>
                          ))}
                          {(jobResults || []).length === 0 && (
                            <tr>
                              <td className="px-4 py-6 mac-muted text-sm" colSpan={9}>
                                {isJobResultsLoading ? 'Loading…' : 'No results.'}
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-xs mac-muted">
                    <div>
                      {jobResultsTotal ? `Showing ${Math.min(jobResultsTotal, jobResultsOffset + 1)}-${Math.min(jobResultsTotal, jobResultsOffset + jobResults.length)} of ${jobResultsTotal}` : '—'}
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        className="mac-btn px-3 py-2 text-xs"
                        disabled={isJobResultsLoading || jobResultsOffset === 0}
                        onClick={() => loadAdminJobResults(selectedJobId, Math.max(0, jobResultsOffset - jobResultsLimit), jobResultsLimit, jobResultsQuery)}
                      >
                        Prev
                      </button>
                      <button
                        className="mac-btn px-3 py-2 text-xs"
                        disabled={isJobResultsLoading || jobResultsOffset + jobResultsLimit >= jobResultsTotal}
                        onClick={() => loadAdminJobResults(selectedJobId, jobResultsOffset + jobResultsLimit, jobResultsLimit, jobResultsQuery)}
                      >
                        Next
                      </button>
                    </div>
                  </div>
                </div>
              )}
              </div>
            )}

            {activeTab === 'pricing' && (
              <div className="mac-panel p-5 space-y-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-lg font-semibold">Pricing simulator</div>
                    <div className="text-sm mac-muted pt-1">Model company-credit pricing using COGS per company credit.</div>
                  </div>
                  <button className="mac-btn px-4 py-2 text-sm" disabled={isBusy || isJobsLoading} onClick={() => loadAdminJobs({ ignoreFilters: true })}>
                    {isJobsLoading ? 'Loading…' : 'Load jobs'}
                  </button>
                </div>

                <div className="mac-card p-4 space-y-4">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-3">
                      <div className="space-y-1">
                        <div className="text-xs mac-muted">Plan</div>
                        <select
                          value={simPlanKey}
                          onChange={(e) => applyPlan(e.target.value)}
                          className="mac-input px-3 py-2 text-sm w-full"
                        >
                          {PRICING_TIERS.map((t) => (
                            <option key={t.key} value={t.key}>
                              {t.name}
                            </option>
                          ))}
                          <option value="custom">Custom</option>
                        </select>
                      </div>
                      <div className="space-y-1">
                        <div className="text-xs mac-muted">Monthly price (USD)</div>
                        <input
                          type="number"
                          value={simMonthlyPrice}
                          onChange={(e) => setSimMonthlyPrice(Number(e.target.value))}
                          className="mac-input px-3 py-2 text-sm w-full"
                        />
                      </div>
                      <div className="space-y-1">
                        <div className="text-xs mac-muted">Included company credits / month</div>
                        <input
                          type="number"
                          value={simIncludedCredits}
                          onChange={(e) => setSimIncludedCredits(Number(e.target.value))}
                          className="mac-input px-3 py-2 text-sm w-full"
                        />
                      </div>
                    </div>
                    <div className="space-y-3">
                      <div className="space-y-1">
                        <div className="text-xs mac-muted">Target gross margin (%)</div>
                        <input
                          type="number"
                          value={simTargetMarginPct}
                          onChange={(e) => setSimTargetMarginPct(Number(e.target.value))}
                          className="mac-input px-3 py-2 text-sm w-full"
                        />
                      </div>
                      <div className="space-y-1">
                        <div className="text-xs mac-muted">COGS per company credit (USD)</div>
                        <input
                          type="number"
                          step="0.000001"
                          value={simCogsPerCredit}
                          onChange={(e) => setSimCogsPerCredit(Number(e.target.value))}
                          className="mac-input px-3 py-2 text-sm w-full"
                        />
                      </div>
                      <div className="space-y-1">
                        <div className="text-xs mac-muted">Use a job’s cost/credit</div>
                        <div className="flex items-center gap-2">
                          <select
                            value={simJobId || ''}
                            onChange={(e) => setSimJobId(e.target.value ? Number(e.target.value) : null)}
                            className="mac-input px-3 py-2 text-sm w-full"
                          >
                            <option value="">Select job…</option>
                            {(adminJobs || []).map((j) => (
                              <option key={j.id} value={j.id}>
                                #{j.id} — {j.filename || '—'}
                              </option>
                            ))}
                          </select>
                          <button className="mac-btn px-3 py-2 text-xs" disabled={!simJobId} onClick={useSelectedJobCogs}>
                            Use
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
                    <div className="bg-[color:var(--surface2)] border border-[color:var(--border)] rounded-2xl p-3">
                      <div className="text-xs mac-muted uppercase tracking-wide">Credits / company</div>
                      <input
                        type="number"
                        value={simCreditsPerCompany}
                        onChange={(e) => setSimCreditsPerCompany(Number(e.target.value))}
                        className="mac-input px-3 py-2 text-sm mt-2 w-full"
                      />
                    </div>
                    <div className="bg-[color:var(--surface2)] border border-[color:var(--border)] rounded-2xl p-3">
                      <div className="text-xs mac-muted uppercase tracking-wide">Contacts / company (est.)</div>
                      <input
                        type="number"
                        value={simContactsPerCompany}
                        onChange={(e) => setSimContactsPerCompany(Number(e.target.value))}
                        className="mac-input px-3 py-2 text-sm mt-2 w-full"
                      />
                    </div>
                    <div className="bg-[color:var(--surface2)] border border-[color:var(--border)] rounded-2xl p-3">
                      <div className="text-xs mac-muted uppercase tracking-wide">Included companies</div>
                      <div className="text-lg font-semibold">{includedCompanies}</div>
                      <div className="text-xs mac-muted pt-1">Est. contacts: {includedContactsEstimate}</div>
                    </div>
                    <div className="bg-[color:var(--surface2)] border border-[color:var(--border)] rounded-2xl p-3">
                      <div className="text-xs mac-muted uppercase tracking-wide">Effective $/company credit</div>
                      <div className="text-lg font-semibold">
                        {Number(simIncludedCredits) > 0 ? fmtUsd(Number(simMonthlyPrice) / Number(simIncludedCredits), 6) : '—'}
                      </div>
                      <div className="text-xs mac-muted pt-1">
                        Implied margin: {typeof impliedMarginPct === 'number' ? `${impliedMarginPct.toFixed(2)}%` : '—'}
                      </div>
                    </div>
                  </div>

                  <div className="mac-muted text-xs">
                    Company credits at target margin = floor((price × (1 − margin)) / COGS per company credit) → {computeCreditsAtTargetMargin(simMonthlyPrice)}
                  </div>

                  <div className="mac-card overflow-hidden">
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm text-left">
                        <thead className="text-[10px] mac-muted uppercase bg-[color:var(--surface2)]">
                          <tr>
                            <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold">Tier</th>
                            <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold text-right">Price</th>
                            <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold text-right">Company credits</th>
                            <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold text-right">$ / company credit</th>
                            <th className="px-4 py-3 border-b border-[color:var(--border)] font-semibold text-right">Implied margin</th>
                          </tr>
                        </thead>
                        <tbody>
                          {PRICING_TIERS.map((t) => {
                            const credits = Number(t.credits);
                            const price = Number(t.price);
                            const m = computeMarginPctForCredits(price, credits);
                            return (
                              <tr key={t.name} className="border-b border-[color:var(--border)] hover:bg-[color:var(--surface2)]/60">
                                <td className="px-4 py-3 font-semibold">{t.name}</td>
                                <td className="px-4 py-3 text-right">{fmtUsd(t.price, 2)}</td>
                                <td className="px-4 py-3 text-right">{t.credits}</td>
                                <td className="px-4 py-3 text-right">{credits > 0 ? fmtUsd(price / credits, 6) : '—'}</td>
                                <td className="px-4 py-3 text-right">{typeof m === 'number' ? `${m.toFixed(2)}%` : '—'}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
