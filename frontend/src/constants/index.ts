export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export const ENDPOINTS = {
  CHAT_STREAM: `${API_BASE_URL}/api/chat/stream`,
  UPLOAD: `${API_BASE_URL}/api/upload`,
  INGESTION_STATUS: `${API_BASE_URL}/api/ingestion/status`,
  HEALTH: `${API_BASE_URL}/health`,
  ANALYTICS: `${API_BASE_URL}/api/analytics`,
  DOCUMENTS: `${API_BASE_URL}/api/documents`,
} as const;

export const INITIAL_MESSAGE: { role: 'assistant'; content: string } = {
  role: 'assistant',
  content: 'Hello! I\'m DocuQuery, your technical documentation assistant. Upload a PDF or ask me a question to get started.',
};
