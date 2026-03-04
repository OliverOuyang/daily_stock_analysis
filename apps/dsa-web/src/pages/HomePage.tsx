import type React from 'react';
import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import type { HistoryItem, AnalysisReport, TaskInfo } from '../types/analysis';
import type { PortfolioProfile, PortfolioStatus } from '../types/portfolio';
import { historyApi } from '../api/history';
import { analysisApi } from '../api/analysis';
import { portfolioApi } from '../api/portfolio';
import { stocksApi, type StockQuote } from '../api/stocks';
import { getRecentStartDate, getTodayInShanghai } from '../utils/format';
import { useAnalysisStore } from '../stores/analysisStore';
import { ReportSummary } from '../components/report';
import { HistoryList, WatchlistPanel, MarketDiscoverPanel } from '../components/history';
import { TaskPanel } from '../components/tasks';
import { useTaskStream } from '../hooks';
import { clampBatchDelayMs, clampBatchSize, parseStockCodesInput } from './homepageUtils';

const HomePage: React.FC = () => {
  const { setLoading, setError: setStoreError } = useAnalysisStore();
  const navigate = useNavigate();

  const [stockCode, setStockCode] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [inputError, setInputError] = useState<string>();

  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 20;

  const [selectedReport, setSelectedReport] = useState<AnalysisReport | null>(null);
  const [isLoadingReport, setIsLoadingReport] = useState(false);

  const [activeTasks, setActiveTasks] = useState<TaskInfo[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [batchSize] = useState(3);
  const [batchDelayMs] = useState(600);

  const [profiles, setProfiles] = useState<PortfolioProfile[]>([]);
  const [isLoadingProfiles, setIsLoadingProfiles] = useState(false);
  const [profileFilter, setProfileFilter] = useState<'all' | PortfolioStatus | 'favorite'>('all');
  const [profileStatus, setProfileStatus] = useState<PortfolioStatus>('watch');
  const [profileFavorite, setProfileFavorite] = useState(false);
  const [buyPriceInput, setBuyPriceInput] = useState('');
  const [positionPctInput, setPositionPctInput] = useState('');
  const [sharesInput, setSharesInput] = useState('');
  const [totalInvestmentInput, setTotalInvestmentInput] = useState('');
  const [targetBuyInput, setTargetBuyInput] = useState('');
  const [targetSellInput, setTargetSellInput] = useState('');
  const [stopLossInput, setStopLossInput] = useState('');
  const [notesInput, setNotesInput] = useState('');
  const [actionHistory, setActionHistory] = useState<string[]>([]);
  const [newAction, setNewAction] = useState('');

  const [availableCash, setAvailableCash] = useState('');
  const [isAnalyzingPortfolio, setIsAnalyzingPortfolio] = useState(false);

  const [watchlistQuotes, setWatchlistQuotes] = useState<Record<string, StockQuote>>({});
  const [historicalTargets, setHistoricalTargets] = useState<Record<string, { idealBuy?: number; secondaryBuy?: number }>>({});

  const [suggestedValues, setSuggestedValues] = useState<{
    targetBuy?: string;
    targetSell?: string;
    stopLoss?: string;
  }>({});

  const analysisRequestIdRef = useRef<number>(0);

  const updateTask = useCallback((updatedTask: TaskInfo) => {
    setActiveTasks((prev) => {
      const index = prev.findIndex((t) => t.taskId === updatedTask.taskId);
      if (index >= 0) {
        const newTasks = [...prev];
        newTasks[index] = updatedTask;
        return newTasks;
      }
      return prev;
    });
  }, []);

  const removeTask = useCallback((taskId: string) => {
    setActiveTasks((prev) => prev.filter((t) => t.taskId !== taskId));
  }, []);

  useTaskStream({
    onTaskCreated: (task) => {
      setActiveTasks((prev) => {
        if (prev.some((t) => t.taskId === task.taskId)) return prev;
        return [...prev, task];
      });
    },
    onTaskStarted: updateTask,
    onTaskCompleted: () => {
      fetchHistory();
      setTimeout(() => removeTask(''), 2000); 
    },
    onTaskFailed: (task) => {
      updateTask(task);
      setStoreError(task.error || '分析失败');
    },
    enabled: true,
  });

  const currentPageRef = useRef(currentPage);
  currentPageRef.current = currentPage;
  const historyItemsRef = useRef(historyItems);
  historyItemsRef.current = historyItems;
  const selectedReportRef = useRef(selectedReport);
  selectedReportRef.current = selectedReport;

  const fetchWatchlistQuotes = useCallback(async (codes: string[]) => {
    if (codes.length === 0) return;
    try {
      const response = await stocksApi.getBatchQuotes(codes);
      const next: Record<string, StockQuote> = {};
      for (const q of response.items) {
        next[q.stockCode] = q;
      }
      setWatchlistQuotes((prev) => ({ ...prev, ...next }));
    } catch (err) {
      console.warn('Failed to fetch watchlist quotes:', err);
    }
  }, []);

  const fetchPortfolioProfiles = useCallback(async () => {
    setIsLoadingProfiles(true);
    try {
      const response = await portfolioApi.list({ limit: 500 });
      setProfiles(response.items);
      const codes = response.items.map(i => i.stockCode);
      if (codes.length > 0) fetchWatchlistQuotes(codes);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoadingProfiles(false);
    }
  }, [fetchWatchlistQuotes]);

  const resetTradeForm = useCallback(() => {
    setProfileStatus('watch');
    setProfileFavorite(false);
    setBuyPriceInput('');
    setPositionPctInput('');
    setSharesInput('');
    setTotalInvestmentInput('');
    setTargetBuyInput('');
    setTargetSellInput('');
    setStopLossInput('');
    setNotesInput('');
    setActionHistory([]);
  }, []);

  const fillTradeFormFromProfile = useCallback((profile?: PortfolioProfile) => {
    if (!profile) {
      resetTradeForm();
      return;
    }
    setProfileStatus(profile.status);
    setProfileFavorite(profile.isFavorite);
    setBuyPriceInput(profile.buyPrice === undefined ? '' : String(profile.buyPrice));
    setPositionPctInput(profile.positionPct === undefined ? '' : String(profile.positionPct));
    setSharesInput(profile.shares === undefined ? '' : String(profile.shares));
    setTotalInvestmentInput(profile.totalInvestment === undefined ? '' : String(profile.totalInvestment));
    setTargetBuyInput(profile.targetBuyPrice === undefined ? '' : String(profile.targetBuyPrice));
    setTargetSellInput(profile.targetSellPrice === undefined ? '' : String(profile.targetSellPrice));
    setStopLossInput(profile.stopLossPrice === undefined ? '' : String(profile.stopLossPrice));
    setNotesInput(profile.notes || '');
    setActionHistory(profile.actionHistory || []);
  }, [resetTradeForm]);

  const fetchHistory = useCallback(async (autoSelectFirst = false, reset = true, silent = false) => {
    if (!silent) {
      if (reset) { setIsLoadingHistory(true); setCurrentPage(1); }
      else setIsLoadingMore(true);
    }
    const page = reset ? 1 : currentPageRef.current + 1;
    try {
      const response = await historyApi.getList({
        startDate: getRecentStartDate(30),
        endDate: getTodayInShanghai(),
        page, limit: pageSize,
      });
      if (silent && reset) {
        setHistoryItems(prev => {
          const existingIds = new Set(prev.map(item => item.id));
          const newItems = response.items.filter(item => !existingIds.has(item.id));
          return newItems.length > 0 ? [...newItems, ...prev] : prev;
        });
      } else if (reset) {
        setHistoryItems(response.items);
        setCurrentPage(1);
      } else {
        setHistoryItems(prev => [...prev, ...response.items]);
        setCurrentPage(page);
      }
      const targets: Record<string, { idealBuy?: number; secondaryBuy?: number }> = {};
      for (const item of response.items) {
        if (item.strategy && !targets[item.stockCode]) {
          const parsePrice = (s?: string) => s ? parseFloat(s.replace(/[^0-9.]/g, '')) : undefined;
          targets[item.stockCode] = { idealBuy: parsePrice(item.strategy.idealBuy), secondaryBuy: parsePrice(item.strategy.secondaryBuy) };
        }
      }
      setHistoricalTargets(prev => ({ ...prev, ...targets }));
      if (!silent) setHasMore((reset ? response.items.length : historyItemsRef.current.length + response.items.length) < response.total);
      if (autoSelectFirst && response.items.length > 0 && !selectedReportRef.current) {
        setIsLoadingReport(true);
        try {
          const report = await historyApi.getDetail(response.items[0].id);
          setSelectedReport(report);
        } finally { setIsLoadingReport(false); }
      }
    } catch (err) { console.error(err); } finally { setIsLoadingHistory(false); setIsLoadingMore(false); }
  }, [pageSize]);

  useEffect(() => { fetchHistory(true); }, [fetchHistory]);
  useEffect(() => { fetchPortfolioProfiles(); }, [fetchPortfolioProfiles]);
  useEffect(() => {
    const interval = setInterval(() => {
      if (profiles.length > 0 && document.visibilityState === 'visible') fetchWatchlistQuotes(profiles.map(p => p.stockCode));
    }, 60_000);
    return () => clearInterval(interval);
  }, [fetchWatchlistQuotes, profiles]);

  const handleHistoryClick = async (recordId: number) => {
    const requestId = ++analysisRequestIdRef.current;
    try {
      const report = await historyApi.getDetail(recordId);
      if (requestId === analysisRequestIdRef.current) {
        setSelectedReport(report);
        if (report.strategy) {
          setSuggestedValues({ targetBuy: report.strategy.idealBuy || report.strategy.secondaryBuy, targetSell: report.strategy.takeProfit, stopLoss: report.strategy.stopLoss });
        } else setSuggestedValues({});
      }
    } catch (err) { setStoreError('报告加载失败'); }
  };

  const handleAnalyze = async () => {
    const parsed = parseStockCodesInput(stockCode);
    if (parsed.message) { setInputError(parsed.message); return; }
    setInputError(undefined); setIsAnalyzing(true); setLoading(true);
    try {
      const size = clampBatchSize(batchSize);
      const delayMs = clampBatchDelayMs(batchDelayMs);
      for (let i = 0; i < parsed.codes.length; i += size) {
        const chunk = parsed.codes.slice(i, i + size);
        await Promise.allSettled(chunk.map((code) => analysisApi.analyzeAsync({ stockCode: code, reportType: 'detailed' })));
        if (i + size < parsed.codes.length) await new Promise((r) => setTimeout(r, delayMs));
      }
      setStockCode('');
    } catch (err) { setStoreError('分析失败'); } finally { setIsAnalyzing(false); setLoading(false); }
  };

  const handleSaveTradeProfile = async () => {
    const parsed = parseStockCodesInput(stockCode);
    if (parsed.codes.length !== 1) { setInputError('请只输入一个股票代码'); return; }
    const toNumber = (v: string) => { const n = Number(v.trim()); return Number.isFinite(n) ? n : undefined; };
    try {
      await portfolioApi.upsert({
        stockCode: parsed.codes[0], status: profileStatus, isFavorite: profileFavorite,
        buyPrice: toNumber(buyPriceInput), positionPct: toNumber(positionPctInput), shares: toNumber(sharesInput),
        totalInvestment: toNumber(totalInvestmentInput), targetBuyPrice: toNumber(targetBuyInput),
        targetSellPrice: toNumber(targetSellInput), stopLossPrice: toNumber(stopLossInput),
        actionHistory, notes: notesInput.trim() || undefined,
      });
      fetchPortfolioProfiles();
    } catch (err) { setStoreError('保存失败'); }
  };

  const handleSelectFromWatchlist = async (code: string) => {
    setStockCode(code);
    const profile = profiles.find((p) => p.stockCode === code);
    fillTradeFormFromProfile(profile);
    try {
      const response = await historyApi.getList({ stockCode: code, page: 1, limit: 1 });
      if (response.items.length > 0) handleHistoryClick(response.items[0].id);
      else { setSelectedReport(null); setSuggestedValues({}); }
    } catch { setSelectedReport(null); setSuggestedValues({}); }
  };

  const handleAnalyzeFromWatchlist = (codes: string | string[]) => {
    const targetCodes = Array.isArray(codes) ? codes : [codes];
    if (targetCodes.length === 0) return;
    setStockCode(targetCodes.join(','));
    void (async () => {
      setIsAnalyzing(true);
      setLoading(true);
      try {
        await Promise.allSettled(
          targetCodes.map((code) => analysisApi.analyzeAsync({ stockCode: code, reportType: 'detailed' })),
        );
      } catch (err) {
        setStoreError('分析失败');
      } finally {
        setIsAnalyzing(false);
        setLoading(false);
      }
    })();
  };

  const handleAnalyzePortfolio = async () => {
    setIsAnalyzingPortfolio(true);
    try {
      const holdings = profiles.filter(p => p.status === 'holding').map(h => `${h.stockCode}(${h.shares}股)`).join(',');
      navigate(`/chat?stock=PORTFOLIO&mode=review&cash=${availableCash}&holdings=${holdings}`);
    } finally { setIsAnalyzingPortfolio(false); }
  };

  const addAction = () => {
    if (!newAction.trim()) return;
    const action = `[${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}] ${newAction.trim()}`;
    setActionHistory((prev) => [action, ...prev]); setNewAction('');
  };

  const filteredProfiles = profiles.filter((item) => profileFilter === 'favorite' ? item.isFavorite : profileFilter === 'all' ? true : item.status === profileFilter);
  const singleSaveCode = !parseStockCodesInput(stockCode).message && parseStockCodesInput(stockCode).codes.length === 1 ? parseStockCodesInput(stockCode).codes[0] : '';

  useEffect(() => { if (singleSaveCode) fillTradeFormFromProfile(profiles.find((p) => p.stockCode === singleSaveCode)); }, [fillTradeFormFromProfile, profiles, singleSaveCode]);

  const sidebarItems = (
    <div className="flex flex-col gap-3">
      <WatchlistPanel items={filteredProfiles} isLoading={isLoadingProfiles} quotes={watchlistQuotes} historicalTargets={historicalTargets} filter={profileFilter} onFilterChange={setProfileFilter} onUseCode={handleSelectFromWatchlist} onAnalyze={handleAnalyzeFromWatchlist} onDelete={(c) => portfolioApi.remove(c).then(fetchPortfolioProfiles)} />
      <MarketDiscoverPanel onSelectStock={handleSelectFromWatchlist} onAnalyze={(code) => handleAnalyzeFromWatchlist(code)} onFavoriteAdded={fetchPortfolioProfiles} />
      <TaskPanel tasks={activeTasks} />
      <HistoryList items={historyItems} isLoading={isLoadingHistory} isLoadingMore={isLoadingMore} hasMore={hasMore} selectedId={selectedReport?.meta.id} onItemClick={handleHistoryClick} onLoadMore={() => !isLoadingMore && hasMore && fetchHistory(false, false)} className="flex-1 min-h-[200px]" />
    </div>
  );

  return (
    <div className="min-h-screen flex flex-col md:grid overflow-hidden w-full bg-[#0a0e17]" style={{ gridTemplateColumns: '12px 260px 24px 1fr 12px', gridTemplateRows: 'auto 1fr' }}>
      <header className="md:col-start-2 md:col-end-5 py-2 px-3 md:px-0 border-b border-white/5 flex-shrink-0">
        <div className="max-w-7xl mx-auto space-y-2">
          <div className="flex items-center gap-2">
            <button onClick={() => setSidebarOpen(true)} className="md:hidden p-1 rounded hover:bg-white/10 text-secondary"><svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M4 6h16M4 12h16M4 18h16" /></svg></button>
            <input type="text" value={stockCode} onChange={(e) => setStockCode(e.target.value.toUpperCase())} placeholder="输入代码，如: 600519" className="input-terminal py-1.5 px-3 flex-1 text-sm bg-white/5" />
            <button onClick={handleAnalyze} disabled={!stockCode || isAnalyzing} className="btn-primary h-9 px-6 text-sm shadow-cyan/20">{isAnalyzing ? '分析中...' : '执行分析'}</button>
          </div>
          <div className="text-[10px] text-muted font-mono">build: e7559e1</div>
          {inputError && <p className="text-[11px] text-rose-400">{inputError}</p>}

          <div className="glass-card p-2 border-white/5 grid grid-cols-1 xl:grid-cols-12 gap-3 items-start">
            <div className="xl:col-span-4 space-y-2">
              <div className="flex items-center gap-2"><div className="w-1 h-3 bg-cyan rounded-full" /><span className="text-[10px] font-bold text-muted uppercase">持仓</span></div>
              <div className="grid grid-cols-2 gap-2">
                <input value={buyPriceInput} onChange={e => setBuyPriceInput(e.target.value)} placeholder="成本价" className="input-terminal py-1 px-2 text-[11px]" />
                <input value={positionPctInput} onChange={e => setPositionPctInput(e.target.value)} placeholder="仓位%" className="input-terminal py-1 px-2 text-[11px]" />
                <input value={sharesInput} onChange={e => setSharesInput(e.target.value)} placeholder="股数" className="input-terminal py-1 px-2 text-[11px]" />
                <select value={profileStatus} onChange={e => setProfileStatus(e.target.value as PortfolioStatus)} className="input-terminal py-1 px-2 text-[11px] bg-white/5"><option value="holding">持仓</option><option value="watch">观望</option><option value="candidate">候选</option></select>
              </div>
              <div className="flex gap-2">
                <button onClick={handleSaveTradeProfile} className="btn-primary py-1 px-3 text-[10px] flex-1">保存</button>
                <button onClick={() => setProfileFavorite(!profileFavorite)} className={`p-1 px-2 rounded border text-[10px] ${profileFavorite ? 'text-amber-400 border-amber-400/30 bg-amber-400/5' : 'text-muted border-white/10'}`}>★</button>
              </div>
            </div>

            <div className="xl:col-span-4 space-y-2 border-x border-white/5 px-3">
              <div className="flex items-center gap-2"><div className="w-1 h-3 bg-amber-500 rounded-full" /><span className="text-[10px] font-bold text-muted uppercase">资产分析 & AI 点位</span></div>
              <div className="flex gap-1.5">
                <input value={availableCash} onChange={e => setAvailableCash(e.target.value)} placeholder="可用现金" className="input-terminal py-1 px-2 text-[11px] flex-1" />
                <button onClick={handleAnalyzePortfolio} disabled={isAnalyzingPortfolio} className="px-2 py-1 rounded bg-amber-500/20 text-amber-300 text-[10px] border border-amber-500/30 disabled:opacity-60">{isAnalyzingPortfolio ? '诊断中...' : '诊断'}</button>
              </div>
              <div className="grid grid-cols-3 gap-1.5">
                <div className="space-y-1"><div className="flex justify-between text-[9px] text-muted">入场 {suggestedValues.targetBuy && <span onClick={() => setTargetBuyInput(suggestedValues.targetBuy!.replace(/[^0-9.]/g,''))} className="text-cyan cursor-pointer">点</span>}</div><input value={targetBuyInput} onChange={e=>setTargetBuyInput(e.target.value)} className="input-terminal py-1 px-2 text-[10px] w-full" /></div>
                <div className="space-y-1"><div className="flex justify-between text-[9px] text-muted">止盈 {suggestedValues.targetSell && <span onClick={() => setTargetSellInput(suggestedValues.targetSell!.replace(/[^0-9.]/g,''))} className="text-emerald-400 cursor-pointer">点</span>}</div><input value={targetSellInput} onChange={e=>setTargetSellInput(e.target.value)} className="input-terminal py-1 px-2 text-[10px] w-full" /></div>
                <div className="space-y-1"><div className="flex justify-between text-[9px] text-muted">止损 {suggestedValues.stopLoss && <span onClick={() => setStopLossInput(suggestedValues.stopLoss!.replace(/[^0-9.]/g,''))} className="text-rose-400 cursor-pointer">点</span>}</div><input value={stopLossInput} onChange={e=>setStopLossInput(e.target.value)} className="input-terminal py-1 px-2 text-[10px] w-full" /></div>
              </div>
            </div>

            <div className="xl:col-span-4 space-y-2">
              <div className="flex items-center gap-2"><div className="w-1 h-3 bg-purple-500 rounded-full" /><span className="text-[10px] font-bold text-muted uppercase">日志</span></div>
              <div className="flex gap-1.5"><input value={newAction} onChange={e=>setNewAction(e.target.value)} placeholder="新记录..." className="input-terminal py-1 px-2 text-[11px] flex-1" onKeyDown={e=>e.key==='Enter'&&addAction()} /><button onClick={addAction} className="px-2 py-1 rounded bg-white/10 text-[10px]">记</button></div>
              <div className="max-h-16 overflow-y-auto space-y-1 pr-1 custom-scrollbar">
                {actionHistory.slice(0,3).map((act, i) => <div key={i} className="text-[9px] text-secondary py-0.5 px-1.5 rounded bg-white/5 border border-white/5 flex justify-between"><span>{act}</span><button onClick={()=>setActionHistory(prev=>prev.filter((_,idx)=>idx!==i))} className="text-rose-400 ml-1">×</button></div>)}
                <textarea value={notesInput} onChange={e=>setNotesInput(e.target.value)} placeholder="笔记..." rows={1} className="input-terminal py-1 px-2 text-[10px] w-full resize-none mt-1 border-dashed" />
              </div>
            </div>
          </div>
        </div>
      </header>

      <div className="hidden md:flex col-start-2 row-start-2 flex-col gap-3 overflow-y-auto min-h-0 h-full pr-1 custom-scrollbar py-3">{sidebarItems}</div>
      {sidebarOpen && <div className="fixed inset-0 z-40 md:hidden" onClick={()=>setSidebarOpen(false)}><div className="absolute inset-0 bg-black/60" /><div className="absolute left-0 top-0 bottom-0 w-72 flex flex-col glass-card border-r border-white/10 p-3" onClick={e=>e.stopPropagation()}>{sidebarItems}</div></div>}
      <section className="md:col-start-4 md:row-start-2 flex-1 overflow-y-auto px-3 md:px-0 py-3">{isLoadingReport ? <div className="flex flex-col items-center justify-center h-full"><div className="w-10 h-10 border-3 border-cyan/20 border-t-cyan rounded-full animate-spin" /><p className="mt-3 text-secondary text-sm">加载中...</p></div> : selectedReport ? <div className="max-w-4xl mx-auto"><div className="flex justify-end mb-2"><button onClick={()=>navigate(`/chat?stock=${selectedReport.meta.stockCode}&rid=${selectedReport.meta.id}`)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan/10 border border-cyan/20 text-cyan text-sm">追问 AI</button></div><ReportSummary data={selectedReport} isHistory /></div> : <div className="flex flex-col items-center justify-center h-full text-center text-muted"><h3 className="text-base font-medium text-white mb-1">开始分析</h3><p className="text-xs">选择或输入股票代码查看深度报告</p></div>}</section>
    </div>
  );
};

export default HomePage;
