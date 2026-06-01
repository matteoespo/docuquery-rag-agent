'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { PanelRightClose, PanelRightOpen } from 'lucide-react';
import { ChatWindow } from '@/components/features/chat-window';
import { FileUpload } from '@/components/features/file-upload';

export default function ChatPage() {
  const [showUpload, setShowUpload] = useState(false);

  useEffect(() => {
    const handler = () => setShowUpload((prev) => !prev);
    window.addEventListener('toggle-upload', handler);
    return () => window.removeEventListener('toggle-upload', handler);
  }, []);

  return (
    <div className="flex-1 flex overflow-hidden relative">
      {/* Chat Area */}
      <div className="flex-1 flex flex-col min-w-0 relative">
        {/* Subtle grid background */}
        <div className="absolute inset-0 bg-grid opacity-50 pointer-events-none" />
        <div className="absolute inset-0 bg-gradient-to-b from-zinc-950/0 via-zinc-950/50 to-zinc-950 pointer-events-none" />

        {/* Toggle upload panel button */}
        <div className="absolute top-3 right-3 z-20">
          <button
            onClick={() => setShowUpload(!showUpload)}
            className="p-2 rounded-lg bg-zinc-900/80 border border-zinc-800/60 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-all backdrop-blur-sm"
            title={showUpload ? 'Hide upload panel' : 'Show upload panel'}
          >
            {showUpload ? <PanelRightClose size={18} /> : <PanelRightOpen size={18} />}
          </button>
        </div>

        <ChatWindow />
      </div>

      {/* Upload Side Panel */}
      <AnimatePresence>
        {showUpload && (
          <motion.div
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 380, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: 'easeInOut' }}
            className="border-l border-zinc-800/60 bg-zinc-900/30 backdrop-blur-xl overflow-hidden flex-shrink-0 hidden lg:block"
          >
            <div className="w-[380px] h-full overflow-y-auto p-5">
              <FileUpload />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Mobile Upload Modal */}
      <AnimatePresence>
        {showUpload && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="lg:hidden fixed inset-0 z-50 flex items-end justify-center"
          >
            <div
              className="absolute inset-0 bg-black/60 backdrop-blur-sm"
              onClick={() => setShowUpload(false)}
            />
            <motion.div
              initial={{ y: '100%' }}
              animate={{ y: 0 }}
              exit={{ y: '100%' }}
              transition={{ type: 'spring', damping: 25, stiffness: 300 }}
              className="relative w-full max-h-[80vh] bg-zinc-900/95 backdrop-blur-xl border-t border-zinc-800/60 rounded-t-3xl p-6 overflow-y-auto"
            >
              <div className="w-12 h-1 bg-zinc-700 rounded-full mx-auto mb-4" />
              <FileUpload />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
