'use client';

import {
  Bot,
  Menu,
  X,
  MessageSquare,
  BarChart3,
  BookOpen,
  Upload,
} from 'lucide-react';
import { useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';

const navItems = [
  { href: '/', label: 'Chat', icon: MessageSquare },
  { href: '/analytics', label: 'Analytics', icon: BarChart3 },
  { href: '/reference', label: 'Quick Reference', icon: BookOpen },
] as const;

export function MobileHeader() {
  const [menuOpen, setMenuOpen] = useState(false);
  const pathname = usePathname();
  const router = useRouter();

  return (
    <>
      <header className="md:hidden h-14 border-b border-zinc-800/60 bg-zinc-900/60 backdrop-blur-xl flex items-center justify-between px-4 relative z-30">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-blue-600/20 text-blue-500 flex items-center justify-center ring-1 ring-blue-500/30">
            <Bot size={16} />
          </div>
          <span className="font-semibold text-base tracking-tight bg-gradient-to-r from-zinc-100 to-zinc-400 bg-clip-text text-transparent">
            DocuQuery
          </span>
        </div>
        <button
          onClick={() => setMenuOpen(!menuOpen)}
          className="p-2 rounded-lg hover:bg-zinc-800 text-zinc-400 transition-colors"
        >
          {menuOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </header>

      {/* Mobile Navigation Menu */}
      <AnimatePresence>
        {menuOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="md:hidden fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
              onClick={() => setMenuOpen(false)}
            />

            {/* Menu Panel */}
            <motion.div
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: 'spring', damping: 25, stiffness: 300 }}
              className="md:hidden fixed top-0 right-0 bottom-0 w-72 bg-zinc-900/95 backdrop-blur-xl border-l border-zinc-800/60 z-50 p-4 flex flex-col"
            >
              <div className="flex items-center justify-between mb-6">
                <span className="text-lg font-semibold text-zinc-100">Menu</span>
                <button
                  onClick={() => setMenuOpen(false)}
                  className="p-2 rounded-lg hover:bg-zinc-800 text-zinc-400"
                >
                  <X size={20} />
                </button>
              </div>

              <nav className="space-y-1 flex-1">
                {navItems.map((item) => {
                  const isActive = pathname === item.href;
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.href}
                      onClick={() => {
                        router.push(item.href);
                        setMenuOpen(false);
                      }}
                      className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
                        isActive
                          ? 'bg-blue-600/15 text-blue-400 ring-1 ring-blue-500/20'
                          : 'text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200'
                      }`}
                    >
                      <Icon size={20} />
                      <span className="text-sm font-medium">{item.label}</span>
                    </button>
                  );
                })}
              </nav>

              <button
                onClick={() => {
                  router.push('/');
                  window.dispatchEvent(new CustomEvent('toggle-upload'));
                  setMenuOpen(false);
                }}
                className="flex items-center gap-3 px-4 py-3 rounded-xl border border-dashed border-zinc-700/60 hover:border-blue-500/40 hover:bg-blue-500/5 text-zinc-400 hover:text-blue-400 transition-all"
              >
                <Upload size={18} />
                <span className="text-sm font-medium">Upload PDF</span>
              </button>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
