import React, { useState, useEffect } from 'react';
import { ArrowRight } from 'lucide-react';

const REQUIRED_FIELDS = [
  { key: 'company_name', label: 'Company Name', required: true },
  { key: 'industry', label: 'Company Type', required: true },
  { key: 'city', label: 'Company City', required: false },
  { key: 'country', label: 'Company Country', required: false },
  { key: 'location', label: 'Address', required: true },
  { key: 'website', label: 'Company Website', required: true },
];

const PLATFORM_OPTIONS = [
  { key: 'linkedin', label: 'LinkedIn' },
  { key: 'google_maps', label: 'Google Maps' },
  { key: 'facebook', label: 'Facebook' },
  { key: 'instagram', label: 'Instagram' },
  { key: 'yelp', label: 'Yelp' },
];

export function ColumnMapping({ previewData, onConfirm, onCancel, error, notice }) {
  const [mappings, setMappings] = useState({});
  const [errors, setErrors] = useState([]);
  const [companyNameHint, setCompanyNameHint] = useState(null);
  const [websiteHint, setWebsiteHint] = useState(null);
  const [selectedPlatforms, setSelectedPlatforms] = useState(['linkedin']);
  const [deepSearch, setDeepSearch] = useState(false);
  const [maxContactsTotal, setMaxContactsTotal] = useState(50);
  const [maxContactsPerCompany, setMaxContactsPerCompany] = useState(1);

  useEffect(() => {
    if (previewData?.suggested_mappings) {
      setMappings(previewData.suggested_mappings);
    }
  }, [previewData]);

  useEffect(() => {
    setErrors([]);
    setCompanyNameHint(null);
    setWebsiteHint(null);
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

  const isUrlLike = (raw) => {
    const v = String(raw || '').trim();
    if (!v) return false;
    if (/^https?:\/\//i.test(v)) return true;
    if (/^www\./i.test(v)) return true;
    if (/[a-z0-9-]+\.[a-z]{2,}/i.test(v) && !/\s/.test(v)) return true;
    return false;
  };

  const urlRatioForColumn = (col) => {
    if (!col) return 0;
    const rows = (previewData?.preview_rows || []).slice(0, 3);
    const values = rows.map((r) => r?.[col]).filter((x) => String(x || '').trim() !== '');
    if (values.length === 0) return 0;
    const urlCount = values.filter(isUrlLike).length;
    return urlCount / values.length;
  };

  const handleConfirm = () => {
    console.groupCollapsed('[Start Processing] validate + submit');
    console.log('mappings:', mappings);
    console.log('selectedPlatforms:', selectedPlatforms);
    console.log('deepSearch:', deepSearch);
    console.log('maxContactsTotal:', maxContactsTotal);
    console.log('maxContactsPerCompany:', maxContactsPerCompany);
    const newErrors = [];
    REQUIRED_FIELDS.forEach(field => {
      if (field.required && !mappings[field.key]) {
        newErrors.push(field.key);
      }
    });

    const companyCol = mappings.company_name;
    const websiteCol = mappings.website;
    if (companyCol) {
      const lower = companyCol.toLowerCase();
      if (/(url|website|domain|http|www|link)/i.test(lower) || urlRatioForColumn(companyCol) > 0.1) {
        setCompanyNameHint('Heads up: this looks like it might be a website/url column. That’s OK — we will try to infer the company name.');
      } else {
        setCompanyNameHint(null);
      }
    }

    if (companyCol && websiteCol && companyCol === websiteCol) {
      setWebsiteHint('Heads up: Company Name and Company Website are mapped to the same column. That’s OK — we will try to infer missing values.');
    } else {
      setWebsiteHint(null);
    }

    if (!selectedPlatforms || selectedPlatforms.length === 0) newErrors.push('platforms');

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
      console.warn('validation failed:', newErrors);
      setErrors(newErrors);
      console.groupEnd();
      return;
    }

    console.log('validation ok, calling onConfirm');
    onConfirm(mappings, {
      selected_platforms: selectedPlatforms,
      max_contacts_total: maxContactsTotal,
      max_contacts_per_company: maxContactsPerCompany,
      deep_search: deepSearch,
    });
    console.groupEnd();
  };

  if (!previewData) return null;

  return (
    <div className="w-full max-w-4xl mx-auto p-6 mac-appear">
      {error && (
        <div className="mb-4 p-4 mac-card text-sm mac-hover-lift" style={{ borderColor: 'color-mix(in srgb, var(--danger) 35%, var(--border))', background: 'color-mix(in srgb, var(--danger-weak) 60%, var(--surface))', color: 'var(--danger)' }}>
          {error}
        </div>
      )}
      {notice && (
        <div className="mb-4 p-4 mac-card text-sm mac-hover-lift" style={{ borderColor: 'color-mix(in srgb, var(--accent) 25%, var(--border))', background: 'color-mix(in srgb, var(--accent-weak) 60%, var(--surface))' }}>
          {notice}
        </div>
      )}
      <div className="mac-card overflow-hidden mac-hover-lift">
        <div className="p-6 border-b border-[color:var(--border)]">
          <h2 className="text-xl font-semibold">Map Columns</h2>
          <p className="mac-muted mt-1">
            Map columns from your CSV to the required fields.
            We found {previewData.total_rows} rows in {previewData.filename}.
          </p>
        </div>

        <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Mapping Form */}
          <div className="space-y-4">
            <h3 className="font-medium mb-4">Field Mapping</h3>
            {REQUIRED_FIELDS.map(field => (
              <div key={field.key} className="space-y-1">
                <label className="text-sm font-medium mac-muted flex items-center justify-between">
                  <span>
                    {field.label}
                    {field.required && <span className="text-red-400 ml-1">*</span>}
                  </span>
                  {errors.includes(field.key) && (
                    <span className="text-xs text-[color:var(--danger)]">{field.required ? 'Required' : 'Invalid'}</span>
                  )}
                </label>
                {field.key === 'company_name' && companyNameHint && (
                  <div className="text-xs mac-muted">{companyNameHint}</div>
                )}
                {field.key === 'website' && websiteHint && (
                  <div className="text-xs mac-muted">{websiteHint}</div>
                )}
                <select
                  value={mappings[field.key] || ''}
                  onChange={(e) => handleMappingChange(field.key, e.target.value)}
                  className={`w-full mac-input px-3 py-2 text-sm ${errors.includes(field.key) ? 'ring-2' : ''}`}
                  style={errors.includes(field.key) ? { borderColor: 'color-mix(in srgb, var(--danger) 35%, var(--border))', boxShadow: '0 0 0 3px var(--danger-weak)' } : undefined}
                >
                  <option value="">-- Select Column --</option>
                  {previewData.columns.map(col => (
                    <option key={col} value={col}>{col}</option>
                  ))}
                </select>
              </div>
            ))}

            <div className="pt-6">
              <h3 className="font-medium mb-3">Research Options</h3>

              <div className="space-y-3">
                <div className="space-y-2">
                  <div className="text-xs mac-muted">Platforms</div>
                  <div className="grid grid-cols-1 gap-2">
                    {PLATFORM_OPTIONS.map((p) => (
                      <label key={p.key} className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={selectedPlatforms.includes(p.key)}
                          disabled={p.key === 'linkedin'}
                          onChange={(e) => {
                            setSelectedPlatforms((prev) => {
                              let next = prev;
                              if (e.target.checked) {
                                next = Array.from(new Set([...prev, p.key]));
                              } else {
                                next = prev.filter((x) => x !== p.key);
                              }
                              if (!next.includes('linkedin')) {
                                next = ['linkedin', ...next];
                              }
                              return next;
                            });
                          }}
                          className="accent-[var(--accent)]"
                        />
                        {p.label}
                      </label>
                    ))}
                  </div>
                  <div className="text-xs mac-muted">
                    Choosing more than 2 platforms will cause the job to process for significantly longer.
                  </div>
                  <label className="flex items-center gap-2 text-sm pt-2">
                    <input
                      type="checkbox"
                      checked={deepSearch}
                      onChange={(e) => setDeepSearch(e.target.checked)}
                      className="accent-[var(--accent)]"
                    />
                    Deep Search (slower, better evidence) (+1 credit per contact found)
                  </label>
                  {errors.includes('platforms') && (
                    <div className="text-xs text-[color:var(--danger)]">Select at least one platform.</div>
                  )}
                </div>

                <div className="space-y-2">
                  <div className="text-xs mac-muted">Overall Contact Finding Limit</div>
                  <input
                    type="number"
                    min={1}
                    value={maxContactsTotal}
                    onChange={(e) => setMaxContactsTotal(Number(e.target.value))}
                    className="w-full mac-input px-3 py-2 text-sm"
                    style={errors.includes('max_total') ? { borderColor: 'color-mix(in srgb, var(--danger) 35%, var(--border))', boxShadow: '0 0 0 3px var(--danger-weak)' } : undefined}
                  />
                </div>

                <div className="space-y-2">
                  <div className="text-xs mac-muted">Contacts Found Per Company Limit</div>
                  <input
                    type="number"
                    min={1}
                    value={maxContactsPerCompany}
                    onChange={(e) => setMaxContactsPerCompany(Number(e.target.value))}
                    className="w-full mac-input px-3 py-2 text-sm"
                    style={errors.includes('max_per_company') ? { borderColor: 'color-mix(in srgb, var(--danger) 35%, var(--border))', boxShadow: '0 0 0 3px var(--danger-weak)' } : undefined}
                  />
                </div>

                <div className="text-xs mac-muted">
                  {(() => {
                    const perContact = Math.max(1, selectedPlatforms.length) + (deepSearch ? 1 : 0);
                    const maxCredits = perContact * (maxContactsTotal || 0);
                    const fmt = new Intl.NumberFormat();
                    return `Approx. max credits for this job: ${fmt.format(maxCredits)} (${perContact} per contact)`;
                  })()}
                </div>
              </div>
            </div>
          </div>

          {/* Data Preview */}
          <div className="md:col-span-2 space-y-4">
            <h3 className="font-medium mb-4">File Preview</h3>
            <div className="overflow-x-auto border border-[color:var(--border)] rounded-2xl bg-[color:var(--surface)]">
              <table className="w-full text-sm text-left">
                <thead className="text-[10px] mac-muted uppercase bg-[color:var(--surface2)]">
                  <tr>
                    {previewData.columns.map(col => (
                      <th key={col} className="px-4 py-3 whitespace-nowrap border-b border-[color:var(--border)] font-semibold">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[color:var(--border)]">
                  {previewData.preview_rows.map((row, idx) => (
                    <tr key={idx} className="hover:bg-[color:var(--surface2)] transition-colors">
                      {previewData.columns.map(col => (
                        <td key={`${idx}-${col}`} className="px-4 py-3 whitespace-nowrap">
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

        <div className="p-6 border-t border-[color:var(--border)] bg-[color:var(--surface2)] flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="mac-button px-4 py-2 text-sm font-medium"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={!selectedPlatforms || selectedPlatforms.length === 0}
            className={`mac-button-primary px-4 py-2 rounded-xl text-sm font-medium transition-colors flex items-center gap-2 ${(!selectedPlatforms || selectedPlatforms.length === 0) ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            Start Processing
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
