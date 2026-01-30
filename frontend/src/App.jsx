import { useState, useEffect } from 'react';
import axios from 'axios';
import { FileUpload } from './components/FileUpload';
import { ColumnMapping } from './components/ColumnMapping';
import { JobProgress } from './components/JobProgress';
import { ResultsTable } from './components/ResultsTable';
import { JobHistory } from './components/JobHistory';
import { Loader2, Square } from 'lucide-react';

function App() {
  const [step, setStep] = useState('upload'); // upload, mapping, creating_job, processing
  const [file, setFile] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState(null);
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

  // Polling Effect
  useEffect(() => {
    let interval;
    if (step === 'processing' && jobId) {
      const fetchJobStatus = async () => {
        try {
          const jobRes = await axios.get(`/api/jobs/${jobId}`);

          setJob(jobRes.data);

          if (['completed', 'failed', 'cancelled'].includes(jobRes.data.status)) {
            if (interval) clearInterval(interval);
          }
        } catch (err) {
          console.error("Error polling job:", err);
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
      if (job && ['queued', 'processing'].includes(job.status)) {
        interval = setInterval(fetchResults, 2000);
      }
    }

    return () => clearInterval(interval);
  }, [step, jobId, job?.status, resultsQuery, resultsOffset, resultsLimit]);

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
    const fetchCredits = async () => {
      try {
        const response = await axios.get('/api/credits');
        setCreditsBalance(response.data.balance);
      } catch (err) {
        setCreditsBalance(null);
      }
    };

    if (step === 'mapping') {
      fetchCredits();
    }
  }, [step]);

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
            const response = await axios.post('/api/jobs', {
                filename: file.name,
                mappings: mappings,
                file_content: data,
                selected_platforms: options?.selected_platforms || [],
                max_contacts_total: options?.max_contacts_total || 50,
                max_contacts_per_company: options?.max_contacts_per_company || 3,
            });
            
            setJobId(response.data.id);
            setResultsQueryInput('');
            setResultsQuery('');
            setResultsOffset(0);
            setResultsLimit(25);
            setStep('processing');
        } catch (err) {
            console.error(err);
            setError('Failed to create job.');
            setStep('mapping');
        }
      };
      reader.readAsText(file);

    } catch (err) {
      setError('Failed to create job.');
      setStep('mapping');
    }
  };

  const handleCancel = () => {
    setFile(null);
    setPreviewData(null);
    setError(null);
    setStep('upload');
  };

  const handleNewJob = () => {
    setFile(null);
    setPreviewData(null);
    setError(null);
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
    <div className="min-h-screen bg-gray-900 text-gray-100 font-sans">
      <header className="border-b border-gray-800 bg-gray-900/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center font-bold text-white">
              D
            </div>
            <span className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-teal-400">
              Decision Maker Discovery
            </span>
          </div>
          <nav className="flex gap-4 text-sm font-medium text-gray-400">
            <a href="#" className="hover:text-white transition-colors">Dashboard</a>
            <a href="#" className="hover:text-white transition-colors">Jobs</a>
            <a href="#" className="hover:text-white transition-colors">Settings</a>
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {step === 'upload' && (
          <div className="space-y-8">
            <div className="text-center space-y-4">
              <h1 className="text-4xl font-bold tracking-tight">
                Find Decision Makers in Seconds
              </h1>
              <p className="text-lg text-gray-400 max-w-2xl mx-auto">
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
          />
        )}
        
        {step === 'creating_job' && (
           <div className="flex flex-col items-center justify-center h-64 space-y-4">
             <Loader2 className="w-12 h-12 text-blue-500 animate-spin" />
             <p className="text-xl text-gray-300">Creating Job...</p>
           </div>
        )}

        {step === 'processing' && job && (
            <div className="space-y-8 animate-in fade-in duration-500">
                <div className="flex justify-between items-center">
                    <h1 className="text-2xl font-bold">Job Dashboard</h1>
                    <div className="flex items-center gap-3">
                        {['queued', 'processing'].includes(job.status) && (
                          <button
                              onClick={handleStopJob}
                              disabled={isCancelling}
                              className="px-4 py-2 bg-red-600/20 text-red-300 hover:bg-red-600/30 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
                          >
                              <Square className="w-4 h-4" />
                              {isCancelling ? 'Stopping…' : 'Stop Job'}
                          </button>
                        )}
                        <button 
                            onClick={handleNewJob}
                            className="px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm font-medium transition-colors"
                        >
                            New Job
                        </button>
                    </div>
                </div>

                {error && (
                  <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-300 text-sm">
                    {error}
                  </div>
                )}

                {job.status === 'completed' && (
                  <div className="p-4 bg-green-500/10 border border-green-500/20 rounded-lg text-green-200 text-sm">
                    Job completed. Results below are final.
                  </div>
                )}
                {job.status === 'cancelled' && (
                  <div className="p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-lg text-yellow-200 text-sm">
                    Job cancelled. Results below include anything found before stopping.
                  </div>
                )}
                {job.status === 'failed' && (
                  <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-200 text-sm">
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
      </main>
    </div>
  );
}

export default App;
