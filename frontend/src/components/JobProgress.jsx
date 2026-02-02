import React, { useEffect, useMemo, useState } from 'react';
import { Loader2, CheckCircle, AlertTriangle, XCircle } from 'lucide-react';
import { clsx } from 'clsx';

export function JobProgress({ job, timerStartMs }) {
  const percentage = job.total_companies > 0 
    ? Math.round((job.processed_companies / job.total_companies) * 100) 
    : 0;

  const [tickMs, setTickMs] = useState(() => Date.now());

  useEffect(() => {
    if (!timerStartMs) return;
    if (!['queued', 'processing'].includes(job.status)) return;
    const id = setInterval(() => setTickMs(Date.now()), 1000);
    return () => clearInterval(id);
  }, [timerStartMs, job?.status, job?.id]);

  useEffect(() => {
    if (['completed', 'failed', 'cancelled'].includes(job.status)) {
      setTickMs(Date.now());
    }
  }, [job?.status]);

  const elapsedLabel = useMemo(() => {
    if (!timerStartMs) return '0:00';
    const ms = Math.max(0, tickMs - timerStartMs);
    const totalSeconds = Math.floor(ms / 1000);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    const pad2 = (n) => String(n).padStart(2, '0');
    if (hours > 0) return `${hours}:${pad2(minutes)}:${pad2(seconds)}`;
    return `${minutes}:${pad2(seconds)}`;
  }, [timerStartMs, tickMs]);

  const getStatusColor = (status) => {
    switch (status) {
      case 'processing': return 'text-[color:var(--accent)]';
      case 'completed': return 'text-[color:var(--accent)]';
      case 'failed': return 'text-[color:var(--danger)]';
      case 'cancelled': return 'text-[var(--muted)]';
      default: return 'text-[var(--muted)]';
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
    <div className="w-full max-w-6xl mx-auto px-6">
      <div className="mac-card p-4 mac-appear mac-hover-lift">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className={getStatusColor(job.status)}>{getStatusIcon(job.status)}</span>
              <span className="text-sm font-semibold">Job #{job.id}</span>
              <span className="text-xs mac-muted truncate">{job.filename}</span>
            </div>
            {!!job.support_id && (
              <div className="mt-1 text-xs mac-muted">
                Job ID: <span className="font-mono">{job.support_id}</span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-3 flex-shrink-0">
            <div className="px-3 py-1 rounded-full bg-[color:var(--surface2)] border border-[color:var(--border)] text-xs">
              <span className="font-semibold">{job.decision_makers_found}</span>
              <span className="mac-muted"> found</span>
            </div>
          </div>
        </div>

        <div className="mt-3 flex items-center justify-between text-xs mac-muted gap-3">
          <span>{job.processed_companies} / {job.total_companies} companies</span>
          <span>{percentage}%</span>
          <span>Credits: {job.credits_spent ?? 0}</span>
          <span>{elapsedLabel}</span>
        </div>
        {job.stop_reason === 'credits_exhausted' && (
          <div className="mt-2 text-xs mac-muted">Stopped: credits exhausted</div>
        )}

        <div className="mt-3 h-2 bg-[color:var(--surface2)] border border-[color:var(--border)] rounded-full overflow-hidden">
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
  );
}
