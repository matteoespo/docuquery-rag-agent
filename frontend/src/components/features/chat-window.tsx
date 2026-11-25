'use client';

import { useEffect, useRef } from 'react';
import { AnimatePresence } from 'framer-motion';
import { SquarePen } from 'lucide-react';
import { useChatStore } from '@/store/chat-store';
import { ChatMessage as ChatMessageComponent } from './chat-message';
import { ChatInput } from './chat-input';

export function ChatWindow() {
  const { messages, clearChat } = useChatStore();
  const bottomRef = useRef<HTMLDivElement>(null);
  const hasConversation = messages.some((m) => m.role === 'user');

  // Restore the saved conversation after mount (see skipHydration in the store).
  useEffect(() => {
    useChatStore.persist.rehydrate();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="flex flex-col h-full relative z-10 w-full max-w-4xl mx-auto">
      {hasConversation && (
        <div className="absolute right-4 top-3 z-20 md:right-8">
          <button
            type="button"
            onClick={clearChat}
            title="Start a new chat"
            className="flex items-center gap-1.5 rounded-full border border-zinc-800 bg-zinc-900/80 px-3 py-1.5 text-xs text-zinc-400 backdrop-blur-sm transition-colors hover:border-zinc-700 hover:text-zinc-200"
          >
            <SquarePen size={14} /> New chat
          </button>
        </div>
      )}
      <div className="flex-1 overflow-y-auto p-4 md:p-8 space-y-6 scroll-smooth scrollbar-thin">
        <div className="max-w-3xl mx-auto space-y-8 pb-4">
          <AnimatePresence initial={false}>
            {messages.map((msg) => (
              <ChatMessageComponent key={msg.id} message={msg} />
            ))}
          </AnimatePresence>
          <div ref={bottomRef} className="h-4" />
        </div>
      </div>

      <div className="p-4 md:p-6 bg-gradient-to-t from-zinc-950 via-zinc-950 to-transparent flex-shrink-0">
        <div className="max-w-3xl mx-auto">
          <ChatInput />
        </div>
      </div>
    </div>
  );
}
