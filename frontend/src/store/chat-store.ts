import { create } from 'zustand';
import type { ChatMessage } from '@/types';
import { INITIAL_MESSAGE } from '@/constants';
import { streamChat } from '@/services/api';

const INITIAL_MESSAGE_ID = 'initial-message';

interface ChatStore {
  messages: ChatMessage[];
  isStreaming: boolean;
  error: string | null;
  sendMessage: (content: string) => Promise<void>;
  clearChat: () => void;
  clearError: () => void;
}

const createMessage = (role: 'user' | 'assistant', content: string): ChatMessage => ({
  id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
  role,
  content,
  timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
});

export const useChatStore = create<ChatStore>((set, get) => ({
  messages: [{
    id: INITIAL_MESSAGE_ID,
    role: 'assistant',
    content: INITIAL_MESSAGE.content,
    timestamp: '',
  }],
  isStreaming: false,
  error: null,

  sendMessage: async (content: string) => {
    const userMessage = createMessage('user', content);
    const assistantMessage = createMessage('assistant', '');

    // Prior turns only: the current query is sent separately as `query`, and the
    // UI greeting / failed replies are not part of the conversation.
    const history = get().messages
      .filter((m) => m.id !== INITIAL_MESSAGE_ID && !m.isError && m.content.trim())
      .map((m) => ({ role: m.role, content: m.content }));

    set((state) => ({
      messages: [...state.messages, userMessage, assistantMessage],
      isStreaming: true,
      error: null,
    }));

    try {
      for await (const event of streamChat(content, history)) {
        set((state) => ({
          messages: state.messages.map((m) => {
            if (m.id !== assistantMessage.id) return m;
            // Discard the rejected answer; show the status until new tokens arrive.
            if (event.type === 'reset') return { ...m, content: '', status: event.status };
            return { ...m, content: m.content + event.text, status: undefined };
          }),
        }));
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Connection failed';
      set((state) => ({
        // Flag the whole failed turn so neither message is sent as history.
        messages: state.messages.map((m) =>
          m.id === assistantMessage.id
            ? { ...m, isError: true, content: 'Sorry, there was an error connecting to the agent. Please check that the backend is running.' }
            : m.id === userMessage.id
              ? { ...m, isError: true }
              : m
        ),
        error: errorMsg,
      }));
    } finally {
      set({ isStreaming: false });
    }
  },

  clearChat: () => {
    set({
      messages: [{
        id: INITIAL_MESSAGE_ID,
        role: 'assistant',
        content: INITIAL_MESSAGE.content,
        timestamp: '',
      }],
      error: null,
    });
  },

  clearError: () => set({ error: null }),
}));
