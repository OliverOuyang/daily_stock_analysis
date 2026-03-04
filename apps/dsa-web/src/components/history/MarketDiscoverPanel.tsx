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
    <div className="glass-card flex flex-col overflow-hidden">
      <div className="p-3 border-b border-white/5 flex items-center justify-between">
        <h2 className="text-xs font-medium text-cyan uppercase tracking-wider flex items-center gap-1.5">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-500"></span>
          </span>
          今日市场异动
        </h2>
        <button 
          onClick={fetchDiscovery}
          disabled={isLoading}
          className="text-[10px] text-muted hover:text-cyan transition-colors"
        >
          {isLoading ? '扫描中...' : '刷新'}
        </button>
      </div>

      <div className="p-2 space-y-3 max-h-[300px] overflow-y-auto custom-scrollbar">
        {error ? (
          <div className="py-4 text-center text-[11px] text-danger">{error}</div>
        ) : isLoading && !data ? (
          <div className="py-8 text-center text-[11px] text-muted">正在扫描板块轮动...</div>
        ) : data?.sectors.length === 0 ? (
          <div className="py-4 text-center text-[11px] text-muted">暂无显著异动板块</div>
        ) : (
          data?.sectors.map((sector: SectorDiscoverItem) => (
            <div key={sector.sectorName} className="space-y-1.5">
              <div className="flex items-center justify-between px-1">
                <span className="text-[11px] font-medium text-white">{sector.sectorName}</span>
                <span className={`text-[10px] ${sector.changePct && sector.changePct > 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {sector.changePct?.toFixed(2)}%
                </span>
              </div>
              <div className="grid grid-cols-1 gap-1">
                {sector.leaders.map((leader) => (
                  <div 
                    key={leader.stockCode}
                    className="flex items-center justify-between p-1.5 rounded bg-white/5 border border-white/5 hover:border-cyan/30 transition-colors group"
                  >
                    <div 
                      className="flex-1 cursor-pointer min-w-0" 
                      onClick={() => onSelectStock(leader.stockCode)}
                    >
                      <p className="text-[11px] text-secondary truncate">{leader.stockName}</p>
                      <p className="text-[9px] text-muted font-mono">{leader.stockCode}</p>
                    </div>
                    <div className="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button 
                        onClick={() => onAnalyze(leader.stockCode)}
                        className="text-[9px] px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30"
                      >
                        分析
                      </button>
                    </div>
                    <span className="text-[10px] text-emerald-400 ml-2 group-hover:hidden">
                      {leader.changePct && leader.changePct > 0 ? `+${leader.changePct.toFixed(1)}%` : `${leader.changePct?.toFixed(1)}%`}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
      <div className="p-2 bg-white/5 border-t border-white/5">
        <p className="text-[9px] text-muted italic">基于板块强度与领涨地位自动筛选</p>
      </div>
    </div>
  );
};
