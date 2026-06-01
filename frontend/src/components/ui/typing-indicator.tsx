'use client';

import { motion, Variants } from 'framer-motion';

const DOT_COUNT = 3;

const containerVariants: Variants = {
  animate: {
    transition: { staggerChildren: 0.15 },
  },
};

const dotVariants: Variants = {
  initial: { y: 0, opacity: 0.4 },
  animate: {
    y: [0, -5, 0],
    opacity: [0.4, 1, 0.4],
    transition: {
      duration: 0.6,
      repeat: Infinity,
      repeatDelay: 0.3,
      ease: 'easeInOut',
    },
  },
};

export function TypingIndicator() {
  return (
    <div className="flex items-start gap-3">
      {/* Bubble */}
      <div className="rounded-2xl rounded-tl-sm border border-zinc-800/60 bg-zinc-900/70 px-4 py-3 backdrop-blur-sm">
        <motion.div
          className="flex items-center gap-1"
          variants={containerVariants}
          initial="initial"
          animate="animate"
        >
          {Array.from({ length: DOT_COUNT }).map((_, i) => (
            <motion.span
              key={i}
              className="block h-2 w-2 rounded-full bg-zinc-400"
              variants={dotVariants}
            />
          ))}
        </motion.div>
      </div>
    </div>
  );
}
