import { ENDPOINTS } from '@/constants';
import type { ChatMessage, UploadResponse, IngestionStatus, AnalyticsData } from '@/types';

export async function* streamChat(
  query: string,
  chatHistory: { role: string; content: string }[]
): AsyncGenerator<string, void, unknown> {
  const response = await fetch(ENDPOINTS.CHAT_STREAM, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, chat_history: chatHistory }),
  });

  if (!response.ok) {
    throw new Error(`Chat request failed: ${response.status}`);
  }

  if (!response.body) {
    throw new Error('No response body');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const dataStr = line.slice(6).trim();
      if (!dataStr) continue;

      try {
        const data = JSON.parse(dataStr);
        if (data.token === '[stream completed]') return;
        if (data.token) yield data.token;
      } catch {
        // skip malformed JSON
      }
    }
  }
}

export async function uploadFiles(files: File[]): Promise<UploadResponse> {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));

  const response = await fetch(ENDPOINTS.UPLOAD, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `Upload failed: ${response.status}`);
  }

  return response.json();
}

export async function fetchIngestionStatus(): Promise<IngestionStatus> {
  const response = await fetch(ENDPOINTS.INGESTION_STATUS);
  if (!response.ok) throw new Error(`Failed to fetch ingestion status: ${response.status}`);
  return response.json();
}

export async function checkHealth(): Promise<{ status: string; model: string; db: string; agent_loaded: boolean }> {
  const response = await fetch(ENDPOINTS.HEALTH);
  if (!response.ok) throw new Error(`Health check failed: ${response.status}`);
  return response.json();
}

export async function fetchAnalytics(): Promise<AnalyticsData> {
  const response = await fetch(ENDPOINTS.ANALYTICS);
  if (!response.ok) throw new Error(`Failed to fetch analytics: ${response.status}`);
  return response.json();
}

export async function fetchDocuments(): Promise<{ documents: { filename: string; size_mb: number }[] }> {
  const response = await fetch(ENDPOINTS.DOCUMENTS);
  if (!response.ok) throw new Error(`Failed to fetch documents: ${response.status}`);
  return response.json();
}
