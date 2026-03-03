import type React from 'react';
import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import type { HistoryItem, AnalysisReport, TaskInfo } from '../types/analysis';
import type { PortfolioProfile, PortfolioStatus } from '../types/portfolio';
import { historyApi } from '../api/history';
import { analysisApi, DuplicateTaskError } from '../api/analysis';
import { portfolioApi } from '../api/portfolio';
import { getRecentStartDate, getTodayInShanghai } from '../utils/format';
import { useAnalysisStore } from '../stores/analysisStore';
import { ReportSummary } from '../components/report';
import { HistoryList, WatchlistPanel } from '../components/history';
import { TaskPanel } from '../components/tasks';
import { useTaskStream } from '../hooks';
import { clampBatchDelayMs, clampBatchSize, parseStockCodesInput } from './homepageUtils';

/**
 * 首页 - 单页设计
 * 顶部输入 + 左侧历史 + 右侧报告
 */
const HomePage: React.FC = () => {
  const { setLoading, setError: setStoreError } = useAnalysisStore();
  const navigate = useNavigate();

  // 输入状态
  const [stockCode, setStockCode] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [inputError, setInputError] = useState<string>();

// 历史列表状态
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 20;

  // 报告详情状态
  const [selectedReport, setSelectedReport] = useState<AnalysisReport | null>(null);
  const [isLoadingReport, setIsLoadingReport] = useState(false);

  // 任务队列状态
  const [activeTasks, setActiveTasks] = useState<TaskInfo[]>([]);
  const [duplicateError, setDuplicateError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [batchSize, setBatchSize] = useState(3);
  const [batchDelayMs, setBatchDelayMs] = useState(600);
  const [batchInfo, setBatchInfo] = useState<string | null>(null);

  // 自选池/交易档案
  const [profiles, setProfiles] = useState<PortfolioProfile[]>([]);
  const [isLoadingProfiles, setIsLoadingProfiles] = useState(false);
  const [profileFilter, setProfileFilter] = useState<'all' | PortfolioStatus | 'favorite'>('all');
  const [profileStatus, setProfileStatus] = useState<PortfolioStatus>('watch');
  const [profileFavorite, setProfileFavorite] = useState(false);
  const [buyPriceInput, setBuyPriceInput] = useState('');
  const [positionPctInput, setPositionPctInput] = useState('');
  const [sharesInput, setSharesInput] = useState('');
  const [targetBuyInput, setTargetBuyInput] = useState('');
  const [targetSellInput, setTargetSellInput] = useState('');
  const [stopLossInput, setStopLossInput] = useState('');
  const [notesInput, setNotesInput] = useState('');

  // 用于跟踪当前分析请求，避免竞态条件
  const analysisRequestIdRef = useRef<number>(0);

  // 更新任务列表中的任务
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

  // 移除已完成/失败的任务
  const removeTask = useCallback((taskId: string) => {
    setActiveTasks((prev) => prev.filter((t) => t.taskId !== taskId));
  }, []);

  // SSE 任务流
  useTaskStream({
    onTaskCreated: (task) => {
      setActiveTasks((prev) => {
        // 避免重复添加
        if (prev.some((t) => t.taskId === task.taskId)) return prev;
        return [...prev, task];
      });
    },
    onTaskStarted: updateTask,
    onTaskCompleted: (task) => {
      // 刷新历史列表
      fetchHistory();
      // 延迟移除任务，让用户看到完成状态
      setTimeout(() => removeTask(task.taskId), 2000);
    },
    onTaskFailed: (task) => {
      updateTask(task);
      // 显示错误提示
      setStoreError(task.error || '分析失败');
      // 延迟移除任务
      setTimeout(() => removeTask(task.taskId), 5000);
    },
    onError: () => {
      console.warn('SSE 连接断开，正在重连...');
    },
    enabled: true,
  });

// 用 ref 追踪易变状态，避免 fetchHistory 频繁重建导致 effect 循环
  const currentPageRef = useRef(currentPage);
  currentPageRef.current = currentPage;
  const historyItemsRef = useRef(historyItems);
  historyItemsRef.current = historyItems;
  const selectedReportRef = useRef(selectedReport);
  selectedReportRef.current = selectedReport;

  const fetchPortfolioProfiles = useCallback(async () => {
    setIsLoadingProfiles(true);
    try {
      const response = await portfolioApi.list({ limit: 500 });
      setProfiles(response.items);
    } catch (err) {
      console.error('Failed to fetch portfolio profiles:', err);
    } finally {
      setIsLoadingProfiles(false);
    }
  }, []);

  const fillTradeFormFromProfile = useCallback((profile?: PortfolioProfile) => {
    if (!profile) return;
    setProfileStatus(profile.status);
    setProfileFavorite(profile.isFavorite);
    setBuyPriceInput(profile.buyPrice === undefined ? '' : String(profile.buyPrice));
    setPositionPctInput(profile.positionPct === undefined ? '' : String(profile.positionPct));
    setSharesInput(profile.shares === undefined ? '' : String(profile.shares));
    setTargetBuyInput(profile.targetBuyPrice === undefined ? '' : String(profile.targetBuyPrice));
    setTargetSellInput(profile.targetSellPrice === undefined ? '' : String(profile.targetSellPrice));
    setStopLossInput(profile.stopLossPrice === undefined ? '' : String(profile.stopLossPrice));
    setNotesInput(profile.notes || '');
  }, []);

  const submitAnalyzeCodesInBatches = useCallback(async (codes: string[]) => {
    let accepted = 0;
    let duplicated = 0;

    const size = clampBatchSize(batchSize);
    const delayMs = clampBatchDelayMs(batchDelayMs);
    for (let i = 0; i < codes.length; i += size) {
      const chunk = codes.slice(i, i + size);
      const settled = await Promise.allSettled(
        chunk.map((code) => analysisApi.analyzeAsync({ stockCode: code, reportType: 'detailed' }))
      );
      for (const item of settled) {
        if (item.status === 'fulfilled') {
          accepted += 1;
        } else if (item.reason instanceof DuplicateTaskError) {
          duplicated += 1;
        } else {
          console.warn('Batch analyze submit failed:', item.reason);
        }
      }
      if (i + size < codes.length && delayMs > 0) {
        await new Promise((resolve) => setTimeout(resolve, delayMs));
      }
    }
    setBatchInfo(`已提交 ${accepted}/${codes.length} 只，重复任务 ${duplicated} 只`);
  }, [batchDelayMs, batchSize]);

  // 加载历史列表
  const fetchHistory = useCallback(async (autoSelectFirst = false, reset = true, silent = false) => {
    if (!silent) {
      if (reset) {
        setIsLoadingHistory(true);
        setCurrentPage(1);
      } else {
        setIsLoadingMore(true);
      }
    }

    // page is always 1 when reset=true, regardless of currentPageRef; the ref
    // is only used for load-more (reset=false) to get the next page number.
    const page = reset ? 1 : currentPageRef.current + 1;

    try {
      const response = await historyApi.getList({
        startDate: getRecentStartDate(30),
        endDate: getTodayInShanghai(),
        page,
        limit: pageSize,
      });

      if (silent && reset) {
        // 后台刷新：合并新增项到列表顶部，保留已加载的分页数据和滚动位置
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

      // 判断是否还有更多数据
      if (!silent) {
        const totalLoaded = reset ? response.items.length : historyItemsRef.current.length + response.items.length;
        setHasMore(totalLoaded < response.total);
      }

      // 如果需要自动选择第一条，且有数据，且当前没有选中报告
      if (autoSelectFirst && response.items.length > 0 && !selectedReportRef.current) {
        const firstItem = response.items[0];
        setIsLoadingReport(true);
        try {
          const report = await historyApi.getDetail(firstItem.id);
          setSelectedReport(report);
        } catch (err) {
          console.error('Failed to fetch first report:', err);
        } finally {
          setIsLoadingReport(false);
        }
      }
    } catch (err) {
      console.error('Failed to fetch history:', err);
    } finally {
      setIsLoadingHistory(false);
      setIsLoadingMore(false);
    }
  }, [pageSize]);

  // 加载更多历史记录
  const handleLoadMore = useCallback(() => {
    if (!isLoadingMore && hasMore) {
      fetchHistory(false, false);
    }
  }, [fetchHistory, isLoadingMore, hasMore]);

  // 初始加载 - 自动选择第一条（仅挂载时执行一次）
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    fetchHistory(true);
  }, []);

  useEffect(() => {
    fetchPortfolioProfiles();
  }, [fetchPortfolioProfiles]);

  // Background polling: re-fetch history every 30s for CLI-initiated analyses
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    const interval = setInterval(() => {
      fetchHistory(false, true, true);
    }, 30_000);
    return () => clearInterval(interval);
  }, []);

  // Refresh when tab regains visibility (e.g. user ran main.py in another terminal)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        fetchHistory(false, true, true);
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, []);

  // 点击历史项加载报告
  const handleHistoryClick = async (recordId: number) => {
    // Increment request ID to cancel any in-flight auto-select result.
    const requestId = ++analysisRequestIdRef.current;

    // Keep the current report visible while
    // the new one loads so the right panel doesn't flash a blank spinner on
    // every click. isLoadingReport is only used for the initial empty state.
    try {
      const report = await historyApi.getDetail(recordId);
      // Ignore result if a newer click has already been issued.
      if (requestId === analysisRequestIdRef.current) {
        setSelectedReport(report);
      }
    } catch (err) {
      console.error('Failed to fetch report:', err);
      setStoreError(err instanceof Error ? err.message : '报告加载失败');
    }
  };

  // 分析股票（异步模式）
  const handleAnalyze = async () => {
    const parsed = parseStockCodesInput(stockCode);
    if (parsed.message) {
      setInputError(parsed.message);
      return;
    }

    setInputError(undefined);
    setDuplicateError(null);
    setBatchInfo(null);
    setIsAnalyzing(true);
    setLoading(true);
    setStoreError(null);

    // 记录当前请求的 ID
    const currentRequestId = ++analysisRequestIdRef.current;

    try {
      await submitAnalyzeCodesInBatches(parsed.codes);

      // 清空输入框
      if (currentRequestId === analysisRequestIdRef.current) {
        setStockCode('');
      }
    } catch (err) {
      console.error('Analysis failed:', err);
      if (currentRequestId === analysisRequestIdRef.current) {
        if (err instanceof DuplicateTaskError) {
          // 显示重复任务错误
          setDuplicateError(`股票 ${err.stockCode} 正在分析中，请等待完成`);
        } else {
          setStoreError(err instanceof Error ? err.message : '分析失败');
        }
      }
    } finally {
      setIsAnalyzing(false);
      setLoading(false);
    }
  };

  const handleSaveTradeProfile = async () => {
    const parsed = parseStockCodesInput(stockCode);
    if (parsed.message || parsed.codes.length !== 1) {
      setInputError(parsed.message || '保存交易信息时请只输入一个股票代码');
      return;
    }
    const code = parsed.codes[0];

    const toNumber = (v: string): number | undefined => {
      const x = v.trim();
      if (!x) return undefined;
      const num = Number(x);
      return Number.isFinite(num) ? num : undefined;
    };

    try {
      const profile = await portfolioApi.upsert({
        stockCode: code,
        status: profileStatus,
        isFavorite: profileFavorite,
        buyPrice: toNumber(buyPriceInput),
        positionPct: toNumber(positionPctInput),
        shares: toNumber(sharesInput),
        targetBuyPrice: toNumber(targetBuyInput),
        targetSellPrice: toNumber(targetSellInput),
        stopLossPrice: toNumber(stopLossInput),
        notes: notesInput.trim() || undefined,
      });
      setBatchInfo(`已保存 ${profile.stockCode} 的交易信息`);
      await fetchPortfolioProfiles();
    } catch (err) {
      console.error('Save portfolio profile failed:', err);
      setStoreError(err instanceof Error ? err.message : '保存交易信息失败');
    }
  };

  const handleQuickAnalyzeFromWatchlist = async (code: string) => {
    setStockCode(code);
    setDuplicateError(null);
    setInputError(undefined);
    setIsAnalyzing(true);
    setLoading(true);
    try {
      await submitAnalyzeCodesInBatches([code]);
    } catch (err) {
      if (err instanceof DuplicateTaskError) {
        setDuplicateError(`股票 ${err.stockCode} 正在分析中，请等待完成`);
      } else {
        setStoreError(err instanceof Error ? err.message : '分析失败');
      }
    } finally {
      setIsAnalyzing(false);
      setLoading(false);
    }
  };

  // 回车提交
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && stockCode && !isAnalyzing) {
      handleAnalyze();
    }
  };

  const filteredProfiles = profiles.filter((item) => {
    if (profileFilter === 'favorite') return item.isFavorite;
    if (profileFilter === 'all') return true;
    return item.status === profileFilter;
  });
  const parsedForSave = parseStockCodesInput(stockCode);
  const canSaveTradeProfile = !parsedForSave.message && parsedForSave.codes.length === 1;
  const singleSaveCode = canSaveTradeProfile ? parsedForSave.codes[0] : '';

  useEffect(() => {
    if (!singleSaveCode) return;
    const profile = profiles.find((p) => p.stockCode === singleSaveCode);
    if (profile) {
      fillTradeFormFromProfile(profile);
    }
  }, [fillTradeFormFromProfile, profiles, singleSaveCode]);

  const handleDeleteProfile = async (code: string) => {
    const ok = window.confirm(`确认删除 ${code} 的交易档案？`);
    if (!ok) return;
    try {
      await portfolioApi.remove(code);
      setBatchInfo(`已删除 ${code} 的交易档案`);
      await fetchPortfolioProfiles();
      if (stockCode.trim().toUpperCase() === code) {
        setBuyPriceInput('');
        setPositionPctInput('');
        setSharesInput('');
        setTargetBuyInput('');
        setTargetSellInput('');
        setStopLossInput('');
        setNotesInput('');
      }
    } catch (err) {
      console.error('Delete portfolio profile failed:', err);
      setStoreError(err instanceof Error ? err.message : '删除交易信息失败');
    }
  };

  const sidebarContent = (
    <div className="flex flex-col gap-3 overflow-hidden min-h-0 h-full">
      <WatchlistPanel
        items={filteredProfiles}
        isLoading={isLoadingProfiles}
        filter={profileFilter}
        onFilterChange={setProfileFilter}
        onUseCode={(code) => {
          setStockCode(code);
          const profile = profiles.find((p) => p.stockCode === code);
          fillTradeFormFromProfile(profile);
        }}
        onAnalyze={(code) => { handleQuickAnalyzeFromWatchlist(code); setSidebarOpen(false); }}
        onDelete={(code) => { handleDeleteProfile(code); }}
      />
      <TaskPanel tasks={activeTasks} />
      <HistoryList
        items={historyItems}
        isLoading={isLoadingHistory}
        isLoadingMore={isLoadingMore}
        hasMore={hasMore}
        selectedId={selectedReport?.meta.id}
        onItemClick={(id) => { handleHistoryClick(id); setSidebarOpen(false); }}
        onLoadMore={handleLoadMore}
        className="max-h-[62vh] md:max-h-[62vh] flex-1 overflow-hidden"
      />
    </div>
  );

  return (
    <div
      className="min-h-screen flex flex-col md:grid overflow-hidden w-full"
      style={{ gridTemplateColumns: 'minmax(12px, 1fr) 256px 24px minmax(auto, 896px) minmax(12px, 1fr)', gridTemplateRows: 'auto 1fr' }}
    >
      {/* 顶部输入栏 */}
      <header
        className="md:col-start-2 md:col-end-5 md:row-start-1 py-3 px-3 md:px-0 border-b border-white/5 flex-shrink-0 min-w-0 overflow-hidden"
      >
        <div className="w-full min-w-0 space-y-2" style={{ maxWidth: 'min(100%, 1168px)' }}>
          <div className="flex items-center gap-2 w-full min-w-0">
            {/* Mobile hamburger */}
            <button
              onClick={() => setSidebarOpen(true)}
              className="md:hidden p-1.5 -ml-1 rounded-lg hover:bg-white/10 transition-colors text-secondary hover:text-white flex-shrink-0"
              title="历史记录"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <div className="flex-1 min-w-0">
              <input
                type="text"
                value={stockCode}
                onChange={(e) => {
                  setStockCode(e.target.value.toUpperCase());
                  setInputError(undefined);
                }}
                onKeyDown={handleKeyDown}
                placeholder="输入股票代码，支持批量：600519, 00700, AAPL"
                disabled={isAnalyzing}
                className={`input-terminal w-full ${inputError ? 'border-danger/50' : ''}`}
              />
            </div>
            <button
              type="button"
              onClick={handleAnalyze}
              disabled={!stockCode || isAnalyzing}
              className="btn-primary h-10 px-4 flex items-center gap-1.5 whitespace-nowrap flex-shrink-0"
            >
              {isAnalyzing ? (
                <>
                  <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  分析中
                </>
              ) : (
                '分析'
              )}
            </button>
          </div>

          {(inputError || duplicateError || batchInfo) && (
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
              {inputError && <p className="text-danger">{inputError}</p>}
              {duplicateError && <p className="text-warning">{duplicateError}</p>}
              {batchInfo && <p className="text-cyan">{batchInfo}</p>}
            </div>
          )}

          <div className="glass-card p-2.5">
            <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-1.5 text-xs">
              <input value={buyPriceInput} onChange={(e) => setBuyPriceInput(e.target.value)} placeholder="买入价" className="input-terminal py-1.5 px-2" />
              <input value={positionPctInput} onChange={(e) => setPositionPctInput(e.target.value)} placeholder="仓位%" className="input-terminal py-1.5 px-2" />
              <input value={sharesInput} onChange={(e) => setSharesInput(e.target.value)} placeholder="持仓股数" className="input-terminal py-1.5 px-2" />
              <input value={targetBuyInput} onChange={(e) => setTargetBuyInput(e.target.value)} placeholder="目标入场" className="input-terminal py-1.5 px-2" />
              <input value={targetSellInput} onChange={(e) => setTargetSellInput(e.target.value)} placeholder="目标止盈" className="input-terminal py-1.5 px-2" />
              <input value={stopLossInput} onChange={(e) => setStopLossInput(e.target.value)} placeholder="止损价" className="input-terminal py-1.5 px-2" />
              <select
                value={profileStatus}
                onChange={(e) => setProfileStatus(e.target.value as PortfolioStatus)}
                className="input-terminal py-1.5 px-2"
              >
                <option value="holding">持仓</option>
                <option value="watch">观望</option>
                <option value="candidate">候选</option>
                <option value="archived">归档</option>
              </select>
              <label className="input-terminal py-1.5 px-2 inline-flex items-center justify-between gap-2 text-muted cursor-pointer">
                <span>收藏</span>
                <input
                  type="checkbox"
                  checked={profileFavorite}
                  onChange={(e) => setProfileFavorite(e.target.checked)}
                />
              </label>
              <textarea
                value={notesInput}
                onChange={(e) => setNotesInput(e.target.value)}
                placeholder="备注（可选）"
                rows={2}
                className="input-terminal py-1.5 px-2 col-span-2 md:col-span-4 xl:col-span-5 resize-none"
              />
              <div className="col-span-2 md:col-span-4 xl:col-span-3 flex flex-wrap items-center gap-1.5 justify-start xl:justify-end">
                <label className="text-muted text-[11px]">每批</label>
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={batchSize}
                  onChange={(e) => setBatchSize(clampBatchSize(Number(e.target.value)))}
                  className="input-terminal py-1.5 px-2 w-16"
                  title="每批数量"
                />
                <label className="text-muted text-[11px]">间隔ms</label>
                <input
                  type="number"
                  min={0}
                  max={5000}
                  value={batchDelayMs}
                  onChange={(e) => setBatchDelayMs(clampBatchDelayMs(Number(e.target.value)))}
                  className="input-terminal py-1.5 px-2 w-20"
                  title="批次间隔ms"
                />
                <button
                  type="button"
                  onClick={handleSaveTradeProfile}
                  className="btn-primary py-1.5 px-3 whitespace-nowrap"
                  disabled={isAnalyzing || !canSaveTradeProfile}
                >
                  保存交易信息
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Desktop sidebar */}
      <div className="hidden md:flex col-start-2 row-start-2 flex-col gap-3 overflow-hidden min-h-0">
        {sidebarContent}
      </div>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 md:hidden" onClick={() => setSidebarOpen(false)}>
          <div className="absolute inset-0 bg-black/60" />
          <div
            className="absolute left-0 top-0 bottom-0 w-72 flex flex-col glass-card overflow-hidden border-r border-white/10 shadow-2xl p-3"
            onClick={(e) => e.stopPropagation()}
          >
            {sidebarContent}
          </div>
        </div>
      )}

      {/* 右侧报告详情 */}
      <section className="md:col-start-4 md:row-start-2 flex-1 overflow-y-auto overflow-x-auto px-3 md:px-0 md:pl-1 min-w-0 min-h-0">
        {isLoadingReport ? (
          <div className="flex flex-col items-center justify-center h-full">
            <div className="w-10 h-10 border-3 border-cyan/20 border-t-cyan rounded-full animate-spin" />
            <p className="mt-3 text-secondary text-sm">加载报告中...</p>
          </div>
        ) : selectedReport ? (
          <div className="max-w-4xl">
            {/* Follow-up button */}
            <div className="flex items-center justify-end mb-2">
              <button
                disabled={selectedReport.meta.id === undefined}
                onClick={() => {
                  const code = selectedReport.meta.stockCode;
                  const name = selectedReport.meta.stockName;
                  const rid = selectedReport.meta.id!;
                  navigate(`/chat?stock=${encodeURIComponent(code)}&name=${encodeURIComponent(name)}&recordId=${rid}`);
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan/10 border border-cyan/20 text-cyan text-sm hover:bg-cyan/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
                追问 AI
              </button>
            </div>
            <ReportSummary data={selectedReport} isHistory />
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-12 h-12 mb-3 rounded-xl bg-elevated flex items-center justify-center">
              <svg className="w-6 h-6 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
            <h3 className="text-base font-medium text-white mb-1.5">开始分析</h3>
            <p className="text-xs text-muted max-w-xs">
              输入股票代码进行分析，或从左侧选择历史报告查看
            </p>
          </div>
        )}
      </section>
    </div>
  );
};

export default HomePage;
