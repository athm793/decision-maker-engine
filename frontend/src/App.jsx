import { useState, useEffect } from 'react';
import axios from 'axios';
import { FileUpload } from './components/FileUpload';
import { ColumnMapping } from './components/ColumnMapping';
import { JobProgress } from './components/JobProgress';
import { ResultsTable } from './components/ResultsTable';
import { JobHistory } from './components/JobHistory';
import { Loader2, Square } from 'lucide-react';
import { ThemeToggle } from './components/ThemeToggle';

function App() {
  const [step, setStep] = useState('upload'); // upload, mapping, creating_job, processing
  const [file, setFile] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [isCancelling, setIsCancelling] = useState(false);
  
  // Job State
  const [job, setJob] = useState(null);
  const [results, setResults] = useState([]);
  const [resultsTotal, setResultsTotal] = useState(0);
  const [resultsQueryInput, setResultsQueryInput] = useState('');
  const [resultsQuery, setResultsQuery] = useState('');
  const [resultsOffset, setResultsOffset] = useState(0);
  const [resultsLimit, setResultsLimit] = useState(25);
  const [isResultsLoading, setIsResultsLoading] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);

  const [jobHistory, setJobHistory] = useState([]);
  const [isJobHistoryLoading, setIsJobHistoryLoading] = useState(false);
  const [creditsBalance, setCreditsBalance] = useState(null);
  const jobStatus = job?.status;

  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem('theme');
    if (saved === 'light' || saved === 'dark') return saved;
    return (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light';
  });

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    localStorage.setItem('theme', theme);
  }, [theme]);

  // Polling Effect
  useEffect(() => {
    let interval;
    if (step === 'processing' && jobId) {
      const fetchJobStatus = async () => {
        try {
          console.log('[poll job] GET /api/jobs/%s', jobId);
          const jobRes = await axios.get(`/api/jobs/${jobId}`);

          setJob(jobRes.data);

          if (['completed', 'failed', 'cancelled'].includes(jobRes.data.status)) {
            if (interval) clearInterval(interval);
          }
        } catch (err) {
          console.error("Error polling job:", err);
          const status = err?.response?.status;
          const detail = err?.response?.data?.detail;
          setError((status ? `Error polling job (${status}). ` : 'Error polling job. ') + (detail || err?.message || ''));
        }
      };

      fetchJobStatus(); // Initial fetch
      interval = setInterval(fetchJobStatus, 2000); // Poll every 2s
    }
    return () => clearInterval(interval);
  }, [step, jobId]);

  useEffect(() => {
    const t = setTimeout(() => setResultsQuery(resultsQueryInput.trim()), 300);
    return () => clearTimeout(t);
  }, [resultsQueryInput]);

  useEffect(() => {
    let interval;

    const fetchResults = async () => {
      if (!jobId) return;
      setIsResultsLoading(true);
      try {
        console.log('[poll results] GET /api/jobs/%s/results/paged', jobId);
        const response = await axios.get(`/api/jobs/${jobId}/results/paged`, {
          params: {
            q: resultsQuery || undefined,
            limit: resultsLimit,
            offset: resultsOffset,
          },
        });

        setResults(response.data.items);
        setResultsTotal(response.data.total);
      } catch (err) {
        console.error('Error fetching results:', err);
      } finally {
        setIsResultsLoading(false);
      }
    };

    if (step === 'processing' && jobId) {
      fetchResults();
      if (jobStatus && ['queued', 'processing'].includes(jobStatus)) {
        interval = setInterval(fetchResults, 2000);
      }
    }

    return () => clearInterval(interval);
  }, [step, jobId, jobStatus, resultsQuery, resultsOffset, resultsLimit]);

  const fetchJobHistory = async () => {
    setIsJobHistoryLoading(true);
    try {
      const response = await axios.get('/api/jobs', { params: { limit: 25, offset: 0 } });
      setJobHistory(response.data);
    } catch (err) {
      console.error('Error fetching job history:', err);
    } finally {
      setIsJobHistoryLoading(false);
    }
  };

  useEffect(() => {
    if (step === 'upload') {
      fetchJobHistory();
    }
  }, [step]);

  useEffect(() => {
    let interval;

    const fetchCredits = async () => {
      try {
        const response = await axios.get('/api/credits');
        setCreditsBalance(response.data.balance);
      } catch {
        setCreditsBalance(null);
      }
    };

    fetchCredits();
    const fast = step === 'processing' && jobStatus && ['queued', 'processing'].includes(jobStatus);
    interval = setInterval(fetchCredits, fast ? 2000 : 10000);
    return () => clearInterval(interval);
  }, [step, jobStatus]);

  const handleStopJob = async () => {
    if (!jobId || isCancelling) return;
    setIsCancelling(true);
    setError(null);

    try {
      const response = await axios.post(`/api/jobs/${jobId}/cancel`);
      setJob(response.data);
    } catch (err) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;
      setError((status ? `Failed to stop job (${status}). ` : 'Failed to stop job. ') + (detail || err?.message || ''));
    } finally {
      setIsCancelling(false);
    }
  };

  const handleFileSelect = async (selectedFile) => {
    setFile(selectedFile);
    setIsUploading(true);
    setError(null);
    setNotice(null);

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const response = await axios.post('/api/upload/preview', formData);

      setPreviewData(response.data);
      setStep('mapping');
    } catch (err) {
      console.error('Upload failed:', err);
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;
      const message =
        (status ? `Upload failed (${status}). ` : 'Upload failed. ') +
        (detail || err?.message || 'Please try again.');
      setError(message);
    } finally {
      setIsUploading(false);
    }
  };

  const handleMappingConfirm = async (mappings, options) => {
    try {
      setStep('creating_job');
      setError(null);
      setNotice(null);
      console.groupCollapsed('[create job] start');
      console.log('filename:', file?.name);
      console.log('mappings:', mappings);
      console.log('options:', options);
      
      const reader = new FileReader();
      reader.onload = async (e) => {
        const text = e.target.result;
        const lines = text.split('\n');
        const headers = lines[0].split(',').map(h => h.trim());
        const data = [];
        
        for(let i = 1; i < lines.length; i++) {
            if(!lines[i].trim()) continue;
            const row = lines[i].split(',');
            const obj = {};
            headers.forEach((h, index) => {
                obj[h] = row[index]?.trim();
            });
            data.push(obj);
        }

        try {
            const seen = new Set();
            const unique = [];
            let duplicates = 0;
            for (const obj of data) {
              const key = headers.map((h) => String(obj?.[h] ?? '')).join('\u001f');
              if (seen.has(key)) {
                duplicates += 1;
                continue;
              }
              seen.add(key);
              unique.push(obj);
            }
            if (duplicates > 0) {
              setNotice(`${duplicates} duplicate row${duplicates === 1 ? '' : 's'} were removed before processing.`);
            }

            const requiredKeys = ['company_name', 'google_maps_url', 'industry', 'city', 'country', 'location', 'website'];
            const missingMappings = requiredKeys.filter((k) => !mappings?.[k]);
            if (missingMappings.length > 0) {
              setError(`Missing required mappings: ${missingMappings.join(', ')}`);
              setStep('mapping');
              console.groupEnd();
              return;
            }
            const requiredColumns = requiredKeys.map((k) => mappings[k]);
            let blankRows = 0;
            for (const rowObj of unique) {
              for (const col of requiredColumns) {
                if (!String(rowObj?.[col] ?? '').trim()) {
                  blankRows += 1;
                  break;
                }
              }
            }
            if (blankRows > 0) {
              setError(`Some rows have blank values in required columns. Fix your CSV and re-upload. (rows affected: ${blankRows})`);
              setStep('mapping');
              console.groupEnd();
              return;
            }

            console.log('[create job] POST /api/jobs rows=%s', unique.length);
            const response = await axios.post('/api/jobs', {
                filename: file.name,
                mappings: mappings,
                file_content: unique,
                selected_platforms: options?.selected_platforms || [],
                max_contacts_total: options?.max_contacts_total || 50,
                max_contacts_per_company: options?.max_contacts_per_company || 1,
            });
            
            setJobId(response.data.id);
            setJob(response.data);
            setResultsQueryInput('');
            setResultsQuery('');
            setResultsOffset(0);
            setResultsLimit(25);
            setStep('processing');
            console.log('[create job] ok id=%s', response.data.id);
            console.groupEnd();
        } catch (err) {
            console.error('[create job] failed:', err);
            const status = err?.response?.status;
            const detail = err?.response?.data?.detail;
            setError((status ? `Failed to create job (${status}). ` : 'Failed to create job. ') + (detail || err?.message || ''));
            setStep('mapping');
            console.groupEnd();
        }
      };
      reader.onerror = (e) => {
        console.error('[create job] FileReader error:', e);
        setError('Failed to read file in browser.');
        setStep('mapping');
        console.groupEnd();
      };
      reader.onabort = () => {
        console.warn('[create job] FileReader aborted');
        setError('File reading was aborted.');
        setStep('mapping');
        console.groupEnd();
      };
      reader.readAsText(file);

    } catch (err) {
      console.error('[create job] unexpected error:', err);
      setError('Failed to create job.');
      setStep('mapping');
      console.groupEnd();
    }
  };

  const handleCancel = () => {
    setFile(null);
    setPreviewData(null);
    setError(null);
    setNotice(null);
    setStep('upload');
  };

  const handleNewJob = () => {
    setFile(null);
    setPreviewData(null);
    setError(null);
    setNotice(null);
    setJobId(null);
    setJob(null);
    setResults([]);
    setResultsTotal(0);
    setResultsQueryInput('');
    setResultsQuery('');
    setResultsOffset(0);
    setResultsLimit(25);
    setStep('upload');
  }

  const handleSelectJobFromHistory = (id) => {
    setError(null);
    setNotice(null);
    setJobId(id);
    setJob(null);
    setResults([]);
    setResultsTotal(0);
    setResultsQueryInput('');
    setResultsQuery('');
    setResultsOffset(0);
    setResultsLimit(25);
    setStep('processing');
  };

  const handleDownloadCsv = async () => {
    if (!jobId || isDownloading) return;
    setIsDownloading(true);
    setError(null);

    try {
      const response = await axios.get(`/api/jobs/${jobId}/results.csv`, {
        params: { q: resultsQuery || undefined },
        responseType: 'blob',
      });

      const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `job-${jobId}-results.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;
      setError((status ? `Failed to download CSV (${status}). ` : 'Failed to download CSV. ') + (detail || err?.message || ''));
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <header className="sticky top-0 z-10">
        <div className="border-b border-[color:var(--border)] bg-[color:var(--bg)]/70 backdrop-blur-md">
          <div className="max-w-7xl mx-auto px-5 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl flex items-center justify-center font-semibold text-white bg-[color:var(--accent)] shadow-sm">
              D
            </div>
            <span className="text-base sm:text-lg font-semibold tracking-tight">
              Decision Maker Discovery
            </span>
          </div>
          <div className="flex items-center gap-4">
            <div className="hidden sm:flex text-xs mac-muted mac-button px-3 py-2">
              Credits: <span className="ml-1 text-[var(--text)]">{typeof creditsBalance === 'number' ? creditsBalance : '—'}</span>
            </div>
            <ThemeToggle theme={theme} onChange={setTheme} />
          </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-5 sm:px-6 lg:px-8 py-10">
        {step === 'upload' && (
          <div className="space-y-8">
            <div className="text-center space-y-3">
              <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight">
                Find Decision Makers in Seconds
              </h1>
              <p className="text-base sm:text-lg mac-muted max-w-2xl mx-auto">
                Upload your business list and let our AI agents hunt down executives across LinkedIn, Google Maps, and more.
              </p>
            </div>
            
            <FileUpload 
              onFileSelect={handleFileSelect} 
              isUploading={isUploading}
              error={error}
            />

            <JobHistory
              jobs={jobHistory}
              isLoading={isJobHistoryLoading}
              onRefresh={fetchJobHistory}
              onSelectJob={handleSelectJobFromHistory}
            />
          </div>
        )}

        {step === 'mapping' && (
          <ColumnMapping
            previewData={previewData}
            onConfirm={handleMappingConfirm}
            onCancel={handleCancel}
            creditsBalance={creditsBalance}
            error={error}
            notice={notice}
          />
        )}
        
        {step === 'creating_job' && (
          <div className="flex flex-col items-center justify-center h-64 space-y-4">
            {notice && (
              <div className="mac-card p-4 text-sm" style={{ borderColor: 'color-mix(in srgb, var(--accent) 25%, var(--border))', background: 'color-mix(in srgb, var(--accent-weak) 60%, var(--surface))' }}>
                {notice}
              </div>
            )}
            <Loader2 className="w-10 h-10 text-[color:var(--accent)] animate-spin" />
            <p className="text-lg mac-muted">Creating Job…</p>
          </div>
        )}

        {step === 'processing' && job && (
            <div className="space-y-8 animate-in fade-in duration-500">
                <div className="flex justify-between items-center">
                    <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">Job Dashboard</h1>
                    <div className="flex items-center gap-3">
                        {['queued', 'processing'].includes(job.status) && (
                          <button
                              onClick={handleStopJob}
                              disabled={isCancelling}
                              className="mac-button-danger px-4 py-2 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium flex items-center gap-2"
                          >
                              <Square className="w-4 h-4" />
                              {isCancelling ? 'Stopping…' : 'Stop Job'}
                          </button>
                        )}
                        <button 
                            onClick={handleNewJob}
                            className="mac-button px-4 py-2 text-sm font-medium"
                        >
                            New Job
                        </button>
                    </div>
                </div>

                {error && (
                  <div className="mac-card p-4 text-sm" style={{ borderColor: 'color-mix(in srgb, var(--danger) 35%, var(--border))', background: 'color-mix(in srgb, var(--danger-weak) 60%, var(--surface))', color: 'var(--danger)' }}>
                    {error}
                  </div>
                )}
                {notice && !error && (
                  <div className="mac-card p-4 text-sm" style={{ borderColor: 'color-mix(in srgb, var(--accent) 25%, var(--border))', background: 'color-mix(in srgb, var(--accent-weak) 60%, var(--surface))' }}>
                    {notice}
                  </div>
                )}

                {job.status === 'completed' && (
                  <div className="mac-card p-4 text-sm" style={{ borderColor: 'color-mix(in srgb, var(--accent) 25%, var(--border))', background: 'color-mix(in srgb, var(--accent-weak) 60%, var(--surface))' }}>
                    Job completed. Results below are final.
                  </div>
                )}
                {job.status === 'cancelled' && (
                  <div className="mac-card p-4 text-sm mac-muted">
                    Job cancelled. Results below include anything found before stopping.
                  </div>
                )}
                {job.status === 'failed' && (
                  <div className="mac-card p-4 text-sm" style={{ borderColor: 'color-mix(in srgb, var(--danger) 35%, var(--border))', background: 'color-mix(in srgb, var(--danger-weak) 60%, var(--surface))', color: 'var(--danger)' }}>
                    Job failed. Check logs for details.
                  </div>
                )}

                <JobProgress job={job} />
                <ResultsTable
                  results={results}
                  total={resultsTotal}
                  query={resultsQueryInput}
                  onQueryChange={(value) => {
                    setResultsQueryInput(value);
                    setResultsOffset(0);
                  }}
                  offset={resultsOffset}
                  limit={resultsLimit}
                  onOffsetChange={setResultsOffset}
                  onLimitChange={(n) => {
                    setResultsLimit(n);
                    setResultsOffset(0);
                  }}
                  onDownload={handleDownloadCsv}
                  isDownloading={isDownloading}
                  isLoading={isResultsLoading}
                />
            </div>
        )}
        {step === 'processing' && !job && (
          <div className="flex flex-col items-center justify-center h-64 space-y-4">
            <Loader2 className="w-10 h-10 text-[color:var(--accent)] animate-spin" />
            <p className="text-lg mac-muted">Starting Job…</p>
            {error && (
              <div className="mac-card p-4 text-sm" style={{ borderColor: 'color-mix(in srgb, var(--danger) 35%, var(--border))', background: 'color-mix(in srgb, var(--danger-weak) 60%, var(--surface))', color: 'var(--danger)' }}>
                {error}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
