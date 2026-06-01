import { create } from 'zustand';
import type { IngestionStatus } from '@/types';
import { uploadFiles, fetchIngestionStatus } from '@/services/api';

type UploadPhase = 'idle' | 'uploading' | 'processing' | 'captioning' | 'done' | 'error';

interface UploadStore {
  phase: UploadPhase;
  docCount: number;
  errorMessage: string | null;
  ingestionStatus: IngestionStatus | null;
  uploadProgress: number;
  upload: (files: File[]) => Promise<void>;
  pollIngestionStatus: () => Promise<void>;
  reset: () => void;
}

export const useUploadStore = create<UploadStore>((set, get) => ({
  phase: 'idle',
  docCount: 0,
  errorMessage: null,
  ingestionStatus: null,
  uploadProgress: 0,

  upload: async (files: File[]) => {
    set({ phase: 'uploading', errorMessage: null, uploadProgress: 0 });

    try {
      // Simulate progress during upload
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

      // Start polling for ingestion status
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
        // Poll again after 3 seconds
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
  },
}));
