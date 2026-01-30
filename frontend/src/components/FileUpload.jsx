import React, { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { UploadCloud, FileType, AlertCircle } from 'lucide-react';
import { clsx } from 'clsx';
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
    <div className="w-full max-w-2xl mx-auto p-6">
      <div
        {...getRootProps()}
        className={twMerge(
          "border-2 border-dashed rounded-xl p-10 transition-all duration-200 ease-in-out cursor-pointer flex flex-col items-center justify-center text-center",
          isDragActive ? "border-blue-500 bg-blue-50/10" : "border-gray-600 hover:border-blue-400 hover:bg-gray-800/50",
          error ? "border-red-500 bg-red-500/10" : ""
        )}
      >
        <input {...getInputProps()} />
        
        <div className="bg-gray-800 p-4 rounded-full mb-4">
          <UploadCloud className="w-8 h-8 text-blue-400" />
        </div>

        <h3 className="text-xl font-semibold mb-2">
          {isDragActive ? "Drop the CSV file here" : "Upload Company List"}
        </h3>
        
        <p className="text-gray-400 mb-6 max-w-sm">
          Drag and drop your CSV file here, or click to browse.
          Supports files up to 50MB.
        </p>

        <div className="flex items-center gap-2 text-sm text-gray-500 bg-gray-800/50 px-4 py-2 rounded-lg">
          <FileType className="w-4 h-4" />
          <span>Supported format: CSV (UTF-8, Latin-1)</span>
        </div>
      </div>

      {error && (
        <div className="mt-4 p-4 bg-red-500/10 border border-red-500/20 rounded-lg flex items-start gap-3 text-red-400">
          <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
          <p className="text-sm">{error}</p>
        </div>
      )}

      {isUploading && (
        <div className="mt-6">
          <div className="flex justify-between text-sm mb-2 text-gray-300">
            <span>Uploading...</span>
            <span>100%</span>
          </div>
          <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
            <div className="h-full bg-blue-500 animate-pulse w-full"></div>
          </div>
        </div>
      )}
    </div>
  );
}
