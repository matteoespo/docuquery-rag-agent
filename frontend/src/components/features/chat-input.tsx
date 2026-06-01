'use client';

import { useState, useRef, useEffect } from 'react';
import { Send, Paperclip } from 'lucide-react';
import { useChatStore } from '@/store/chat-store';

export function ChatInput() {
  const [inputValue, setInputValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { sendMessage, isStreaming } = useChatStore();

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'inherit';
      const computed = window.getComputedStyle(textareaRef.current);
      const height = textareaRef.current.scrollHeight + parseInt(computed.borderTopWidth) + parseInt(computed.borderBottomWidth);
      textareaRef.current.style.height = `${Math.min(height, 128)}px`; // Max height roughly 8rem/128px
    }
  }, [inputValue]);

  const handleSend = async () => {
    if (!inputValue.trim() || isStreaming) return;

    const content = inputValue.trim();
    setInputValue('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'inherit';
    }
    
    await sendMessage(content);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="w-full relative">
      <div className="relative flex items-end gap-2 bg-zinc-900/50 backdrop-blur-xl border border-zinc-800 rounded-3xl p-2 shadow-2xl transition-all focus-within:ring-1 focus-within:ring-blue-500/50 focus-within:border-blue-500/50 hover:border-zinc-700">
        <button
          type="button"
          onClick={() => window.dispatchEvent(new CustomEvent('toggle-upload'))}
          className="p-3 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 rounded-full transition-colors flex-shrink-0"
          title="Upload document"
        >
          <Paperclip size={20} />
        </button>

        <textarea
          ref={textareaRef}
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about your documentation..."
          className="flex-1 max-h-32 min-h-[44px] bg-transparent border-none focus:ring-0 resize-none py-3 px-2 text-[15px] placeholder:text-zinc-500 text-zinc-100 scrollbar-thin overflow-y-auto outline-none"
          rows={1}
        />

        <button
          type="button"
          onClick={handleSend}
          disabled={!inputValue.trim() || isStreaming}
          className="p-3 bg-blue-600 text-white rounded-full hover:bg-blue-500 transition-colors disabled:opacity-50 disabled:hover:bg-blue-600 flex-shrink-0 shadow-lg shadow-blue-600/20"
        >
          <Send size={18} className="ml-0.5" />
        </button>
      </div>
      <div className="text-center mt-3 text-xs text-zinc-500">
        DocuQuery can make mistakes. Consider verifying important information.
      </div>
    </div>
  );
}
