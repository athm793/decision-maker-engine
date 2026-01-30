import { useState, useEffect } from 'react';
import axios from 'axios';
import { FileUpload } from './components/FileUpload';
import { ColumnMapping } from './components/ColumnMapping';
import { JobProgress } from './components/JobProgress';
import { ResultsTable } from './components/ResultsTable';
import { Loader2 } from 'lucide-react';

function App() {
  const [step, setStep] = useState('upload'); // upload, mapping, creating_job, processing
  const [file, setFile] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState(null);
  const [jobId, setJobId] = useState(null);
  
  // Job State
  const [job, setJob] = useState(null);
  const [results, setResults] = useState([]);

  // Polling Effect
  useEffect(() => {
    let interval;
    if (step === 'processing' && jobId) {
      const fetchJobStatus = async () => {
        try {
          const [jobRes, resultsRes] = await Promise.all([
            axios.get(`/api/jobs/${jobId}`),
            axios.get(`/api/jobs/${jobId}/results`)
          ]);
          
          setJob(jobRes.data);
          setResults(resultsRes.data);

          if (['completed', 'failed', 'cancelled'].includes(jobRes.data.status)) {
            // Stop polling eventually, or keep it to show final state
            // For now, we just keep polling to keep it simple, or reduce frequency
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

  const handleFileSelect = async (selectedFile) => {
    setFile(selectedFile);
    setIsUploading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const response = await axios.post('http://localhost:8000/api/upload/preview', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setPreviewData(response.data);
      setStep('mapping');
    } catch (err) {
      console.error('Upload failed:', err);
      setError(err.response?.data?.detail || 'Failed to upload file. Please try again.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleMappingConfirm = async (mappings) => {
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
                file_content: data
            });
            
            setJobId(response.data.id);
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
    setStep('upload');
  }

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
          </div>
        )}

        {step === 'mapping' && (
          <ColumnMapping
            previewData={previewData}
            onConfirm={handleMappingConfirm}
            onCancel={handleCancel}
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
                    <button 
                        onClick={handleNewJob}
                        className="px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm font-medium transition-colors"
                    >
                        New Job
                    </button>
                </div>

                <JobProgress job={job} />
                <ResultsTable results={results} />
            </div>
        )}
      </main>
    </div>
  );
}

export default App;
