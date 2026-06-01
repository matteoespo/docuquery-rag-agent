import type { Metadata } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';
import { Sidebar } from '@/components/layout/sidebar';
import { MobileHeader } from '@/components/layout/mobile-header';

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
});

export const metadata: Metadata = {
  title: 'DocuQuery — RAG Agent',
  description:
    'An on-premise RAG agentic system for processing and querying technical documentation. Powered by LangGraph and local LLMs.',
  keywords: ['RAG', 'LangGraph', 'AI', 'documentation', 'chat', 'on-premise'],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased dark`}
    >
      <body className="h-full bg-zinc-950 text-zinc-50">
        <div className="flex h-full overflow-hidden">
          <Sidebar />
          <div className="flex-1 flex flex-col min-w-0">
            <MobileHeader />
            {children}
          </div>
        </div>
      </body>
    </html>
  );
}
