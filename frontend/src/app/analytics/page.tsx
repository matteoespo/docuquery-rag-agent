import { AnalyticsDashboard } from '@/components/features/analytics-dashboard';

export const metadata = {
  title: 'Analytics — DocuQuery',
  description: 'System analytics and performance metrics for the DocuQuery system.',
};

export default function AnalyticsPage() {
  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-8 scroll-smooth scrollbar-thin relative">
      <div className="absolute inset-0 bg-grid opacity-50 pointer-events-none z-0" />
      <div className="absolute inset-0 bg-gradient-to-b from-zinc-950/0 via-zinc-950/50 to-zinc-950 pointer-events-none z-0" />
      
      <div className="relative z-10 py-8 h-full">
        <AnalyticsDashboard />
      </div>
    </div>
  );
}
