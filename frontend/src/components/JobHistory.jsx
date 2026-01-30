import React from 'react';
import { RefreshCw, Play } from 'lucide-react';


const statusColors = {
  queued: 'text-gray-300',
  processing: 'text-blue-300',
  completed: 'text-green-300',
  failed: 'text-red-300',
  cancelled: 'text-yellow-300',
};


export function JobHistory({ jobs, isLoading, onRefresh, onSelectJob }) {
  return (
    <div className="w-full max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-300">Recent Jobs</h3>
        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="px-3 py-1.5 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-xs font-medium transition-colors flex items-center gap-2"
        >
          <RefreshCw className={isLoading ? 'w-4 h-4 animate-spin' : 'w-4 h-4'} />
          Refresh
        </button>
      </div>

      <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        {(!jobs || jobs.length === 0) && !isLoading ? (
          <div className="p-6 text-sm text-gray-400">No jobs yet. Upload a CSV to start one.</div>
        ) : (
          <div className="divide-y divide-gray-700">
            {(jobs || []).map((job) => (
              <button
                key={job.id}
                onClick={() => onSelectJob(job.id)}
                className="w-full text-left p-4 hover:bg-gray-800/60 transition-colors flex items-center justify-between gap-4"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-white truncate">{job.filename}</span>
                    <span className={"text-xs font-medium uppercase tracking-wide " + (statusColors[job.status] || 'text-gray-300')}>
                      {job.status}
                    </span>
                  </div>
                  <div className="text-xs text-gray-400 mt-1">
                    {new Date(job.created_at).toLocaleString()} • {job.processed_companies}/{job.total_companies} processed • {job.decision_makers_found} found
                  </div>
                </div>

                <div className="flex items-center gap-2 text-xs text-gray-300 flex-shrink-0">
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

