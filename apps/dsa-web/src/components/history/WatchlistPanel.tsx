import type React from 'react';
import type { PortfolioProfile, PortfolioStatus } from '../../types/portfolio';

type FilterValue = 'all' | PortfolioStatus | 'favorite';

interface WatchlistPanelProps {
  items: PortfolioProfile[];
  isLoading: boolean;
  filter: FilterValue;
  onFilterChange: (value: FilterValue) => void;
  onUseCode: (code: string) => void;
  onAnalyze: (code: string) => void;
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

export const WatchlistPanel: React.FC<WatchlistPanelProps> = ({
  items,
  isLoading,
  filter,
  onFilterChange,
  onUseCode,
  onAnalyze,
  onDelete,
}) => {
  return (
    <aside className="glass-card overflow-hidden flex flex-col">
      <div className="p-3 space-y-2">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-xs font-medium text-cyan uppercase tracking-wider">自选池筛选</h2>
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

        {isLoading ? (
          <div className="py-3 text-xs text-muted text-center">加载中...</div>
        ) : items.length === 0 ? (
          <div className="py-3 text-xs text-muted text-center">暂无交易档案</div>
        ) : (
          <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1">
            {items.map((item) => (
              <div key={item.id} className="rounded-lg border border-white/10 bg-black/20 p-2">
                <div className="flex items-center justify-between gap-2">
                  <button
                    type="button"
                    onClick={() => onUseCode(item.stockCode)}
                    className="text-left min-w-0"
                    title="填入输入框"
                  >
                    <p className="text-xs text-white truncate">{item.stockName || item.stockCode}</p>
                    <p className="text-[11px] text-muted font-mono">{item.stockCode}</p>
                  </button>
                  <div className="flex items-center gap-1">
                    {item.isFavorite && <span className="text-amber-300 text-xs">★</span>}
                    <span className={`text-[11px] px-1.5 py-0.5 border rounded ${STATUS_BADGE[item.status]}`}>
                      {STATUS_LABEL[item.status]}
                    </span>
                  </div>
                </div>
                <div className="mt-1 text-[11px] text-muted flex items-center gap-2">
                  <span>买入: {item.buyPrice ?? '--'}</span>
                  <span>仓位: {item.positionPct ?? '--'}%</span>
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <button
                    type="button"
                    className="text-[11px] px-2 py-1 rounded border border-cyan/30 text-cyan hover:bg-cyan/15"
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
            ))}
          </div>
        )}
      </div>
    </aside>
  );
};
