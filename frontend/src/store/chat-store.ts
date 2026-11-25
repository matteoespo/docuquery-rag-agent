import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import type { ChatMessage } from '@/types';
import { INITIAL_MESSAGE } from '@/constants';
import { AgentError, streamChat } from '@/services/api';

const INITIAL_MESSAGE_ID = 'initial-message';
const STORAGE_KEY = 'docuquery-chat';

interface ChatStore {
  messages: ChatMessage[];
  isStreaming: boolean;
  error: string | null;
  sendMessage: (content: string) => Promise<void>;
  stopGeneration: () => void;
  clearChat: () => void;
  clearError: () => void;
}

const initialMessages = (): ChatMessage[] => [{
  id: INITIAL_MESSAGE_ID,
  role: 'assistant',
  content: INITIAL_MESSAGE.content,
  timestamp: '',
}];

const createMessage = (role: 'user' | 'assistant', content: string): ChatMessage => ({
  id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
  role,
  content,
  timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
});

// The in-flight request; not part of the (persisted) state.
let controller: AbortController | null = null;

/** Messages restored from storage: drop answers a page reload cut off mid-stream. */
function restoreMessages(messages: ChatMessage[]): ChatMessage[] {
  const restored = messages
    .filter((m) => m.role === 'user' || m.content.trim())
    .map((m) => ({ ...m, status: undefined }));
  return restored.length ? restored : initialMessages();
}

export const useChatStore = create<ChatStore>()(
  persist(
    (set, get) => ({
      messages: initialMessages(),
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

        const update = (fn: (m: ChatMessage) => ChatMessage) =>
          set((state) => ({
            messages: state.messages.map((m) => (m.id === assistantMessage.id ? fn(m) : m)),
          }));

        controller = new AbortController();
        try {
          for await (const event of streamChat(content, history, controller.signal)) {
            switch (event.type) {
              case 'status':
                update((m) => (m.content ? m : { ...m, status: event.text }));
                break;
              case 'sources':
                update((m) => ({ ...m, sources: event.sources }));
                break;
              case 'reset':
                // Discard the rejected answer; show the status until new tokens arrive.
                update((m) => ({ ...m, content: '', status: event.status }));
                break;
              case 'token':
                update((m) => ({ ...m, content: m.content + event.text, status: undefined }));
                break;
            }
          }
        } catch (err) {
          if (err instanceof DOMException && err.name === 'AbortError') {
            const answered = Boolean(get().messages.find((m) => m.id === assistantMessage.id)?.content.trim());
            set((state) => ({
              messages: state.messages.map((m) => {
                if (m.id === assistantMessage.id) {
                  return answered
                    ? { ...m, stopped: true, status: undefined }
                    // Nothing was answered: leave the turn out of the history like a failed one.
                    : { ...m, stopped: true, isError: true, status: undefined, content: 'Stopped before an answer was generated.' };
                }
                return m.id === userMessage.id && !answered ? { ...m, isError: true } : m;
              }),
            }));
            return;
          }
          const errorMsg = err instanceof Error ? err.message : 'Connection failed';
          const shown = err instanceof AgentError
            ? err.message
            : 'Sorry, there was an error connecting to the agent. Please check that the backend is running.';
          set((state) => ({
            // Flag the whole failed turn so neither message is sent as history.
            messages: state.messages.map((m) =>
              m.id === assistantMessage.id
                ? { ...m, isError: true, status: undefined, content: shown }
                : m.id === userMessage.id
                  ? { ...m, isError: true }
                  : m
            ),
            error: errorMsg,
          }));
        } finally {
          controller = null;
          set({ isStreaming: false });
        }
      },

      stopGeneration: () => controller?.abort(),

      clearChat: () => {
        controller?.abort();
        set({ messages: initialMessages(), error: null });
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ messages: state.messages }),
      merge: (persisted, current) => ({
        ...current,
        messages: restoreMessages((persisted as Partial<ChatStore> | undefined)?.messages ?? current.messages),
      }),
      // Rehydrated from ChatWindow after mount: the server render has no localStorage,
      // so hydrating during the first render would mismatch.
      skipHydration: true,
    }
  )
);
