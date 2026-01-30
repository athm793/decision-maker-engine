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
          <h3 className="text-lg font-semibold text-gray-200">Found Decision Makers</h3>
          <button
            onClick={onDownload}
            disabled={true}
            className="px-4 py-2 bg-gray-800 rounded-lg text-sm font-medium text-gray-400 cursor-not-allowed flex items-center gap-2"
          >
            <Download className="w-4 h-4" />
            Download CSV
          </button>
        </div>

        <div className="bg-gray-800 rounded-xl border border-gray-700 p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-gray-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                value={query}
                onChange={(e) => onQueryChange(e.target.value)}
                placeholder="Search results (company, name, title, URL, reasoning…)"
                className="w-full bg-gray-900 border border-gray-700 rounded-lg pl-10 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
            </div>
          </div>

          <div className="text-center py-10 text-gray-500 text-sm">
            {isLoading ? 'Loading results…' : 'No decision makers found yet.'}
          </div>
        </div>
      </div>
    );
  }

  const getConfidenceBadge = (score) => {
    const colors = {
      HIGH: 'bg-green-500/10 text-green-400 border-green-500/20',
      MEDIUM: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
      LOW: 'bg-red-500/10 text-red-400 border-red-500/20'
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
          <h3 className="text-lg font-semibold text-gray-200">Found Decision Makers</h3>
          {typeof total === 'number' && (
            <span className="text-xs text-gray-400">{total} total</span>
          )}
        </div>

        <button
          onClick={onDownload}
          disabled={isDownloading}
          className="px-4 py-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
        >
          <Download className="w-4 h-4" />
          {isDownloading ? 'Preparing…' : 'Download CSV'}
        </button>
      </div>

      <div className="flex items-center justify-between mb-4 gap-4">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-gray-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder="Search results (company, name, title, URL, reasoning…)"
            className="w-full bg-gray-900 border border-gray-700 rounded-lg pl-10 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          />
        </div>

        <select
          value={limit}
          onChange={(e) => onLimitChange(Number(e.target.value))}
          className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
        >
          {[10, 25, 50, 100].map((n) => (
            <option key={n} value={n}>
              {n} / page
            </option>
          ))}
        </select>
      </div>

      <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-gray-400 uppercase bg-gray-900/50">
              <tr>
                <th className="px-6 py-3 border-b border-gray-700">Company</th>
                <th className="px-6 py-3 border-b border-gray-700">Name & Title</th>
                <th className="px-6 py-3 border-b border-gray-700">Platform</th>
                <th className="px-6 py-3 border-b border-gray-700">Confidence</th>
                <th className="px-6 py-3 border-b border-gray-700">Reasoning</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {results.map((dm) => (
                <tr key={dm.id} className="bg-gray-800/50 hover:bg-gray-800 transition-colors">
                  <td className="px-6 py-4 whitespace-nowrap text-gray-300 font-medium">
                    {dm.company_name}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-col">
                      <span className="text-white font-medium">{dm.name}</span>
                      <span className="text-gray-400 text-xs">{dm.title}</span>
                      {dm.profile_url && (
                        <a 
                          href={dm.profile_url} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="text-blue-400 hover:text-blue-300 text-xs flex items-center gap-1 mt-0.5 w-fit"
                        >
                          View Profile <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-gray-400">
                    {dm.platform}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {getConfidenceBadge(dm.confidence_score)}
                  </td>
                  <td className="px-6 py-4 text-gray-400 max-w-xs truncate" title={dm.reasoning}>
                    {dm.reasoning}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {typeof total === 'number' && (
        <div className="flex items-center justify-between mt-4 text-sm text-gray-400">
          <div>
            Showing {Math.min(total, offset + 1)}-{Math.min(total, offset + results.length)} of {total}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onOffsetChange(Math.max(0, offset - limit))}
              disabled={offset === 0}
              className="px-3 py-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors flex items-center gap-2"
            >
              <ChevronLeft className="w-4 h-4" />
              Prev
            </button>
            <button
              onClick={() => onOffsetChange(offset + limit)}
              disabled={offset + limit >= total}
              className="px-3 py-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors flex items-center gap-2"
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
