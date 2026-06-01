'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { BookOpen, HelpCircle, AlertTriangle, Info, CheckCircle2, ChevronRight, Server, Database, BrainCircuit, MessageSquare } from 'lucide-react';

type Tab = 'getting-started' | 'architecture' | 'troubleshooting';

export function QuickReference() {
  const [activeTab, setActiveTab] = useState<Tab>('getting-started');

  return (
    <div className="w-full max-w-4xl mx-auto flex flex-col h-full overflow-hidden bg-zinc-950/50 rounded-2xl border border-zinc-800/60 shadow-xl backdrop-blur-sm">
      {/* Header */}
      <div className="p-6 border-b border-zinc-800/60 flex items-center gap-3">
        <div className="p-2.5 rounded-xl bg-blue-600/20 text-blue-500 ring-1 ring-blue-500/30">
          <BookOpen size={24} />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-zinc-100">Quick Reference</h1>
          <p className="text-sm text-zinc-400">Documentation & guides for the DocuQuery system</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex px-6 pt-4 border-b border-zinc-800/60 gap-6">
        <TabButton active={activeTab === 'getting-started'} onClick={() => setActiveTab('getting-started')} icon={<CheckCircle2 size={16} />}>Getting Started</TabButton>
        <TabButton active={activeTab === 'architecture'} onClick={() => setActiveTab('architecture')} icon={<Server size={16} />}>Architecture</TabButton>
        <TabButton active={activeTab === 'troubleshooting'} onClick={() => setActiveTab('troubleshooting')} icon={<HelpCircle size={16} />}>Troubleshooting</TabButton>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6 scrollbar-thin">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
            className="space-y-8 pb-8"
          >
            {activeTab === 'getting-started' && <GettingStartedContent />}
            {activeTab === 'architecture' && <ArchitectureContent />}
            {activeTab === 'troubleshooting' && <TroubleshootingContent />}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}

function TabButton({ active, onClick, children, icon }: { active: boolean; onClick: () => void; children: React.ReactNode; icon: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`pb-4 px-1 flex items-center gap-2 text-sm font-medium transition-colors relative ${
        active ? 'text-blue-400' : 'text-zinc-400 hover:text-zinc-200'
      }`}
    >
      {icon}
      {children}
      {active && (
        <motion.div
          layoutId="activeTab"
          className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-500"
        />
      )}
    </button>
  );
}

function GettingStartedContent() {
  return (
    <div className="space-y-6">
      <div className="prose prose-invert max-w-none">
        <h2 className="text-xl font-medium flex items-center gap-2 text-zinc-100">
          <Info size={20} className="text-blue-500" /> System Overview
        </h2>
        <p className="text-zinc-400 leading-relaxed mt-2">
          DocuQuery is an advanced on-premise RAG (Retrieval-Augmented Generation) system. It allows you to upload technical PDFs and converse with them using local LLMs.
        </p>
      </div>

      <div className="space-y-4 mt-8">
        <h3 className="text-lg font-medium text-zinc-200">How to use the system:</h3>
        
        <Step number={1} title="Upload your PDFs">
          Click the "Upload PDF" button in the sidebar or toggle the right panel. Drag and drop your technical documents. The system will extract text and tables immediately.
        </Step>
        
        <Step number={2} title="Wait for Background Processing">
          Large documents or documents with many images will process in the background. You can start querying immediately for text, but image captions will become available as they finish processing.
        </Step>
        
        <Step number={3} title="Start Querying">
          Type your question in the chat bar. The system will:
          <ul className="list-disc pl-5 mt-2 space-y-1 text-zinc-400">
            <li>Analyze your intent</li>
            <li>Search the vector database for relevant chunks</li>
            <li>Evaluate if the retrieved information is sufficient</li>
            <li>Generate a response (or fallback to web search if needed)</li>
          </ul>
        </Step>
      </div>
    </div>
  );
}

function ArchitectureContent() {
  return (
    <div className="space-y-8">
      <div className="grid md:grid-cols-2 gap-4">
        <ArchitectureCard 
          icon={<Database className="text-emerald-500" />}
          title="Data Ingestion"
          description="PDFs are processed using pdfplumber (text/tables) and PyMuPDF (images). Text is chunked, and images are passed to a vision model (Moondream) for captioning. All data is embedded and stored in ChromaDB."
        />
        <ArchitectureCard 
          icon={<BrainCircuit className="text-purple-500" />}
          title="Agentic Routing (LangGraph)"
          description="A cyclical graph structure routes queries. A grader evaluates retrieved docs. If context is poor, it falls back to a web search to augment the response before generating."
        />
        <ArchitectureCard 
          icon={<Server className="text-blue-500" />}
          title="Local Models (Ollama)"
          description="Llama 3.2 (3B) handles reasoning and generation. Nomic-embed-text generates semantic embeddings. Everything runs locally on-premise for full privacy."
        />
        <ArchitectureCard 
          icon={<MessageSquare className="text-amber-500" />}
          title="Sliding Memory"
          description="Maintains the last 3 messages verbatim. Older context is recursively summarized by the LLM into concise bullet points to preserve continuity without blowing up token limits."
        />
      </div>
    </div>
  );
}

function TroubleshootingContent() {
  return (
    <div className="space-y-4">
      <TroubleshootingItem 
        type="error"
        title="Agent not initialized. Try again later."
        description="The backend FastAPI server is running, but the LangGraph agent failed to initialize. Check if the Ollama container is running and the required models are pulled."
      />
      <TroubleshootingItem 
        type="warning"
        title="Web search fallback occurring too often"
        description="If the agent frequently searches the web, your documents might not contain the answers, or the ChromaDB index might be corrupted. Try re-uploading the documents."
      />
      <TroubleshootingItem 
        type="info"
        title="Images not being recognized"
        description="Image captioning runs asynchronously in the background. It may take a few minutes for diagrams to become searchable after uploading a large PDF."
      />
      <TroubleshootingItem 
        type="info"
        title="Answers seem truncated or cut off"
        description="The streaming response might have timed out. The system has a 300s timeout for stream generation. Try asking a more specific question."
      />
    </div>
  );
}

function Step({ number, title, children }: { number: number; title: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-4 p-4 rounded-xl bg-zinc-900/50 border border-zinc-800/50">
      <div className="w-8 h-8 rounded-full bg-zinc-800 text-zinc-300 flex items-center justify-center font-bold flex-shrink-0 border border-zinc-700">
        {number}
      </div>
      <div>
        <h4 className="text-zinc-100 font-medium mb-1">{title}</h4>
        <div className="text-sm text-zinc-400">{children}</div>
      </div>
    </div>
  );
}

function ArchitectureCard({ title, description, icon }: { title: string; description: string; icon: React.ReactNode }) {
  return (
    <div className="p-5 rounded-xl bg-zinc-900/40 border border-zinc-800/60 hover:bg-zinc-800/40 transition-colors">
      <div className="flex items-center gap-3 mb-3">
        <div className="p-2 rounded-lg bg-zinc-950 border border-zinc-800">
          {icon}
        </div>
        <h4 className="font-medium text-zinc-200">{title}</h4>
      </div>
      <p className="text-sm text-zinc-400 leading-relaxed">{description}</p>
    </div>
  );
}

function TroubleshootingItem({ type, title, description }: { type: 'error' | 'warning' | 'info'; title: string; description: string }) {
  const styles = {
    error: 'border-red-500/20 bg-red-500/5 text-red-400',
    warning: 'border-amber-500/20 bg-amber-500/5 text-amber-400',
    info: 'border-blue-500/20 bg-blue-500/5 text-blue-400',
  };
  
  const icons = {
    error: <AlertTriangle size={18} />,
    warning: <AlertTriangle size={18} />,
    info: <Info size={18} />,
  };

  return (
    <div className={`p-4 rounded-xl border flex gap-3 ${styles[type]}`}>
      <div className="mt-0.5">{icons[type]}</div>
      <div>
        <h4 className="font-medium mb-1">{title}</h4>
        <p className="text-sm opacity-80">{description}</p>
      </div>
    </div>
  );
}
