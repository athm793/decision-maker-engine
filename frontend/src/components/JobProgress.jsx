import React from 'react';
import { Loader2, CheckCircle, AlertTriangle, XCircle, Search } from 'lucide-react';
import { clsx } from 'clsx';

export function JobProgress({ job }) {
  const percentage = job.total_companies > 0 
    ? Math.round((job.processed_companies / job.total_companies) * 100) 
    : 0;

  const getStatusColor = (status) => {
    switch (status) {
      case 'processing': return 'text-blue-400';
      case 'completed': return 'text-green-400';
      case 'failed': return 'text-red-400';
      case 'cancelled': return 'text-yellow-400';
      default: return 'text-gray-400';
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
      <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <span className={getStatusColor(job.status)}>
                {getStatusIcon(job.status)}
              </span>
              Processing Job #{job.id}
            </h2>
            <p className="text-gray-400 text-sm mt-1">
              File: {job.filename}
            </p>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-white">
              {job.decision_makers_found}
            </div>
            <div className="text-xs text-gray-500 uppercase tracking-wide">
              Decision Makers Found
            </div>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm text-gray-400">
            <span>Progress: {percentage}%</span>
            <span>{job.processed_companies} / {job.total_companies} Companies</span>
          </div>
          <div className="h-3 bg-gray-700 rounded-full overflow-hidden">
            <div 
              className={clsx(
                "h-full transition-all duration-500 ease-out",
                job.status === 'completed' ? "bg-green-500" : "bg-blue-500"
              )}
              style={{ width: `${percentage}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
