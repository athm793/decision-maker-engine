import React, { useState, useEffect } from 'react';
import { ArrowRight } from 'lucide-react';

const REQUIRED_FIELDS = [
  { key: 'company_name', label: 'Company Name', required: true },
  { key: 'industry', label: 'Company Type', required: false },
  { key: 'location', label: 'Address', required: true },
  { key: 'website', label: 'Company Website', required: false },
];

export function ColumnMapping({ previewData, onConfirm, onCancel, error, notice }) {
  const [mappings, setMappings] = useState({});
  const [errors, setErrors] = useState([]);
  const [companyNameHint, setCompanyNameHint] = useState(null);
  const [websiteHint, setWebsiteHint] = useState(null);
  const [deepSearch, setDeepSearch] = useState(false);
  const [jobTitles, setJobTitles] = useState([]);
  const [jobTitleDraft, setJobTitleDraft] = useState('');

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

  const parseList = (raw) => {
    return String(raw || '')
      .split(/[\n,]+/g)
      .map((s) => s.trim())
      .filter(Boolean);
  };

  const addJobTitlesFromRaw = (raw) => {
    const parts = String(raw || '').split(',').map((s) => s.trim()).filter(Boolean);
    if (parts.length === 0) return;
    setJobTitles((prev) => {
      const next = [...prev];
      for (const p of parts) {
        if (next.length >= 5) break;
        if (next.some((x) => String(x).toLowerCase() === p.toLowerCase())) continue;
        next.push(p);
      }
      return next;
    });
  };

  const commitDraftTitles = () => {
    const raw = String(jobTitleDraft || '').trim();
    if (!raw) return;
    addJobTitlesFromRaw(raw);
    setJobTitleDraft('');
  };

  const handleConfirm = () => {
    console.groupCollapsed('[Start Processing] validate + submit');
    console.log('mappings:', mappings);
    console.log('deepSearch:', deepSearch);
    console.log('jobTitles:', jobTitles);
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

    const titles = jobTitles.slice(0, 5);
    if (titles.length < 1) {
      newErrors.push('job_titles');
    }

    if (newErrors.length > 0) {
      console.warn('validation failed:', newErrors);
      setErrors(newErrors);
      console.groupEnd();
      return;
    }

    console.log('validation ok, calling onConfirm');
    onConfirm(mappings, {
      selected_platforms: ['linkedin'],
      deep_search: deepSearch,
      job_titles: titles,
    });
    console.groupEnd();
  };

  if (!previewData) return null;

  return (
    <div className="w-full max-w-7xl mx-auto p-4 sm:p-6 mac-appear">
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

        <div className="p-6 space-y-6">
          <div className="space-y-3">
            <h3 className="font-medium">File Preview</h3>
            <div className="border border-[color:var(--border)] rounded-2xl bg-[color:var(--surface)] overflow-hidden">
              <div className="overflow-auto max-h-[420px]">
                <table className="text-xs text-left table-auto min-w-max">
                  <thead className="text-[10px] mac-muted uppercase bg-[color:var(--surface2)] sticky top-0 z-10">
                    <tr>
                      {previewData.columns.map(col => (
                        <th key={col} className="px-3 py-2 border-b border-[color:var(--border)] font-semibold whitespace-nowrap">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[color:var(--border)]">
                    {previewData.preview_rows.map((row, idx) => (
                      <tr key={idx} className="hover:bg-[color:var(--surface2)] transition-colors">
                        {previewData.columns.map(col => (
                          <td key={`${idx}-${col}`} className="px-3 py-2 whitespace-nowrap">
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

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-4">
              <h3 className="font-medium">Field Mapping</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
              </div>
            </div>

            <div className="space-y-4">
              <h3 className="font-medium">Research Options</h3>
              <div className="space-y-3">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={deepSearch} onChange={(e) => setDeepSearch(e.target.checked)} className="accent-[var(--accent)]" />
                  Deep Search (+1 credit per company, adds location query)
                </label>
                <div className="text-xs mac-muted">
                  For Deep Search, mapping Company Website and Company Type can help find even more contacts.
                </div>

                <div className="space-y-2 pt-1">
                  <div className="text-xs mac-muted">
                    Job Titles (required, up to 5, comma-separated)
                  </div>
                  <div
                    className="w-full mac-input px-3 py-2 text-sm flex flex-wrap gap-2 items-center"
                    style={errors.includes('job_titles') ? { borderColor: 'color-mix(in srgb, var(--danger) 35%, var(--border))', boxShadow: '0 0 0 3px var(--danger-weak)' } : undefined}
                    onClick={() => document.getElementById('job-title-draft')?.focus()}
                  >
                    {jobTitles.map((t) => (
                      <span key={t} className="inline-flex items-center gap-2 px-2 py-1 rounded-lg bg-[color:var(--surface2)] border border-[color:var(--border)]">
                        <span>{t}</span>
                        <button
                          type="button"
                          className="mac-muted hover:text-[color:var(--text)]"
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            setJobTitles((prev) => prev.filter((x) => x !== t));
                          }}
                        >
                          ×
                        </button>
                      </span>
                    ))}
                    {jobTitles.length < 5 && (
                      <input
                        id="job-title-draft"
                        value={jobTitleDraft}
                        onChange={(e) => {
                          const v = e.target.value;
                          if (v.includes(',')) {
                            const parts = v.split(',');
                            addJobTitlesFromRaw(parts.slice(0, -1).join(','));
                            setJobTitleDraft(parts.slice(-1)[0]);
                          } else {
                            setJobTitleDraft(v);
                          }
                        }}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            commitDraftTitles();
                          }
                          if (e.key === ',' ) {
                            e.preventDefault();
                            commitDraftTitles();
                          }
                          if (e.key === 'Backspace' && !jobTitleDraft && jobTitles.length > 0) {
                            e.preventDefault();
                            setJobTitles((prev) => prev.slice(0, -1));
                          }
                        }}
                        onBlur={() => commitDraftTitles()}
                        placeholder={jobTitles.length === 0 ? 'e.g. CEO, Founder, Owner' : ''}
                        className="flex-1 min-w-[120px] bg-transparent outline-none"
                      />
                    )}
                  </div>
                </div>

                <div className="text-xs mac-muted">
                  {(() => {
                    const perCompany = 1 + (deepSearch ? 1 : 0);
                    const totalCompanies = Number(previewData?.total_rows || 0);
                    const maxCredits = perCompany * totalCompanies;
                    const fmt = new Intl.NumberFormat();
                    return `Approx. max credits for this job: ${fmt.format(maxCredits)} (${perCompany} per company)`;
                  })()}
                </div>
              </div>
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
            className="mac-button-primary px-4 py-2 rounded-xl text-sm font-medium transition-colors flex items-center gap-2"
          >
            Start Processing
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
