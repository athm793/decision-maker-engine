import React from 'react';
import { ExternalLink, BadgeCheck } from 'lucide-react';

export function ResultsTable({ results }) {
  if (!results || results.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        No decision makers found yet.
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
      <h3 className="text-lg font-semibold text-gray-200 mb-4">Found Decision Makers</h3>
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
    </div>
  );
}
