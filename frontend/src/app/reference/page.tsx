import { QuickReference } from '@/components/features/quick-reference';

export const metadata = {
  title: 'Quick Reference — DocuQuery',
  description: 'Documentation and guides for the DocuQuery system.',
};

export default function ReferencePage() {
  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-8 scroll-smooth scrollbar-thin">
      <div className="absolute inset-0 bg-grid opacity-50 pointer-events-none z-0" />
      <div className="absolute inset-0 bg-gradient-to-b from-zinc-950/0 via-zinc-950/50 to-zinc-950 pointer-events-none z-0" />
      
      <div className="relative z-10 max-w-4xl mx-auto py-8">
        <QuickReference />
      </div>
    </div>
  );
}
