import React, { useState, useEffect } from 'react';
import { Check, AlertCircle, ArrowRight } from 'lucide-react';

const REQUIRED_FIELDS = [
  { key: 'company_name', label: 'Company Name', required: true },
  { key: 'google_maps_url', label: 'Google Maps URL', required: false },
  { key: 'industry', label: 'Industry', required: false },
  { key: 'location', label: 'Location', required: false },
  { key: 'website', label: 'Website', required: false },
];

export function ColumnMapping({ previewData, onConfirm, onCancel }) {
  const [mappings, setMappings] = useState({});
  const [errors, setErrors] = useState([]);

  useEffect(() => {
    if (previewData?.suggested_mappings) {
      setMappings(previewData.suggested_mappings);
    }
  }, [previewData]);

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

    if (newErrors.length > 0) {
      setErrors(newErrors);
      return;
    }

    onConfirm(mappings);
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
