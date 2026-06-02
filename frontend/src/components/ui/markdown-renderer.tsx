'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';

interface MarkdownRendererProps {
  content: string;
}

const components: Components = {
  // ── Code ──────────────────────────────────────────────────────────
  code({ className, children, ...rest }) {
    const match = /language-(\w+)/.exec(className || '');
    const isBlock = Boolean(match);

    if (isBlock) {
      return (
        <div className="my-3 overflow-hidden rounded-xl border border-zinc-800/60">
          {match && (
            <div className="flex items-center border-b border-zinc-800/60 bg-zinc-900/80 px-4 py-1.5">
              <span className="text-[11px] font-medium tracking-wide text-zinc-500 uppercase">
                {match[1]}
              </span>
            </div>
          )}
          <pre className="overflow-x-auto bg-zinc-900 p-4">
            <code
              className={`font-mono text-sm leading-relaxed text-zinc-300 ${className ?? ''}`}
              style={{ fontFamily: 'var(--font-geist-mono), ui-monospace, monospace' }}
              {...rest}
            >
              {children}
            </code>
          </pre>
        </div>
      );
    }

    return (
      <code
        className="rounded-md bg-zinc-800 px-1.5 py-0.5 font-mono text-[13px] text-zinc-300"
        style={{ fontFamily: 'var(--font-geist-mono), ui-monospace, monospace' }}
        {...rest}
      >
        {children}
      </code>
    );
  },

  // ── Pre (passthrough – actual styling lives in `code`) ────────────
  pre({ children }) {
    return <>{children}</>;
  },

  // ── Headings ──────────────────────────────────────────────────────
  h1({ children }) {
    return (
      <h1 className="mb-4 mt-6 text-2xl font-bold tracking-tight text-zinc-100 first:mt-0">
        {children}
      </h1>
    );
  },
  h2({ children }) {
    return (
      <h2 className="mb-3 mt-5 text-xl font-semibold tracking-tight text-zinc-100 first:mt-0">
        {children}
      </h2>
    );
  },
  h3({ children }) {
    return (
      <h3 className="mb-2 mt-4 text-lg font-semibold text-zinc-200 first:mt-0">
        {children}
      </h3>
    );
  },
  h4({ children }) {
    return (
      <h4 className="mb-2 mt-3 text-base font-semibold text-zinc-200 first:mt-0">
        {children}
      </h4>
    );
  },
  h5({ children }) {
    return (
      <h5 className="mb-1 mt-3 text-sm font-semibold text-zinc-300 first:mt-0">
        {children}
      </h5>
    );
  },
  h6({ children }) {
    return (
      <h6 className="mb-1 mt-2 text-sm font-medium text-zinc-400 first:mt-0">
        {children}
      </h6>
    );
  },

  // ── Paragraph ─────────────────────────────────────────────────────
  p({ children }) {
    return <p className="mb-3 leading-relaxed text-zinc-300 last:mb-0">{children}</p>;
  },

  // ── Links ─────────────────────────────────────────────────────────
  a({ href, children }) {
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-blue-400 underline decoration-blue-400/30 underline-offset-2 transition-colors hover:text-blue-300 hover:decoration-blue-300/50"
      >
        {children}
      </a>
    );
  },

  // ── Lists ─────────────────────────────────────────────────────────
  ul({ children }) {
    return <ul className="mb-3 ml-6 list-disc space-y-1 text-zinc-300 last:mb-0">{children}</ul>;
  },
  ol({ children }) {
    return (
      <ol className="mb-3 ml-6 list-decimal space-y-1 text-zinc-300 last:mb-0">{children}</ol>
    );
  },
  li({ children }) {
    return <li className="leading-relaxed text-zinc-300">{children}</li>;
  },

  // ── Blockquote ────────────────────────────────────────────────────
  blockquote({ children }) {
    return (
      <blockquote className="my-3 border-l-2 border-blue-500/50 bg-zinc-900/40 py-1 pl-4 italic text-zinc-400">
        {children}
      </blockquote>
    );
  },

  // ── Tables ────────────────────────────────────────────────────────
  table({ children }) {
    return (
      <div className="my-3 overflow-x-auto rounded-xl border border-zinc-800/60">
        <table className="min-w-full text-sm">{children}</table>
      </div>
    );
  },
  thead({ children }) {
    return <thead className="border-b border-zinc-800/60 bg-zinc-900/60">{children}</thead>;
  },
  tbody({ children }) {
    return <tbody className="divide-y divide-zinc-800/40">{children}</tbody>;
  },
  tr({ children }) {
    return <tr className="even:bg-zinc-900/30">{children}</tr>;
  },
  th({ children }) {
    return (
      <th className="px-4 py-2 text-left text-xs font-semibold tracking-wide text-zinc-400 uppercase">
        {children}
      </th>
    );
  },
  td({ children }) {
    return <td className="px-4 py-2 text-zinc-300">{children}</td>;
  },

  // ── Horizontal Rule ───────────────────────────────────────────────
  hr() {
    return <hr className="my-6 border-zinc-800/60" />;
  },

  // ── Images ────────────────────────────────────────────────────────
  img({ src, alt }) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={src}
        alt={alt ?? ''}
        className="my-3 max-w-full rounded-xl border border-zinc-800/60"
        loading="lazy"
      />
    );
  },

  // ── Strong & Emphasis ─────────────────────────────────────────────
  strong({ children }) {
    return <strong className="font-semibold text-zinc-100">{children}</strong>;
  },
  em({ children }) {
    return <em className="italic text-zinc-300">{children}</em>;
  },

  // ── Strikethrough ─────────────────────────────────────────────────
  del({ children }) {
    return <del className="text-zinc-500 line-through">{children}</del>;
  },

  // ── Task list checkbox (GFM) ──────────────────────────────────────
  input({ checked, ...rest }) {
    return (
      <input
        type="checkbox"
        checked={checked}
        readOnly
        className="mr-2 accent-blue-500"
        {...rest}
      />
    );
  },
};

export function MarkdownRenderer({ content }: MarkdownRendererProps) {
  return (
    <div className="max-w-none">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
