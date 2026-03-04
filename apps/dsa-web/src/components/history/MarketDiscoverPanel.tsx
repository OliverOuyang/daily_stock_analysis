import type React from 'react';
import { useState, useEffect } from 'react';
import type { MarketDiscoverResponse, SectorDiscoverItem } from '../../types/market';
import { marketApi } from '../../api/market';

interface MarketDiscoverPanelProps {
  onSelectStock: (code: string) => void;
  onAnalyze: (code: string) => void;
}

export const MarketDiscoverPanel: React.FC<MarketDiscoverPanelProps> = ({
  onSelectStock,
  onAnalyze,
}) => {
  const [data, setData] = useState<MarketDiscoverResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDiscovery = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await marketApi.discover({ triggerAnalysis: false });
      setData(res);
    } catch (err) {
      setError('获取市场发现数据失败');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDiscovery();
  }, []);

  return (
    <div className="glass-card flex flex-col overflow-hidden border-cyan/10 shadow-lg shadow-cyan/5">
      <div className="p-3 border-b border-white/5 flex items-center justify-between bg-white/[0.02]">
        <h2 className="text-xs font-semibold text-cyan uppercase tracking-wider flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-500"></span>
          </span>
          今日市场异动
        </h2>
        <button 
          onClick={fetchDiscovery}
          disabled={isLoading}
          className="text-[10px] text-muted hover:text-cyan transition-colors flex items-center gap-1"
        >
          {isLoading ? (
            <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
          ) : (
            <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          )}
          {isLoading ? '扫描中' : '刷新'}
        </button>
      </div>

      <div className="p-2 space-y-4 max-h-[320px] overflow-y-auto custom-scrollbar bg-black/10">
        {error ? (
          <div className="py-6 text-center">
            <p className="text-[11px] text-rose-400 mb-2">{error}</p>
            <button onClick={fetchDiscovery} className="text-[10px] px-2 py-1 rounded bg-white/5 border border-white/10 text-muted">重试</button>
          </div>
        ) : isLoading && !data ? (
          <div className="py-12 flex flex-col items-center justify-center gap-3">
            <div className="w-6 h-6 border-2 border-cyan/20 border-t-cyan rounded-full animate-spin" />
            <p className="text-[10px] text-muted animate-pulse">正在扫描板块轮动...</p>
          </div>
        ) : data?.sectors.length === 0 ? (
          <div className="py-8 text-center text-[11px] text-muted italic">暂无显著异动板块</div>
        ) : (
          data?.sectors.map((sector: SectorDiscoverItem) => (
            <div key={sector.sectorName} className="space-y-1.5 group/sector">
              <div className="flex items-center justify-between px-2 py-1 rounded bg-white/[0.03] border-l-2 border-cyan/50">
                <span className="text-[11px] font-bold text-white tracking-wide">{sector.sectorName}</span>
                <span className={`text-[10px] font-mono ${sector.changePct && sector.changePct > 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {sector.changePct && sector.changePct > 0 ? '+' : ''}{sector.changePct?.toFixed(2)}%
                </span>
              </div>
              <div className="grid grid-cols-1 gap-1 pl-1">
                {sector.leaders.map((leader) => (
                  <div 
                    key={leader.stockCode}
                    className="flex items-center justify-between p-2 rounded-md bg-white/[0.01] border border-transparent hover:bg-white/5 hover:border-white/10 transition-all duration-200 group/item"
                  >
                    <div 
                      className="flex-1 cursor-pointer min-w-0" 
                      onClick={() => onSelectStock(leader.stockCode)}
                    >
                      <p className="text-[11px] text-secondary group-hover/item:text-cyan transition-colors truncate font-medium">{leader.stockName}</p>
                      <p className="text-[9px] text-muted font-mono opacity-70">{leader.stockCode}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono text-emerald-400 group-hover/item:hidden">
                        {leader.changePct && leader.changePct > 0 ? '+' : ''}{leader.changePct?.toFixed(1)}%
                      </span>
                      <button 
                        onClick={(e) => { e.stopPropagation(); onAnalyze(leader.stockCode); }}
                        className="hidden group-hover/item:flex items-center gap-1 text-[9px] px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 hover:bg-cyan-500/30 transition-all"
                      >
                        分析
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
      <div className="p-2 bg-white/[0.02] border-t border-white/5 flex items-center justify-between">
        <p className="text-[9px] text-muted italic">数据源: Akshare 智能筛选</p>
        <div className="flex gap-1">
          <div className="w-1 h-1 rounded-full bg-emerald-500/50" />
          <div className="w-1 h-1 rounded-full bg-cyan-500/50" />
          <div className="w-1 h-1 rounded-full bg-blue-500/50" />
        </div>
      </div>
    </div>
  );
};
