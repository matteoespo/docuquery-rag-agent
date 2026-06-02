'use client';

import { useCallback, useState, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, FileText, Check, AlertCircle, X, RefreshCw, Database } from 'lucide-react';
import { useUploadStore } from '@/store/upload-store';
import { ProgressBar } from '@/components/ui/progress-bar';
import { StatusBadge } from '@/components/ui/status-badge';
import { fetchDocuments } from '@/services/api';

export function FileUpload() {
  const { phase, docCount, errorMessage, ingestionStatus, uploadProgress, upload, reset } = useUploadStore();
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [serverDocs, setServerDocs] = useState<{filename: string, size_mb: number}[]>([]);

  const loadDocuments = useCallback(async () => {
    try {
      const data = await fetchDocuments();
      setServerDocs(data.documents);
    } catch (e) {
      console.error('Failed to load documents:', e);
    }
  }, []);

  useEffect(() => {
    if (phase === 'idle' || phase === 'done') {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      loadDocuments();
    }
  }, [phase, loadDocuments]);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setSelectedFiles((prev) => [...prev, ...acceptedFiles]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
  });

  const removeFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUpload = () => {
    if (selectedFiles.length > 0) {
      upload(selectedFiles);
    }
  };

  const handleReset = () => {
    setSelectedFiles([]);
    reset();
  };

  return (
    <div className="flex flex-col h-full space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-zinc-100 flex items-center gap-2">
          <Upload size={18} className="text-blue-500" />
          Document Upload
        </h2>
        
        {phase === 'done' && <StatusBadge status="ready" />}
        {phase === 'uploading' && <StatusBadge status="processing" />}
        {phase === 'captioning' && <StatusBadge status="processing" />}
        {phase === 'error' && <StatusBadge status="error" />}
        {phase === 'idle' && <StatusBadge status="waiting" />}
      </div>

      <AnimatePresence mode="wait">
        {/* IDLE STATE */}
        {phase === 'idle' && (
          <motion.div
            key="idle"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="flex flex-col space-y-4"
          >
            <div
              {...getRootProps()}
              className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-colors ${
                isDragActive ? 'border-blue-500 bg-blue-500/10' : 'border-zinc-700/60 hover:border-blue-500/50 hover:bg-zinc-800/50'
              }`}
            >
              <input {...getInputProps()} />
              <div className="w-12 h-12 rounded-xl bg-blue-600/20 text-blue-500 flex items-center justify-center mx-auto mb-4 ring-1 ring-blue-500/30">
                <Upload size={24} />
              </div>
              <p className="text-sm font-medium text-zinc-300">
                {isDragActive ? 'Drop PDFs here' : 'Drag PDFs here or click to browse'}
              </p>
              <p className="text-xs text-zinc-500 mt-2">Only .pdf files are supported</p>
            </div>

            {selectedFiles.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider px-1">Selected Files</h3>
                <div className="max-h-48 overflow-y-auto space-y-2 pr-1 scrollbar-thin">
                  {selectedFiles.map((file, i) => (
                    <div key={`${file.name}-${i}`} className="flex items-center justify-between p-3 rounded-xl bg-zinc-800/50 border border-zinc-700/50 group">
                      <div className="flex items-center gap-3 overflow-hidden">
                        <FileText size={16} className="text-blue-400 flex-shrink-0" />
                        <span className="text-sm text-zinc-300 truncate">{file.name}</span>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          removeFile(i);
                        }}
                        className="text-zinc-500 hover:text-red-400 p-1 rounded-md opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <X size={14} />
                      </button>
                    </div>
                  ))}
                </div>
                
                <button
                  onClick={handleUpload}
                  className="w-full py-2.5 px-4 mt-4 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium flex items-center justify-center gap-2 transition-all active:scale-95 shadow-lg shadow-blue-500/20"
                >
                  <Upload size={18} />
                  Upload & Process
                </button>
              </div>
            )}

            {selectedFiles.length === 0 && serverDocs.length > 0 && (
              <div className="space-y-2 mt-4 pt-4 border-t border-zinc-800/60">
                <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider px-1 flex items-center gap-2">
                  <Database size={12} />
                  Database Documents
                </h3>
                <div className="max-h-48 overflow-y-auto space-y-2 pr-1 scrollbar-thin">
                  {serverDocs.map((doc, i) => (
                    <div key={`${doc.filename}-${i}`} className="flex items-center justify-between p-3 rounded-xl bg-zinc-800/20 border border-zinc-700/30">
                      <div className="flex items-center gap-3 overflow-hidden">
                        <FileText size={16} className="text-zinc-500 flex-shrink-0" />
                        <span className="text-sm text-zinc-400 truncate">{doc.filename}</span>
                      </div>
                      <span className="text-xs text-zinc-500">{doc.size_mb} MB</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}

        {/* UPLOADING STATE */}
        {phase === 'uploading' && (
          <motion.div
            key="uploading"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="flex flex-col items-center justify-center py-12 space-y-6"
          >
            <div className="relative">
              <div className="w-16 h-16 rounded-full border-4 border-zinc-800 flex items-center justify-center">
                <RefreshCw size={24} className="text-blue-500 animate-spin" />
              </div>
            </div>
            <div className="text-center space-y-2 w-full">
              <h3 className="text-lg font-medium text-zinc-200">Processing Documents</h3>
              <p className="text-sm text-zinc-500">Extracting text and tables...</p>
              <div className="mt-4 w-full">
                 <ProgressBar value={uploadProgress} label={`${selectedFiles.length} file(s)`} />
              </div>
            </div>
          </motion.div>
        )}

        {/* CAPTIONING STATE */}
        {phase === 'captioning' && (
          <motion.div
            key="captioning"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex flex-col items-center justify-center py-12 space-y-6"
          >
            <div className="relative">
              <div className="w-16 h-16 rounded-full border-4 border-zinc-800 flex items-center justify-center">
                <RefreshCw size={24} className="text-emerald-500 animate-spin" />
              </div>
            </div>
            <div className="text-center space-y-2 w-full">
              <h3 className="text-lg font-medium text-zinc-200">Background Task Running</h3>
              <p className="text-sm text-zinc-500">{ingestionStatus?.detail || 'Captioning images...'}</p>
              {ingestionStatus && ingestionStatus.images_total > 0 && (
                <div className="mt-4 w-full">
                  <ProgressBar 
                    value={(ingestionStatus.images_done / ingestionStatus.images_total) * 100} 
                    label={`${ingestionStatus.images_done} / ${ingestionStatus.images_total} images`} 
                  />
                </div>
              )}
            </div>
          </motion.div>
        )}

        {/* DONE STATE */}
        {phase === 'done' && (
          <motion.div
            key="done"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex flex-col items-center justify-center py-12 space-y-6"
          >
            <div className="w-16 h-16 rounded-full bg-emerald-500/20 text-emerald-500 flex items-center justify-center ring-4 ring-emerald-500/10">
              <Check size={32} />
            </div>
            <div className="text-center space-y-1">
              <h3 className="text-lg font-medium text-zinc-200">Upload Complete</h3>
              <p className="text-sm text-zinc-400">Successfully ingested {docCount} document(s).</p>
            </div>
            <button
              onClick={handleReset}
              className="px-6 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-medium transition-colors"
            >
              Upload more files
            </button>
            
            {serverDocs.length > 0 && (
              <div className="w-full space-y-2 mt-8 pt-4 border-t border-zinc-800/60 text-left">
                <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider px-1 flex items-center gap-2">
                  <Database size={12} />
                  Database Documents
                </h3>
                <div className="max-h-48 overflow-y-auto space-y-2 pr-1 scrollbar-thin">
                  {serverDocs.map((doc, i) => (
                    <div key={`${doc.filename}-${i}`} className="flex items-center justify-between p-3 rounded-xl bg-zinc-800/20 border border-zinc-700/30">
                      <div className="flex items-center gap-3 overflow-hidden">
                        <FileText size={16} className="text-zinc-500 flex-shrink-0" />
                        <span className="text-sm text-zinc-400 truncate">{doc.filename}</span>
                      </div>
                      <span className="text-xs text-zinc-500">{doc.size_mb} MB</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}

        {/* ERROR STATE */}
        {phase === 'error' && (
          <motion.div
            key="error"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex flex-col items-center justify-center py-12 space-y-6 text-center"
          >
            <div className="w-16 h-16 rounded-full bg-red-500/20 text-red-500 flex items-center justify-center ring-4 ring-red-500/10">
              <AlertCircle size={32} />
            </div>
            <div className="space-y-1">
              <h3 className="text-lg font-medium text-zinc-200">Upload Failed</h3>
              <p className="text-sm text-red-400 max-w-xs mx-auto">{errorMessage}</p>
            </div>
            <button
              onClick={handleReset}
              className="px-6 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 font-medium transition-colors"
            >
              Try again
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
