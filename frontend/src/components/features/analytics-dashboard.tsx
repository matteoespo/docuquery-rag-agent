'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { 
  BarChart3, 
  FileText, 
  Layers, 
  MessageSquare, 
  Clock, 
  RefreshCw,
  TrendingDown
} from 'lucide-react';
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  Area,
  AreaChart
} from 'recharts';
import { fetchAnalytics } from '@/services/api';
import type { AnalyticsData } from '@/types';

export function AnalyticsDashboard() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchAnalytics();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load analytics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center h-full min-h-[400px]">
        <RefreshCw size={24} className="animate-spin text-blue-500" />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[400px] text-zinc-400">
        <p className="mb-4">{error}</p>
        <button 
          onClick={loadData}
          className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg transition-colors flex items-center gap-2"
        >
          <RefreshCw size={16} />
          Retry
        </button>
      </div>
    );
  }

  if (!data) return null;

  const avgResponseTime = data.query_response_times.length > 0 
    ? (data.query_response_times.reduce((a, b) => a + b, 0) / data.query_response_times.length).toFixed(2)
    : '0.00';

  const chartData = data.query_response_times.map((time, index) => ({
    query: index + 1,
    time: Number(time.toFixed(2))
  }));

  return (
    <div className="w-full max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-100 flex items-center gap-2">
            <BarChart3 className="text-blue-500" />
            System Analytics
          </h1>
          <p className="text-sm text-zinc-400 mt-1">Real-time metrics and performance data</p>
        </div>
        <button 
          onClick={loadData}
          disabled={loading}
          className="p-2.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors disabled:opacity-50"
          title="Refresh data"
        >
          <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard 
          title="Total Documents" 
          value={data.total_documents} 
          icon={<FileText size={20} className="text-emerald-500" />} 
        />
        <MetricCard 
          title="Total Chunks" 
          value={data.total_chunks} 
          icon={<Layers size={20} className="text-blue-500" />} 
        />
        <MetricCard 
          title="Total Queries" 
          value={data.total_queries} 
          icon={<MessageSquare size={20} className="text-purple-500" />} 
        />
        <MetricCard 
          title="Avg Response Time" 
          value={`${avgResponseTime}s`} 
          icon={<Clock size={20} className="text-amber-500" />} 
          trend={<TrendingDown size={14} className="text-emerald-500" />}
        />
      </div>

      {/* Charts Area */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-8">
        {/* Main Chart */}
        <div className="col-span-1 lg:col-span-2 p-6 rounded-2xl bg-zinc-900/50 border border-zinc-800/60 backdrop-blur-sm">
          <h3 className="text-sm font-medium text-zinc-400 mb-6">Query Response Times</h3>
          <div className="h-[300px] w-full">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 5, right: 0, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorTime" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                  <XAxis 
                    dataKey="query" 
                    stroke="#52525b" 
                    fontSize={12} 
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(val) => `Q${val}`}
                  />
                  <YAxis 
                    stroke="#52525b" 
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(val) => `${val}s`}
                  />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#18181b', borderColor: '#27272a', borderRadius: '8px' }}
                    itemStyle={{ color: '#e4e4e7' }}
                  />
                  <Area 
                    type="monotone" 
                    dataKey="time" 
                    stroke="#3b82f6" 
                    strokeWidth={2}
                    fillOpacity={1} 
                    fill="url(#colorTime)" 
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-zinc-500 text-sm">
                No query data available yet
              </div>
            )}
          </div>
        </div>

        {/* Stats Table */}
        <div className="col-span-1 p-6 rounded-2xl bg-zinc-900/50 border border-zinc-800/60 backdrop-blur-sm flex flex-col">
          <h3 className="text-sm font-medium text-zinc-400 mb-4">Document Stats</h3>
          <div className="flex-1 overflow-y-auto pr-2 scrollbar-thin">
            {data.document_stats.length > 0 ? (
              <div className="space-y-3">
                {data.document_stats.map((doc, idx) => (
                  <div key={idx} className="p-3 rounded-xl bg-zinc-800/40 border border-zinc-700/30">
                    <div className="text-sm font-medium text-zinc-200 truncate mb-2" title={doc.filename}>
                      {doc.filename}
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div>
                        <span className="text-zinc-500">Pages:</span> <span className="text-zinc-300">{doc.pages}</span>
                      </div>
                      <div>
                        <span className="text-zinc-500">Chunks:</span> <span className="text-zinc-300">{doc.chunks}</span>
                      </div>
                      <div className="col-span-2">
                        <span className="text-zinc-500">Processing Time:</span> <span className="text-zinc-300">{doc.processing_time.toFixed(1)}s</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-zinc-500 text-sm">
                No documents processed yet
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricCard({ title, value, icon, trend }: { title: string; value: string | number; icon: React.ReactNode; trend?: React.ReactNode }) {
  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="p-5 rounded-2xl bg-zinc-900/40 border border-zinc-800/60 backdrop-blur-sm relative overflow-hidden group"
    >
      <div className="absolute top-0 right-0 p-4 opacity-10 transform translate-x-2 -translate-y-2 group-hover:scale-110 transition-transform duration-500">
        {icon}
      </div>
      <div className="flex justify-between items-start mb-4">
        <div className="p-2.5 rounded-xl bg-zinc-950 border border-zinc-800/80">
          {icon}
        </div>
        {trend && (
          <div className="flex items-center gap-1 text-xs font-medium bg-zinc-950 px-2 py-1 rounded-md border border-zinc-800">
            {trend}
          </div>
        )}
      </div>
      <div className="space-y-1">
        <h3 className="text-sm font-medium text-zinc-400">{title}</h3>
        <p className="text-2xl font-semibold text-zinc-100">{value}</p>
      </div>
    </motion.div>
  );
}
