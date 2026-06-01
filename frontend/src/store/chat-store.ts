import { create } from 'zustand';
import type { ChatMessage } from '@/types';
import { INITIAL_MESSAGE } from '@/constants';
import { streamChat } from '@/services/api';

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
    id: 'initial-message',
    role: 'assistant',
    content: INITIAL_MESSAGE.content,
    timestamp: 'Just now',
  }],
  isStreaming: false,
  error: null,

  sendMessage: async (content: string) => {
    const userMessage = createMessage('user', content);
    const assistantMessage = createMessage('assistant', '');

    set((state) => ({
      messages: [...state.messages, userMessage, assistantMessage],
      isStreaming: true,
      error: null,
    }));

    const history = get().messages
      .filter((m) => m.id !== assistantMessage.id)
      .map((m) => ({ role: m.role, content: m.content }));

    try {
      for await (const token of streamChat(content, history)) {
        set((state) => ({
          messages: state.messages.map((m) =>
            m.id === assistantMessage.id
              ? { ...m, content: m.content + token }
              : m
          ),
        }));
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Connection failed';
      set((state) => ({
        messages: state.messages.map((m) =>
          m.id === assistantMessage.id
            ? { ...m, content: 'Sorry, there was an error connecting to the agent. Please check that the backend is running.' }
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
        id: 'initial-message',
        role: 'assistant',
        content: INITIAL_MESSAGE.content,
        timestamp: 'Just now',
      }],
      error: null,
    });
  },

  clearError: () => set({ error: null }),
}));
