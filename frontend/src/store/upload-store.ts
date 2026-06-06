import { create } from 'zustand';
import type { IngestionStatus } from '@/types';
import { uploadFiles, fetchIngestionStatus, fetchDocuments, deleteDocument } from '@/services/api';

type UploadPhase = 'idle' | 'uploading' | 'processing' | 'captioning' | 'done' | 'error';

interface UploadStore {
  phase: UploadPhase;
  docCount: number;
  errorMessage: string | null;
  ingestionStatus: IngestionStatus | null;
  uploadProgress: number;
  serverDocs: { filename: string; size_mb: number }[];
  isDeleting: string | null;
  upload: (files: File[]) => Promise<void>;
  pollIngestionStatus: () => Promise<void>;
  fetchServerDocs: () => Promise<void>;
  deleteDoc: (filename: string) => Promise<void>;
  reset: () => void;
}

export const useUploadStore = create<UploadStore>((set, get) => ({
  phase: 'idle',
  docCount: 0,
  errorMessage: null,
  ingestionStatus: null,
  uploadProgress: 0,
  serverDocs: [],
  isDeleting: null,

  fetchServerDocs: async () => {
    try {
      const data = await fetchDocuments();
      const docs = data.documents;
      set({ serverDocs: docs });

      // Auto-transition: if docs exist and we're idle, show as ready
      const { phase } = get();
      if (docs.length > 0 && phase === 'idle') {
        set({ phase: 'done', docCount: docs.length });
      }
    } catch {
      // Silently fail — server may not be running yet
    }
  },

  deleteDoc: async (filename: string) => {
    set({ isDeleting: filename });
    try {
      await deleteDocument(filename);
      await get().fetchServerDocs();
      // If no docs remain, go back to idle
      if (get().serverDocs.length === 0) {
        set({ phase: 'idle', docCount: 0 });
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Delete failed';
      set({ errorMessage: msg });
    } finally {
      set({ isDeleting: null });
    }
  },

  upload: async (files: File[]) => {
    set({ phase: 'uploading', errorMessage: null, uploadProgress: 0 });

    try {
      const progressInterval = setInterval(() => {
        set((state) => ({
          uploadProgress: Math.min(state.uploadProgress + 10, 90),
        }));
      }, 200);

      const result = await uploadFiles(files);

      clearInterval(progressInterval);
      set({
        phase: 'done',
        docCount: result.doc_count,
        uploadProgress: 100,
      });

      // Refresh doc list and start polling
      get().fetchServerDocs();
      get().pollIngestionStatus();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Upload failed';
      set({ phase: 'error', errorMessage: msg, uploadProgress: 0 });
    }
  },

  pollIngestionStatus: async () => {
    try {
      const status = await fetchIngestionStatus();
      set({ ingestionStatus: status });

      if (status.phase !== 'idle' && status.phase !== 'complete') {
        set({ phase: 'captioning' });
        setTimeout(() => get().pollIngestionStatus(), 3000);
      } else {
        set({ phase: 'done' });
      }
    } catch {
      // Silently fail polling
    }
  },

  reset: () => {
    set({
      phase: 'idle',
      errorMessage: null,
      ingestionStatus: null,
      uploadProgress: 0,
    });
    // Re-check for existing docs to potentially auto-transition back to 'done'
    get().fetchServerDocs();
  },
}));
