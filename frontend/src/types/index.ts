export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  /** Set on both messages of a failed turn; excluded from history sent to the backend. */
  isError?: boolean;
  /** Agent progress shown while the message has no content yet. */
  status?: string;
}

export interface UploadResponse {
  message: string;
  doc_count: number;
}

export interface IngestionStatus {
  phase: string;
  detail: string;
  images_done: number;
  images_total: number;
}

export interface DocumentStat {
  filename: string;
  size_mb: number;
}

export interface AnalyticsData {
  total_requests: number;
  success_rate: number;
  avg_latency: number;
  total_tokens: number;
  latencies: number[];
}
