export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
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
  chunks: number;
  pages: number;
  processing_time: number;
}

export interface AnalyticsData {
  total_documents: number;
  total_chunks: number;
  total_queries: number;
  query_response_times: number[];
  document_stats: DocumentStat[];
}
