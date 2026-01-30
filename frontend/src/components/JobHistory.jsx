import React from 'react';
import { RefreshCw, Play } from 'lucide-react';


const statusColors = {
  queued: 'text-[var(--muted)]',
  processing: 'text-[color:var(--accent)]',
  completed: 'text-[color:var(--accent)]',
  failed: 'text-[color:var(--danger)]',
  cancelled: 'text-[var(--muted)]',
};


export function JobHistory({ jobs, isLoading, onRefresh, onSelectJob }) {
  return (
    <div className="w-full max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold">Recent Jobs</h3>
        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="mac-button px-3 py-2 disabled:opacity-50 disabled:cursor-not-allowed text-xs font-medium flex items-center gap-2"
        >
          <RefreshCw className={isLoading ? 'w-4 h-4 animate-spin' : 'w-4 h-4'} />
          Refresh
        </button>
      </div>

      <div className="mac-card overflow-hidden">
        {(!jobs || jobs.length === 0) && !isLoading ? (
          <div className="p-6 text-sm mac-muted">No jobs yet. Upload a CSV to start one.</div>
        ) : (
          <div className="divide-y divide-[color:var(--border)]">
            {(jobs || []).map((job) => (
              <button
                key={job.id}
                onClick={() => onSelectJob(job.id)}
                className="w-full text-left p-4 hover:bg-[color:var(--surface2)] transition-colors flex items-center justify-between gap-4"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium truncate">{job.filename}</span>
                    <span className={"text-[10px] font-semibold uppercase tracking-wide " + (statusColors[job.status] || 'text-[var(--muted)]')}>
                      {job.status}
                    </span>
                  </div>
                  <div className="text-xs mac-muted mt-1">
                    {new Date(job.created_at).toLocaleString()} • {job.processed_companies}/{job.total_companies} processed • {job.decision_makers_found} found
                  </div>
                </div>

                <div className="flex items-center gap-2 text-xs mac-muted flex-shrink-0">
                  <Play className="w-4 h-4" />
                  Open
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
