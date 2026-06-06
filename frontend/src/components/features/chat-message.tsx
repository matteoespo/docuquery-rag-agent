'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { User, Bot } from 'lucide-react';
import type { ChatMessage as ChatMessageType } from '@/types';
import { MarkdownRenderer } from '@/components/ui/markdown-renderer';
import { TypingIndicator } from '@/components/ui/typing-indicator';

interface ChatMessageProps {
  message: ChatMessageType;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const isEmpty = !message.content;

  // Compute timestamp client-side to avoid SSR timezone mismatch
  const [displayTimestamp, setDisplayTimestamp] = useState(message.timestamp);

  useEffect(() => {
    if (!message.timestamp) {
      setDisplayTimestamp(
        new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      );
    } else {
      setDisplayTimestamp(message.timestamp);
    }
  }, [message.timestamp]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`flex gap-4 ${isUser ? 'flex-row-reverse' : ''}`}
    >
      {/* Avatar */}
      <div
        className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full ${
          isUser
            ? 'border border-zinc-700 bg-zinc-800 text-zinc-300'
            : 'border border-blue-500/30 bg-blue-600/20 text-blue-400'
        }`}
      >
        {isUser ? <User size={14} /> : <Bot size={14} />}
      </div>

      {/* Content */}
      <div
        className={`flex max-w-[80%] flex-col gap-1 ${
          isUser ? 'items-end' : 'items-start'
        }`}
      >
        {/* Role label + timestamp */}
        <div className="flex items-center gap-2 px-1 text-xs text-zinc-500">
          <span>{isUser ? 'You' : 'DocuQuery'}</span>
          <span>•</span>
          <span>{displayTimestamp}</span>
        </div>

        {/* Message bubble */}
        <div
          className={`rounded-2xl p-4 text-[15px] leading-relaxed shadow-sm ${
            isUser
              ? 'rounded-tr-sm border border-zinc-700/50 bg-zinc-800 text-zinc-100'
              : 'rounded-tl-sm border border-zinc-800 bg-zinc-900/80 text-zinc-200 shadow-xl backdrop-blur-sm'
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : isEmpty ? (
            <TypingIndicator />
          ) : (
            <MarkdownRenderer content={message.content} />
          )}
        </div>
      </div>
    </motion.div>
  );
}
