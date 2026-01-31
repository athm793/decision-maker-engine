import React from 'react';
import { Download, ExternalLink, Search, ChevronLeft, ChevronRight } from 'lucide-react';

export function ResultsTable({
  results,
  total,
  query,
  onQueryChange,
  offset,
  limit,
  onOffsetChange,
  onLimitChange,
  onDownload,
  isDownloading,
  isLoading,
}) {
  if (!results || results.length === 0) {
    return (
      <div className="w-full max-w-6xl mx-auto px-6 pb-12">
        <div className="flex items-center justify-between mb-4 gap-4">
          <h3 className="text-lg font-semibold">Found Decision Makers</h3>
          <button
            onClick={onDownload}
            disabled={true}
            className="mac-button px-4 py-2 text-sm font-medium opacity-50 cursor-not-allowed flex items-center gap-2"
          >
            <Download className="w-4 h-4" />
            Download CSV
          </button>
        </div>

        <div className="mac-card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="relative flex-1">
              <Search className="w-4 h-4 mac-muted absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                value={query}
                onChange={(e) => onQueryChange(e.target.value)}
                placeholder="Search results (company, name, title, URL, reasoning…)"
                className="w-full mac-input pl-10 pr-3 py-2 text-sm"
              />
            </div>
          </div>

          <div className="text-center py-10 mac-muted text-sm">
            {isLoading ? 'Loading results…' : 'No decision makers found yet.'}
          </div>
        </div>
      </div>
    );
  }

  const getConfidenceBadge = (score) => {
    const colors = {
      HIGH: 'bg-[color:var(--accent-weak)] text-[color:var(--accent)] border-[color:color-mix(in srgb, var(--accent) 30%, transparent)]',
      MEDIUM: 'bg-[color:var(--warning-weak)] text-[color:var(--warning)] border-[color:color-mix(in srgb, var(--warning) 30%, transparent)]',
      LOW: 'bg-[color:var(--danger-weak)] text-[color:var(--danger)] border-[color:color-mix(in srgb, var(--danger) 30%, transparent)]'
    };
    
    return (
      <span className={`px-2 py-0.5 rounded text-xs font-medium border ${colors[score] || colors.LOW}`}>
        {score || 'UNKNOWN'}
      </span>
    );
  };

  return (
    <div className="w-full max-w-6xl mx-auto px-6 pb-12">
      <div className="flex items-center justify-between mb-4 gap-4">
        <div className="flex items-center gap-3">
          <h3 className="text-lg font-semibold">Found Decision Makers</h3>
          {typeof total === 'number' && (
            <span className="text-xs mac-muted">{total} total</span>
          )}
        </div>

        <button
          onClick={onDownload}
          disabled={isDownloading}
          className="mac-button px-4 py-2 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl text-sm font-medium flex items-center gap-2"
        >
          <Download className="w-4 h-4" />
          {isDownloading ? 'Preparing…' : 'Download CSV'}
        </button>
      </div>

      <div className="flex items-center justify-between mb-4 gap-4">
        <div className="relative flex-1">
          <Search className="w-4 h-4 mac-muted absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder="Search results (company, name, title, URL, reasoning…)"
            className="w-full mac-input pl-10 pr-3 py-2 text-sm"
          />
        </div>

        <select
          value={limit}
          onChange={(e) => onLimitChange(Number(e.target.value))}
          className="mac-input px-3 py-2 text-sm"
        >
          {[10, 25, 50, 100].map((n) => (
            <option key={n} value={n}>
              {n} / page
            </option>
          ))}
        </select>
      </div>

      <div className="mac-card overflow-hidden mac-appear mac-hover-lift">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-[10px] mac-muted uppercase bg-[color:var(--surface2)]">
              <tr>
                <th className="px-6 py-3 border-b border-[color:var(--border)] font-semibold">Company Name</th>
                <th className="px-6 py-3 border-b border-[color:var(--border)] font-semibold">Company Type</th>
                <th className="px-6 py-3 border-b border-[color:var(--border)] font-semibold">Company Location</th>
                <th className="px-6 py-3 border-b border-[color:var(--border)] font-semibold">Company Website</th>
                <th className="px-6 py-3 border-b border-[color:var(--border)] font-semibold">Contact Name</th>
                <th className="px-6 py-3 border-b border-[color:var(--border)] font-semibold">Contact Job Title</th>
                <th className="px-6 py-3 border-b border-[color:var(--border)] font-semibold">Platform</th>
                <th className="px-6 py-3 border-b border-[color:var(--border)] font-semibold">Confidence</th>
                <th className="px-6 py-3 border-b border-[color:var(--border)] font-semibold">Reasoning</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[color:var(--border)]">
              {results.map((dm) => (
                <tr key={dm.id} className="hover:bg-[color:var(--surface2)] transition-colors">
                  <td className="px-6 py-4 whitespace-nowrap font-medium">
                    {dm.company_name}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap mac-muted">
                    {dm.company_type || ''}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap mac-muted">
                    {[dm.company_city, dm.company_country].filter(Boolean).join(', ') || ''}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {dm.company_website ? (
                      <a
                        href={dm.company_website}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[color:var(--accent)] hover:opacity-80 text-xs flex items-center gap-1 w-fit"
                      >
                        {dm.company_website} <ExternalLink className="w-3 h-3" />
                      </a>
                    ) : (
                      <span className="mac-muted">—</span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap font-medium">
                    {dm.name || 'Unknown'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap mac-muted">
                    {dm.title || ''}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="mac-muted">{dm.platform || ''}</span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {getConfidenceBadge(dm.confidence_score)}
                  </td>
                  <td className="px-6 py-4 mac-muted max-w-xs truncate" title={dm.reasoning}>
                    {dm.reasoning}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {typeof total === 'number' && (
        <div className="flex items-center justify-between mt-4 text-sm mac-muted">
          <div>
            Showing {Math.min(total, offset + 1)}-{Math.min(total, offset + results.length)} of {total}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onOffsetChange(Math.max(0, offset - limit))}
              disabled={offset === 0}
              className="mac-button px-3 py-2 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl flex items-center gap-2"
            >
              <ChevronLeft className="w-4 h-4" />
              Prev
            </button>
            <button
              onClick={() => onOffsetChange(offset + limit)}
              disabled={offset + limit >= total}
              className="mac-button px-3 py-2 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl flex items-center gap-2"
            >
              Next
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
