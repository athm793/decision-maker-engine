import React, { useState, useEffect } from 'react';
import { Check, AlertCircle, ArrowRight } from 'lucide-react';

const REQUIRED_FIELDS = [
  { key: 'company_name', label: 'Company Name', required: true },
  { key: 'industry', label: 'Company Type', required: false },
  { key: 'location', label: 'Location', required: false },
  { key: 'website', label: 'Company Website', required: false },
];

const PLATFORM_OPTIONS = [
  { key: 'google_maps', label: 'Google Maps' },
  { key: 'linkedin', label: 'LinkedIn' },
  { key: 'facebook', label: 'Facebook' },
  { key: 'instagram', label: 'Instagram' },
  { key: 'yelp', label: 'Yelp' },
];

export function ColumnMapping({ previewData, onConfirm, onCancel, creditsBalance }) {
  const [mappings, setMappings] = useState({});
  const [errors, setErrors] = useState([]);
  const [companyNameHint, setCompanyNameHint] = useState(null);
  const [selectedPlatforms, setSelectedPlatforms] = useState(['google_maps', 'linkedin']);
  const [maxContactsTotal, setMaxContactsTotal] = useState(50);
  const [maxContactsPerCompany, setMaxContactsPerCompany] = useState(3);

  useEffect(() => {
    if (previewData?.suggested_mappings) {
      setMappings(previewData.suggested_mappings);
    }
  }, [previewData]);

  useEffect(() => {
    setErrors([]);
    setCompanyNameHint(null);
  }, [mappings]);

  const handleMappingChange = (targetField, sourceColumn) => {
    setMappings(prev => ({
      ...prev,
      [targetField]: sourceColumn
    }));
    // Clear error if mapping is fixed
    if (sourceColumn) {
      setErrors(prev => prev.filter(e => e !== targetField));
    }
  };

  const handleConfirm = () => {
    const newErrors = [];
    REQUIRED_FIELDS.forEach(field => {
      if (field.required && !mappings[field.key]) {
        newErrors.push(field.key);
      }
    });

    const companyCol = mappings.company_name;
    if (companyCol) {
      const lower = companyCol.toLowerCase();
      if (/(url|website|domain|http|www|link)/i.test(lower)) {
        newErrors.push('company_name');
        setCompanyNameHint('Company Name must be the business name, not a website/url column.');
      } else {
        setCompanyNameHint(null);
      }
    }

    if (!selectedPlatforms || selectedPlatforms.length === 0) {
      newErrors.push('platforms');
    }

    if (!maxContactsTotal || maxContactsTotal < 1) {
      newErrors.push('max_total');
    }

    if (!maxContactsPerCompany || maxContactsPerCompany < 1) {
      newErrors.push('max_per_company');
    }

    if (maxContactsPerCompany > maxContactsTotal) {
      newErrors.push('max_per_company');
      setCompanyNameHint((prev) => prev || 'Per-company limit cannot exceed overall limit.');
    }

    if (newErrors.length > 0) {
      setErrors(newErrors);
      return;
    }

    onConfirm(mappings, {
      selected_platforms: selectedPlatforms,
      max_contacts_total: maxContactsTotal,
      max_contacts_per_company: maxContactsPerCompany,
    });
  };

  if (!previewData) return null;

  return (
    <div className="w-full max-w-4xl mx-auto p-6">
      <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <div className="p-6 border-b border-gray-700">
          <h2 className="text-xl font-semibold">Map Columns</h2>
          <p className="text-gray-400 mt-1">
            Map columns from your CSV to the required fields.
            We found {previewData.total_rows} rows in {previewData.filename}.
          </p>
        </div>

        <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Mapping Form */}
          <div className="space-y-4">
            <h3 className="font-medium text-gray-300 mb-4">Field Mapping</h3>
            {REQUIRED_FIELDS.map(field => (
              <div key={field.key} className="space-y-1">
                <label className="text-sm font-medium text-gray-400 flex items-center justify-between">
                  <span>
                    {field.label}
                    {field.required && <span className="text-red-400 ml-1">*</span>}
                  </span>
                  {errors.includes(field.key) && (
                    <span className="text-xs text-red-400">Required</span>
                  )}
                </label>
                {field.key === 'company_name' && companyNameHint && (
                  <div className="text-xs text-yellow-300">{companyNameHint}</div>
                )}
                <select
                  value={mappings[field.key] || ''}
                  onChange={(e) => handleMappingChange(field.key, e.target.value)}
                  className={`w-full bg-gray-900 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 transition-colors ${
                    errors.includes(field.key)
                      ? 'border-red-500 focus:ring-red-500/20'
                      : 'border-gray-700 focus:border-blue-500 focus:ring-blue-500/20'
                  }`}
                >
                  <option value="">-- Select Column --</option>
                  {previewData.columns.map(col => (
                    <option key={col} value={col}>{col}</option>
                  ))}
                </select>
              </div>
            ))}

            <div className="pt-6">
              <h3 className="font-medium text-gray-300 mb-3">Research Options</h3>

              <div className="space-y-3">
                <div className="space-y-2">
                  <div className="text-xs text-gray-400">Platforms</div>
                  <div className="grid grid-cols-1 gap-2">
                    {PLATFORM_OPTIONS.map((p) => (
                      <label key={p.key} className="flex items-center gap-2 text-sm text-gray-300">
                        <input
                          type="checkbox"
                          checked={selectedPlatforms.includes(p.key)}
                          onChange={(e) => {
                            setSelectedPlatforms((prev) => {
                              if (e.target.checked) return [...prev, p.key];
                              return prev.filter((x) => x !== p.key);
                            });
                          }}
                          className="accent-blue-500"
                        />
                        {p.label}
                      </label>
                    ))}
                  </div>
                  {errors.includes('platforms') && (
                    <div className="text-xs text-red-400">Select at least one platform.</div>
                  )}
                </div>

                <div className="space-y-2">
                  <div className="text-xs text-gray-400">Overall Contact Finding Limit</div>
                  <input
                    type="number"
                    min={1}
                    value={maxContactsTotal}
                    onChange={(e) => setMaxContactsTotal(Number(e.target.value))}
                    className={
                      'w-full bg-gray-900 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 transition-colors ' +
                      (errors.includes('max_total') ? 'border-red-500 focus:ring-red-500/20' : 'border-gray-700 focus:border-blue-500 focus:ring-blue-500/20')
                    }
                  />
                </div>

                <div className="space-y-2">
                  <div className="text-xs text-gray-400">Contacts Found Per Company Limit</div>
                  <input
                    type="number"
                    min={1}
                    value={maxContactsPerCompany}
                    onChange={(e) => setMaxContactsPerCompany(Number(e.target.value))}
                    className={
                      'w-full bg-gray-900 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 transition-colors ' +
                      (errors.includes('max_per_company') ? 'border-red-500 focus:ring-red-500/20' : 'border-gray-700 focus:border-blue-500 focus:ring-blue-500/20')
                    }
                  />
                </div>

                <div className="text-xs text-gray-400">
                  Estimated credits: {Math.max(1, selectedPlatforms.length) * maxContactsTotal}
                  {typeof creditsBalance === 'number' && ` • Available: ${creditsBalance}`}
                </div>
              </div>
            </div>
          </div>

          {/* Data Preview */}
          <div className="md:col-span-2 space-y-4">
            <h3 className="font-medium text-gray-300 mb-4">File Preview</h3>
            <div className="overflow-x-auto border border-gray-700 rounded-lg">
              <table className="w-full text-sm text-left">
                <thead className="text-xs text-gray-400 uppercase bg-gray-900/50">
                  <tr>
                    {previewData.columns.map(col => (
                      <th key={col} className="px-4 py-3 whitespace-nowrap border-b border-gray-700">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-700">
                  {previewData.preview_rows.map((row, idx) => (
                    <tr key={idx} className="bg-gray-800/50 hover:bg-gray-800">
                      {previewData.columns.map(col => (
                        <td key={`${idx}-${col}`} className="px-4 py-3 whitespace-nowrap text-gray-300">
                          {row[col]}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div className="p-6 border-t border-gray-700 bg-gray-900/30 flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm font-medium text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            className="px-4 py-2 text-sm font-medium bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors flex items-center gap-2"
          >
            Start Processing
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
