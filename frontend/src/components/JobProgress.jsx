import React, { useEffect, useMemo, useState } from 'react';
import { Loader2, CheckCircle, AlertTriangle, XCircle } from 'lucide-react';
import { clsx } from 'clsx';

export function JobProgress({ job }) {
  const percentage = job.total_companies > 0 
    ? Math.round((job.processed_companies / job.total_companies) * 100) 
    : 0;

  const [tickMs, setTickMs] = useState(() => Date.now());

  useEffect(() => {
    if (!job?.created_at) return;
    if (!['queued', 'processing'].includes(job.status)) return;
    const id = setInterval(() => setTickMs(Date.now()), 1000);
    return () => clearInterval(id);
  }, [job?.created_at, job?.status, job?.id]);

  useEffect(() => {
    if (['completed', 'failed', 'cancelled'].includes(job.status)) {
      setTickMs(Date.now());
    }
  }, [job?.status]);

  const elapsedLabel = useMemo(() => {
    const start = new Date(job.created_at).getTime();
    if (!Number.isFinite(start)) return '—';
    const end = tickMs;
    const ms = Math.max(0, end - start);
    const totalSeconds = Math.floor(ms / 1000);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    const pad2 = (n) => String(n).padStart(2, '0');
    if (hours > 0) return `${hours}:${pad2(minutes)}:${pad2(seconds)}`;
    return `${minutes}:${pad2(seconds)}`;
  }, [job?.created_at, tickMs]);

  const getStatusColor = (status) => {
    switch (status) {
      case 'processing': return 'text-[color:var(--accent)]';
      case 'completed': return 'text-[color:var(--accent)]';
      case 'failed': return 'text-[color:var(--danger)]';
      case 'cancelled': return 'text-[var(--muted)]';
      default: return 'text-[var(--muted)]';
    }
  };

  const getStatusLabel = (status) => {
    switch (status) {
      case 'queued': return 'Queued';
      case 'processing': return 'Processing';
      case 'completed': return 'Completed';
      case 'failed': return 'Failed';
      case 'cancelled': return 'Cancelled';
      default: return status;
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'processing': return <Loader2 className="w-5 h-5 animate-spin" />;
      case 'completed': return <CheckCircle className="w-5 h-5" />;
      case 'failed': return <XCircle className="w-5 h-5" />;
      case 'cancelled': return <AlertTriangle className="w-5 h-5" />;
      default: return <Loader2 className="w-5 h-5" />;
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto p-6 space-y-6">
      <div className="mac-card p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <span className={getStatusColor(job.status)}>
                {getStatusIcon(job.status)}
              </span>
              Processing Job #{job.id}
            </h2>
            <p className="mac-muted text-sm mt-1">
              File: {job.filename}
            </p>
          </div>
          <div className="text-right">
            <div className={clsx('text-xs font-medium uppercase tracking-wide', getStatusColor(job.status))}>
              {getStatusLabel(job.status)}
            </div>
            <div className="text-2xl font-semibold">
              {job.decision_makers_found}
            </div>
            <div className="text-xs mac-muted uppercase tracking-wide">
              Decision Makers Found
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 mb-6">
          <div className="bg-[color:var(--surface2)] border border-[color:var(--border)] rounded-2xl p-3">
            <div className="text-xs mac-muted uppercase tracking-wide">Platforms</div>
            <div className="text-sm mt-1">
              {(job.selected_platforms && job.selected_platforms.length > 0) ? job.selected_platforms.join(', ') : 'default'}
            </div>
          </div>
          <div className="bg-[color:var(--surface2)] border border-[color:var(--border)] rounded-2xl p-3">
            <div className="text-xs mac-muted uppercase tracking-wide">Limits</div>
            <div className="text-sm mt-1">
              {job.max_contacts_total || '—'} total • {job.max_contacts_per_company || '—'} / company
            </div>
          </div>
          <div className="bg-[color:var(--surface2)] border border-[color:var(--border)] rounded-2xl p-3">
            <div className="text-xs mac-muted uppercase tracking-wide">Credits Spent</div>
            <div className="text-sm mt-1">
              {job.credits_spent ?? 0}
            </div>
            {job.stop_reason === 'credits_exhausted' && (
              <div className="text-xs mt-1 mac-muted">Stopped: credits exhausted</div>
            )}
          </div>
          <div className="bg-[color:var(--surface2)] border border-[color:var(--border)] rounded-2xl p-3">
            <div className="text-xs mac-muted uppercase tracking-wide">Elapsed</div>
            <div className="text-sm mt-1">
              {elapsedLabel}
            </div>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm mac-muted">
            <span>Progress: {percentage}%</span>
            <span>{job.processed_companies} / {job.total_companies} Companies</span>
          </div>
          <div className="h-3 bg-[color:var(--surface2)] border border-[color:var(--border)] rounded-full overflow-hidden">
            <div 
              className={clsx(
                "h-full transition-all duration-500 ease-out",
                job.status === 'completed'
                  ? "bg-[color:var(--accent)]"
                  : job.status === 'failed'
                    ? "bg-[color:var(--danger)]"
                    : job.status === 'cancelled'
                      ? "bg-[color:var(--muted)]"
                      : "bg-[color:var(--accent)]"
              )}
              style={{ width: `${percentage}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
