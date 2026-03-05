import type React from 'react';
import { useState } from 'react';
import type { PortfolioProfile, PortfolioStatus } from '../../types/portfolio';
import type { StockQuote } from '../../api/stocks';

type FilterValue = 'all' | PortfolioStatus | 'favorite';

interface WatchlistPanelProps {
  items: PortfolioProfile[];
  isLoading: boolean;
  quotes?: Record<string, StockQuote>;
  historicalTargets?: Record<string, { idealBuy?: number; secondaryBuy?: number }>;
  filter: FilterValue;
  onFilterChange: (value: FilterValue) => void;
  onUseCode: (code: string) => void;
  onAnalyze: (code: string | string[]) => void;
  onDelete: (code: string) => void;
}

const STATUS_LABEL: Record<PortfolioStatus, string> = {
  holding: '持仓',
  watch: '观望',
  candidate: '候选',
  archived: '归档',
};

const STATUS_BADGE: Record<PortfolioStatus, string> = {
  holding: 'text-emerald-300 bg-emerald-500/15 border-emerald-500/30',
  watch: 'text-amber-300 bg-amber-500/15 border-amber-500/30',
  candidate: 'text-cyan-300 bg-cyan-500/15 border-cyan-500/30',
  archived: 'text-slate-300 bg-slate-500/15 border-slate-500/30',
};

const BuyOpportunityBadge: React.FC = () => (
  <span className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-amber-500/20 border border-amber-500/40 text-[10px] text-amber-300 animate-pulse">
    ✨ 买入机会
  </span>
);

export const WatchlistPanel: React.FC<WatchlistPanelProps> = ({
  items,
  isLoading,
  quotes = {},
  historicalTargets = {},
  filter,
  onFilterChange,
  onUseCode,
  onAnalyze,
  onDelete,
}) => {
  const [selectedCodes, setSelectedCodes] = useState<Set<string>>(new Set());

  const toggleSelect = (code: string) => {
    const next = new Set(selectedCodes);
    if (next.has(code)) {
      next.delete(code);
    } else {
      next.add(code);
    }
    setSelectedCodes(next);
  };

  const toggleAll = () => {
    if (selectedCodes.size === items.length && items.length > 0) {
      setSelectedCodes(new Set());
    } else {
      setSelectedCodes(new Set(items.map(i => i.stockCode)));
    }
  };

  const handleBatchAnalyze = () => {
    if (selectedCodes.size > 0) {
      onAnalyze(Array.from(selectedCodes));
      setSelectedCodes(new Set());
    }
  };

  const checkBuyOpportunity = (code: string) => {
    const quote = quotes[code];
    const target = historicalTargets[code];
    if (!quote || !target) return false;

    const price = quote.currentPrice;
    const ideal = target.idealBuy;
    const secondary = target.secondaryBuy;

    if (!ideal && !secondary) return false;

    // 如果价格在 [secondary*0.98, ideal*1.02] 之间，认为进入买入区
    const low = Math.min(ideal || secondary!, secondary || ideal!) * 0.98;
    const high = Math.max(ideal || secondary!, secondary || ideal!) * 1.02;
    
    return price >= low && price <= high;
  };

  return (
    <aside className="glass-card overflow-hidden flex flex-col">
      <div className="p-3 space-y-2">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <h2 className="text-xs font-medium text-cyan uppercase tracking-wider">自选池筛选</h2>
            {items.length > 0 && (
              <button
                onClick={toggleAll}
                className="text-[10px] text-muted hover:text-cyan px-1.5 py-0.5 border border-white/10 rounded"
              >
                {selectedCodes.size === items.length ? '全取消' : '全选'}
              </button>
            )}
          </div>
          <select
            value={filter}
            onChange={(e) => onFilterChange(e.target.value as FilterValue)}
            className="input-terminal text-xs py-1 px-2 max-w-28"
          >
            <option value="all">全部</option>
            <option value="holding">持仓</option>
            <option value="watch">观望</option>
            <option value="candidate">候选</option>
            <option value="favorite">收藏</option>
          </select>
        </div>

        {selectedCodes.size > 0 && (
          <div className="flex items-center justify-between p-2 rounded-lg bg-cyan/10 border border-cyan/30 mb-2">
            <span className="text-[11px] text-cyan-300">已选 {selectedCodes.size} 个股票</span>
            <button
              onClick={handleBatchAnalyze}
              className="text-[11px] px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30 transition-colors"
            >
              分析选中
            </button>
          </div>
        )}

        {isLoading ? (
          <div className="py-3 text-xs text-muted text-center">加载中...</div>
        ) : items.length === 0 ? (
          <div className="py-3 text-xs text-muted text-center">暂无交易档案</div>
        ) : (
          <div className="space-y-1.5 max-h-[360px] md:max-h-[360px] overflow-y-auto pr-1 custom-scrollbar">
            {items.map((item) => {
              const quote = quotes[item.stockCode];
              const isOpportunity = checkBuyOpportunity(item.stockCode);
              const displayName =
                (item.stockName && item.stockName !== item.stockCode ? item.stockName : undefined)
                || (quote?.stockName && quote.stockName !== item.stockCode ? quote.stockName : undefined)
                || item.stockCode;
              return (
                <div
                  key={item.id}
                  className={`rounded-lg border transition-colors p-2 ${
                    selectedCodes.has(item.stockCode)
                      ? 'border-cyan/50 bg-cyan/5'
                      : 'border-white/10 bg-black/20'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={selectedCodes.has(item.stockCode)}
                      onChange={() => toggleSelect(item.stockCode)}
                      className="w-3.5 h-3.5 rounded border-white/20 bg-black/50 text-cyan-500"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <button
                          type="button"
                          onClick={() => onUseCode(item.stockCode)}
                          className="text-left min-w-0"
                          title="填入输入框"
                        >
                          <p className="text-xs text-white truncate font-medium">{displayName}</p>
                          <p className="text-[10px] text-muted font-mono">{item.stockCode}</p>
                        </button>
                        <div className="flex flex-col items-end gap-1">
                          <span className={`text-[11px] px-1.5 py-0.5 border rounded ${STATUS_BADGE[item.status]}`}>
                            {STATUS_LABEL[item.status]}
                          </span>
                          {isOpportunity && <BuyOpportunityBadge />}
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  <div className="mt-1.5 flex items-center justify-between">
                    <div className="text-[11px] text-muted flex items-center gap-x-3 gap-y-1 flex-wrap">
                      <span>买入: <span className="text-secondary">{item.buyPrice ?? '--'}</span></span>
                      <span>仓位: <span className="text-secondary">{item.positionPct ?? '--'}%</span></span>
                    </div>
                    {quote && (
                      <div className="text-right">
                        <span className="text-[11px] text-white font-mono">{quote.currentPrice.toFixed(2)}</span>
                        <span className={`text-[10px] ml-1.5 ${quote.changePercent && quote.changePercent >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {quote.changePercent ? (quote.changePercent > 0 ? `+${quote.changePercent.toFixed(2)}%` : `${quote.changePercent.toFixed(2)}%`) : '--'}
                        </span>
                      </div>
                    )}
                  </div>

                  <div className="mt-2 flex items-center gap-2">
                    <button
                      type="button"
                      className="text-[11px] px-2 py-1 rounded border border-cyan/30 text-cyan hover:bg-cyan/15 flex-1"
                      onClick={() => onUseCode(item.stockCode)}
                    >
                      填入
                    </button>
                    <button
                      type="button"
                      className="text-[11px] px-2 py-1 rounded border border-emerald-400/30 text-emerald-300 hover:bg-emerald-500/15"
                      onClick={() => onAnalyze(item.stockCode)}
                    >
                      分析
                    </button>
                    <button
                      type="button"
                      className="text-[11px] px-2 py-1 rounded border border-rose-400/30 text-rose-300 hover:bg-rose-500/15"
                      onClick={() => onDelete(item.stockCode)}
                    >
                      删除
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </aside>
  );
};
