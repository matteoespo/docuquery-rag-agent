'use client';

import { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { User, Bot, FileText, Globe, Square } from 'lucide-react';
import type { ChatMessage as ChatMessageType, Source } from '@/types';
import { MarkdownRenderer } from '@/components/ui/markdown-renderer';
import { TypingIndicator } from '@/components/ui/typing-indicator';
import { citedSourceKeys, linkifyCitations, sourceHref, sourceKey, sourceLabel } from '@/lib/citations';

interface ChatMessageProps {
  message: ChatMessageType;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const isEmpty = !message.content;

  const [mounted, setMounted] = useState(false);
  
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true);
  }, []);

  // Compute timestamp client-side to avoid SSR timezone mismatch
  const displayTimestamp = message.timestamp || (mounted ? new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '');

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
            <TypingIndicator label={message.status} />
          ) : (
            <MarkdownRenderer content={linkifyCitations(message.content, message.sources ?? [])} />
          )}
        </div>

        {!isUser && message.stopped && !isEmpty && (
          <div className="flex items-center gap-1 px-1 text-xs text-zinc-500">
            <Square size={10} /> Stopped
          </div>
        )}

        {!isUser && !isEmpty && !message.isError && message.sources && message.sources.length > 0 && (
          <SourceChips sources={message.sources} content={message.content} />
        )}
      </div>
    </motion.div>
  );
}

/** Retrieved sources under an answer; the ones the answer cites come first and are highlighted. */
function SourceChips({ sources, content }: { sources: Source[]; content: string }) {
  const cited = useMemo(() => citedSourceKeys(content, sources), [content, sources]);
  const ordered = [...sources].sort((a, b) => Number(cited.has(sourceKey(b))) - Number(cited.has(sourceKey(a))));

  return (
    <div className="flex flex-wrap items-center gap-1.5 px-1 pt-1">
      <span className="text-xs text-zinc-500">Sources:</span>
      {ordered.map((source) => {
        const isCited = cited.has(sourceKey(source));
        const Icon = source.url ? Globe : FileText;
        return (
          <a
            key={sourceKey(source)}
            href={sourceHref(source)}
            target="_blank"
            rel="noopener noreferrer"
            title={isCited ? 'Cited in the answer' : 'Retrieved, not cited'}
            className={`flex max-w-[16rem] items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors ${
              isCited
                ? 'border-blue-500/40 bg-blue-500/10 text-blue-300 hover:bg-blue-500/20'
                : 'border-zinc-800 bg-zinc-900/60 text-zinc-500 hover:text-zinc-300'
            }`}
          >
            <Icon size={12} className="flex-shrink-0" />
            <span className="truncate">{sourceLabel(source)}</span>
          </a>
        );
      })}
    </div>
  );
}
