import React, { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { UploadCloud, FileType, AlertCircle } from 'lucide-react';
import { twMerge } from 'tailwind-merge';

export function FileUpload({ onFileSelect, isUploading, error }) {
  const onDrop = useCallback((acceptedFiles) => {
    if (acceptedFiles?.length > 0) {
      onFileSelect(acceptedFiles[0]);
    }
  }, [onFileSelect]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
      'application/vnd.ms-excel': ['.csv']
    },
    maxFiles: 1,
    multiple: false
  });

  return (
    <div className="w-full max-w-2xl mx-auto p-6 mac-appear">
      <div
        {...getRootProps()}
        className={twMerge(
          "border-2 border-dashed rounded-2xl p-10 transition-all duration-200 ease-in-out cursor-pointer flex flex-col items-center justify-center text-center mac-hover-lift",
          isDragActive ? "border-[color:var(--accent)] bg-[color:var(--accent-weak)]" : "border-[color:var(--border)] hover:border-[color:var(--accent)] hover:bg-[color:var(--surface2)]",
          error ? "border-[color:var(--danger)] bg-[color:var(--danger-weak)]" : ""
        )}
      >
        <input {...getInputProps()} />
        
        <div className="mac-card p-4 rounded-full mb-4 mac-sheen">
          <UploadCloud className="w-8 h-8 text-[color:var(--accent)]" />
        </div>

        <h3 className="text-xl font-semibold mb-2">
          {isDragActive ? "Drop the CSV file here" : "Upload Company List"}
        </h3>
        
        <p className="mac-muted mb-6 max-w-sm">
          Drag and drop your CSV file here, or click to browse.
          Supports files up to 50MB.
        </p>

        <div className="flex items-center gap-2 text-sm mac-muted bg-[color:var(--surface2)] px-4 py-2 rounded-xl border border-[color:var(--border)]">
          <FileType className="w-4 h-4" />
          <span>Supported format: CSV (UTF-8, Latin-1)</span>
        </div>
      </div>

      {error && (
        <div className="mt-4 p-4 mac-card flex items-start gap-3 text-[color:var(--danger)]" style={{ background: 'color-mix(in srgb, var(--danger-weak) 60%, var(--surface))', borderColor: 'color-mix(in srgb, var(--danger) 35%, var(--border))' }}>
          <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
          <p className="text-sm">{error}</p>
        </div>
      )}

      {isUploading && (
        <div className="mt-6">
          <div className="flex justify-between text-sm mb-2 mac-muted">
            <span>Uploading...</span>
            <span>100%</span>
          </div>
          <div className="h-2 bg-[color:var(--surface2)] border border-[color:var(--border)] rounded-full overflow-hidden">
            <div className="h-full bg-[color:var(--accent)] animate-pulse w-full"></div>
          </div>
        </div>
      )}
    </div>
  );
}
