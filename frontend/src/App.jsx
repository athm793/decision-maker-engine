import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { FileUpload } from './components/FileUpload';
import { ColumnMapping } from './components/ColumnMapping';
import { JobProgress } from './components/JobProgress';
import { ResultsTable } from './components/ResultsTable';
import { JobHistory } from './components/JobHistory';
import { ChevronLeft, ChevronRight, Loader2, Square } from 'lucide-react';
import { Link } from 'react-router-dom';
import { TopBar } from './components/TopBar';
import { useAuth } from './auth/AuthProvider.jsx';

function App() {
  const { user, signOut } = useAuth();
  const [step, setStep] = useState('upload'); // upload, mapping, creating_job, processing
  const [file, setFile] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [isCancelling, setIsCancelling] = useState(false);
  const [jobTimerStartMs, setJobTimerStartMs] = useState(null);
  const [uploadErrorPopup, setUploadErrorPopup] = useState(null);
  
  // Job State
  const [job, setJob] = useState(null);
  const [results, setResults] = useState([]);
  const [resultsTotal, setResultsTotal] = useState(0);
  const [resultsQueryInput, setResultsQueryInput] = useState('');
  const [resultsQuery, setResultsQuery] = useState('');
  const [resultsOffset, setResultsOffset] = useState(0);
  const [resultsLimit, setResultsLimit] = useState(50);
  const [isResultsLoading, setIsResultsLoading] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);

  const [jobHistory, setJobHistory] = useState([]);
  const [isJobHistoryLoading, setIsJobHistoryLoading] = useState(false);
  const [creditsBalance, setCreditsBalance] = useState(null);
  const jobStatus = job?.status;
  const [navBackStack, setNavBackStack] = useState([]);
  const [navForwardStack, setNavForwardStack] = useState([]);
  const [navHint, setNavHint] = useState(null);
  const navHintTimerRef = useRef(null);
  const uploadErrorTimerRef = useRef(null);

  const captureNavState = () => {
    return { step, jobId: jobId || null };
  };

  const pushNavBack = (state) => {
    setNavBackStack((prev) => {
      const next = [...prev, state];
      return next.length > 50 ? next.slice(next.length - 50) : next;
    });
  };

  const pushNavForward = (state) => {
    setNavForwardStack((prev) => {
      const next = [...prev, state];
      return next.length > 50 ? next.slice(next.length - 50) : next;
    });
  };

  const showNavHint = (message) => {
    setNavHint(message);
    if (navHintTimerRef.current) clearTimeout(navHintTimerRef.current);
    navHintTimerRef.current = setTimeout(() => setNavHint(null), 1200);
  };

  useEffect(() => {
    if (!error) return;
    if (!['upload', 'mapping', 'creating_job'].includes(step)) return;
    setUploadErrorPopup(String(error));
    if (uploadErrorTimerRef.current) clearTimeout(uploadErrorTimerRef.current);
    uploadErrorTimerRef.current = setTimeout(() => setUploadErrorPopup(null), 5000);
    return () => {
      if (uploadErrorTimerRef.current) clearTimeout(uploadErrorTimerRef.current);
    };
  }, [error, step]);

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
    let inFlight = false;

    const fetchCredits = async () => {
      if (inFlight) return;
      inFlight = true;
      try {
        const response = await axios.get('/api/credits', { timeout: 10000 });
        setCreditsBalance(response.data.balance);
      } catch {
        setCreditsBalance(null);
      } finally {
        inFlight = false;
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
      const response = await axios.post('/api/upload/preview', formData, { timeout: 120000 });

      setPreviewData(response.data);
      setStep('mapping');
    } catch (err) {
      console.error('Upload failed:', err);
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;
      const isTimeout = err?.code === 'ECONNABORTED';
      const message =
        (status ? `Upload failed (${status}). ` : 'Upload failed. ') +
        (detail || (isTimeout ? 'Timed out while processing the CSV. Try a smaller file or remove unusual formatting.' : (err?.message || 'Please try again.')));
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
        const text = String(e.target.result || '');
        const parseCsvLine = (line) => {
          const out = [];
          let cur = '';
          let inQuotes = false;
          for (let i = 0; i < line.length; i += 1) {
            const ch = line[i];
            if (ch === '"') {
              const next = line[i + 1];
              if (inQuotes && next === '"') {
                cur += '"';
                i += 1;
                continue;
              }
              inQuotes = !inQuotes;
              continue;
            }
            if (ch === ',' && !inQuotes) {
              out.push(cur);
              cur = '';
              continue;
            }
            cur += ch;
          }
          out.push(cur);
          return out;
        };

        const normalizeHeaders = (rawHeaders) => {
          const used = new Map();
          return rawHeaders.map((h, idx) => {
            const base = String(h ?? '').trim();
            const initial = base ? base : `Unnamed: ${idx}`;
            const count = (used.get(initial) || 0) + 1;
            used.set(initial, count);
            if (count === 1) return initial;
            return `${initial}.${count - 1}`;
          });
        };

        const lines = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');
        const nonEmptyLines = lines.filter((l) => String(l || '').trim().length > 0);
        if (nonEmptyLines.length === 0) {
          setError('CSV file is empty.');
          setStep('mapping');
          console.groupEnd();
          return;
        }

        const headerFields = parseCsvLine(nonEmptyLines[0]);
        const headers = normalizeHeaders(headerFields);
        const data = [];

        for (let i = 1; i < nonEmptyLines.length; i += 1) {
          const fields = parseCsvLine(nonEmptyLines[i]);
          const obj = {};
          for (let c = 0; c < headers.length; c += 1) {
            obj[headers[c]] = String(fields[c] ?? '').trim();
          }
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

            if (!mappings?.company_name) {
              setError('Missing required mapping: Company Name');
              setStep('mapping');
              console.groupEnd();
              return;
            }
            if (!mappings?.location) {
              setError('Missing required mapping: Address');
              setStep('mapping');
              console.groupEnd();
              return;
            }
            const companyCol = mappings?.company_name;
            const websiteCol = mappings?.website;
            const kept = [];
            let missingIdentityRows = 0;
            for (const rowObj of unique) {
              const companyVal = companyCol ? String(rowObj?.[companyCol] ?? '').trim() : '';
              const websiteVal = websiteCol ? String(rowObj?.[websiteCol] ?? '').trim() : '';
              if (companyVal || websiteVal) kept.push(rowObj);
              else missingIdentityRows += 1;
            }
            if (missingIdentityRows > 0) {
              setNotice((prev) => {
                const msg = `${missingIdentityRows} row${missingIdentityRows === 1 ? '' : 's'} were skipped because both Company Name and Company Website were blank.`;
                return prev ? `${prev} ${msg}` : msg;
              });
            }
            if (kept.length === 0) {
              setError('All rows were blank for both Company Name and Company Website. Fill at least one of those fields, or map Company Website.');
              setStep('mapping');
              console.groupEnd();
              return;
            }

            console.log('[create job] POST /api/jobs rows=%s', kept.length);
            const response = await axios.post('/api/jobs', {
                filename: file.name,
                mappings: mappings,
                file_content: kept,
                selected_platforms: options?.selected_platforms || [],
                deep_search: Boolean(options?.deep_search),
                job_titles: (options?.job_titles && options.job_titles.length > 0) ? options.job_titles : null,
            });
            
            setJobId(response.data.id);
            setJob(response.data);
            setJobTimerStartMs(Date.now());
            setResultsQueryInput('');
            setResultsQuery('');
            setResultsOffset(0);
            setResultsLimit(50);
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
    setJobTimerStartMs(null);
    setStep('upload');
  };

  const handleNewJob = () => {
    if (step !== 'upload') {
      pushNavBack(captureNavState());
      setNavForwardStack([]);
    }
    setFile(null);
    setPreviewData(null);
    setError(null);
    setNotice(null);
    setJobId(null);
    setJob(null);
    setJobTimerStartMs(null);
    setResults([]);
    setResultsTotal(0);
    setResultsQueryInput('');
    setResultsQuery('');
    setResultsOffset(0);
    setResultsLimit(25);
    setStep('upload');
  }

  const handleSelectJobFromHistory = (id, options = {}) => {
    const shouldPush = options.pushNav !== false;
    if (shouldPush) {
      pushNavBack(captureNavState());
      setNavForwardStack([]);
    }
    setError(null);
    setNotice(null);
    setJobId(id);
    setJob(null);
    setJobTimerStartMs(Date.now());
    setResults([]);
    setResultsTotal(0);
    setResultsQueryInput('');
    setResultsQuery('');
    setResultsOffset(0);
    setResultsLimit(25);
    setStep('processing');
  };

  const handleNavBack = () => {
    if (navBackStack.length) {
      const prev = navBackStack[navBackStack.length - 1];
      setNavBackStack((s) => s.slice(0, -1));
      pushNavForward(captureNavState());
      if (prev.step === 'processing' && prev.jobId) {
        handleSelectJobFromHistory(prev.jobId, { pushNav: false });
        return;
      }
      handleNewJob();
      return;
    }

    if (step === 'upload') {
      showNavHint('No previous view.');
      return;
    }
    if (step === 'mapping') {
      handleCancel();
      return;
    }
    handleNewJob();
  };

  const handleNavForward = () => {
    if (navForwardStack.length) {
      const next = navForwardStack[navForwardStack.length - 1];
      setNavForwardStack((s) => s.slice(0, -1));
      pushNavBack(captureNavState());
      if (next.step === 'processing' && next.jobId) {
        handleSelectJobFromHistory(next.jobId, { pushNav: false });
        return;
      }
      handleNewJob();
      return;
    }
    showNavHint('No next view.');
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
      <TopBar
        left={
          <div className="flex items-center gap-2 min-w-0">
            <div className="flex items-center gap-1">
              <button
                type="button"
                className={
                  'mac-btn px-2 py-2 text-xs ' +
                  (step === 'upload' && navBackStack.length === 0 ? 'opacity-50 cursor-not-allowed' : '')
                }
                onClick={handleNavBack}
                aria-label="Back"
                title="Back"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                type="button"
                className={'mac-btn px-2 py-2 text-xs ' + (navForwardStack.length === 0 ? 'opacity-50 cursor-not-allowed' : '')}
                onClick={handleNavForward}
                aria-label="Forward"
                title="Forward"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
            <div className="min-w-0">
              <div className="text-sm sm:text-base font-semibold tracking-tight truncate">localcontacts.biz</div>
            </div>
          </div>
        }
        menuTitle="Account"
        menuItems={({ close }) => (
          <>
            <div className="mac-card p-3 text-xs">
              <div className="mac-muted">Signed in</div>
              <div className="pt-1 font-semibold truncate">{user?.email || '—'}</div>
              <div className="pt-2 mac-muted">
                Credits: <span className="text-[var(--text)]">{typeof creditsBalance === 'number' ? creditsBalance : '—'}</span>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Link className="mac-btn px-3 py-2 text-xs text-center" to="/plans" onClick={close}>
                Plans
              </Link>
              <Link className="mac-btn px-3 py-2 text-xs text-center" to="/admin" onClick={close}>
                Admin
              </Link>
            </div>
            <button
              type="button"
              className="mac-btn mac-btn-primary px-3 py-2 text-xs w-full"
              onClick={async () => {
                close();
                await signOut();
              }}
            >
              Sign out
            </button>
          </>
        )}
      />

      <main className="max-w-7xl mx-auto px-5 sm:px-6 lg:px-8 py-10">
        {navHint && (
          <div className="mb-4">
            <div className="inline-flex mac-card px-3 py-2 text-xs mac-muted">{navHint}</div>
          </div>
        )}
        {step === 'upload' && (
          <div className="space-y-8">
            <div className="text-center space-y-3">
              <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight">
                Find Local Decision Makers in Seconds
              </h1>
              <p className="text-base sm:text-lg mac-muted max-w-2xl mx-auto">
                Upload your business list and let our AI agent find real decision makers with evidence.
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
            <div className="space-y-4 animate-in fade-in duration-500">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="px-3 py-1 rounded-full bg-[color:var(--surface2)] border border-[color:var(--border)] text-xs mac-muted flex-shrink-0">
                      {(job.status || '').toString().toUpperCase()}
                    </div>
                    <div className="text-sm font-semibold truncate">Job #{job.id}</div>
                    {job.status === 'completed' && <div className="text-xs mac-muted flex-shrink-0">Results are final</div>}
                    {job.status === 'cancelled' && <div className="text-xs mac-muted flex-shrink-0">Stopped early</div>}
                    {job.status === 'failed' && <div className="text-xs mac-muted flex-shrink-0">Failed</div>}
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                      {['queued', 'processing'].includes(job.status) && (
                        <button
                            onClick={handleStopJob}
                            disabled={isCancelling}
                            className="mac-button mac-button-danger px-3 py-2 disabled:opacity-50 disabled:cursor-not-allowed text-xs font-medium flex items-center gap-2"
                        >
                            <Square className="w-4 h-4" />
                            {isCancelling ? 'Stopping…' : 'Stop'}
                        </button>
                      )}
                      <button
                          onClick={handleNewJob}
                          className="mac-button px-3 py-2 text-xs font-medium"
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

                <JobProgress job={job} timerStartMs={jobTimerStartMs} />
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
      {uploadErrorPopup && (
        <div className="fixed bottom-6 right-6 z-50 max-w-md">
          <div
            className="mac-card p-4 text-sm shadow-lg"
            style={{
              borderColor: 'color-mix(in srgb, var(--danger) 35%, var(--border))',
              background: 'color-mix(in srgb, var(--danger-weak) 60%, var(--surface))',
              color: 'var(--danger)',
            }}
          >
            <div className="whitespace-pre-wrap">{uploadErrorPopup}</div>
            <div className="mt-3 flex justify-end">
              <button
                type="button"
                className="mac-button px-4 py-2 text-xs font-medium"
                onClick={() => {
                  setUploadErrorPopup(null);
                  setError(null);
                }}
              >
                OK
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
