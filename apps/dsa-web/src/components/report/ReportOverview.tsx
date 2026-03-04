import type React from 'react';
import type {
  ReportMeta,
  ReportSummary as ReportSummaryType,
  ReportStrategy,
} from '../../types/analysis';
import { ScoreGauge, Card } from '../common';
import { formatDateTime } from '../../utils/format';

interface ReportOverviewProps {
  meta: ReportMeta;
  summary: ReportSummaryType;
  strategy?: ReportStrategy;
  isHistory?: boolean;
}

/**
 * 报告概览区组件 - 终端风格
 */
export const ReportOverview: React.FC<ReportOverviewProps> = ({
  meta,
  summary,
  strategy,
}) => {
  const parsePositionActions = (text: string) => {
    const clean = text.replace(/\s+/g, ' ');
    const reduceMatch = clean.match(/(?:减仓|卖出)[^。；\n]*?(\d+(?:\.\d+)?)\s*%?/);
    const addMatch = clean.match(/(?:补仓|加仓)[^。；\n]*?(\d+(?:\.\d+)?)\s*%?/);
    const reduceText = reduceMatch ? `建议减仓/卖出比例: ${reduceMatch[1]}%` : '未提取到明确减仓比例';
    const addText = addMatch ? `建议补仓/加仓比例: ${addMatch[1]}%` : '未提取到明确补仓比例';
    return { reduceText, addText };
  };

  const fallbackPositionActions = parsePositionActions(
    `${summary.operationAdvice || ''}\n${summary.analysisSummary || ''}`,
  );
  const structuredActions = strategy?.positionActions;

  // 根据涨跌幅获取颜色
  const getPriceChangeColor = (changePct: number | undefined): string => {
    if (changePct === undefined || changePct === null) return 'text-muted';
    if (changePct > 0) return 'text-[#ff4d4d]'; // 红涨
    if (changePct < 0) return 'text-[#00d46a]'; // 绿跌
    return 'text-muted';
  };

  // 格式化涨跌幅
  const formatChangePct = (changePct: number | undefined): string => {
    if (changePct === undefined || changePct === null) return '--';
    const sign = changePct > 0 ? '+' : '';
    return `${sign}${changePct.toFixed(2)}%`;
  };

  return (
    <div className="space-y-4">
      {/* 主信息区 - 两列布局，items-stretch 确保右侧与左侧同高 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-stretch">
        {/* 左侧：股票信息与结论 */}
        <div className="lg:col-span-2 space-y-4">
          {/* 股票头部 */}
          <Card variant="gradient" padding="md">
            <div className="flex items-start justify-between mb-4">
              <div className="flex-1">
                <div className="flex items-center gap-3">
                  <h2 className="text-2xl font-bold text-white">
                    {meta.stockName || meta.stockCode}
                  </h2>
                  {/* 价格和涨跌幅 */}
                  {meta.currentPrice != null && (
                    <div className="flex items-baseline gap-2">
                      <span className={`text-xl font-bold font-mono ${getPriceChangeColor(meta.changePct)}`}>
                        {meta.currentPrice.toFixed(2)}
                      </span>
                      <span className={`text-sm font-semibold font-mono ${getPriceChangeColor(meta.changePct)}`}>
                        {formatChangePct(meta.changePct)}
                      </span>
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2 mt-1.5">
                  <span className="font-mono text-xs text-cyan bg-cyan/10 px-1.5 py-0.5 rounded">
                    {meta.stockCode}
                  </span>
                  <span className="text-xs text-muted flex items-center gap-1">
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    {formatDateTime(meta.createdAt)}
                  </span>
                </div>
              </div>
            </div>

            {/* 关键结论 */}
            <div className="border-t border-white/5 pt-4">
              <span className="label-uppercase">KEY INSIGHTS</span>
              <p className="text-white text-sm leading-relaxed mt-1.5 whitespace-pre-wrap text-left">
                {summary.analysisSummary || '暂无分析结论'}
              </p>
            </div>
          </Card>

          {/* 操作建议和趋势预测 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {/* 操作建议 */}
            <Card variant="bordered" padding="sm" hoverable>
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-success/10 flex items-center justify-center flex-shrink-0">
                  <svg className="w-4 h-4 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                  </svg>
                </div>
                <div>
                  <h4 className="text-xs font-medium text-success mb-0.5">操作建议</h4>
                  <p className="text-white text-sm font-medium">
                    {summary.operationAdvice || '暂无建议'}
                  </p>
                </div>
              </div>
            </Card>

            {/* 趋势预测 */}
            <Card variant="bordered" padding="sm" hoverable>
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-warning/10 flex items-center justify-center flex-shrink-0">
                  <svg className="w-4 h-4 text-warning" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                  </svg>
                </div>
                <div>
                  <h4 className="text-xs font-medium text-warning mb-0.5">趋势预测</h4>
                  <p className="text-white text-sm font-medium">
                    {summary.trendPrediction || '暂无预测'}
                  </p>
                </div>
              </div>
            </Card>
          </div>

          <Card variant="bordered" padding="sm">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-cyan/10 flex items-center justify-center flex-shrink-0">
                <svg className="w-4 h-4 text-cyan" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 10h11M9 21V3m12 11h-8m4-4 4 4-4 4" />
                </svg>
              </div>
              <div className="space-y-1">
                <h4 className="text-xs font-medium text-cyan mb-0.5">持仓动作建议（结构化优先）</h4>
                {structuredActions ? (
                  <>
                    <p className="text-[12px] text-white">
                      {structuredActions.reducePrice != null || structuredActions.reduceRatioPct != null
                        ? `减仓: ${structuredActions.reducePrice != null ? `${structuredActions.reducePrice}` : '--'} 元，${structuredActions.reduceRatioPct != null ? `${structuredActions.reduceRatioPct}%` : '--'}`
                        : '减仓: 暂无明确价位/比例'}
                    </p>
                    <p className="text-[12px] text-white">
                      {structuredActions.addPrice != null || structuredActions.addRatioPct != null
                        ? `补仓: ${structuredActions.addPrice != null ? `${structuredActions.addPrice}` : '--'} 元，${structuredActions.addRatioPct != null ? `${structuredActions.addRatioPct}%` : '--'}`
                        : '补仓: 暂无明确价位/比例'}
                    </p>
                    {structuredActions.basis && (
                      <p className="text-[11px] text-secondary">依据: {structuredActions.basis}</p>
                    )}
                  </>
                ) : (
                  <>
                    <p className="text-[12px] text-white">{fallbackPositionActions.reduceText}</p>
                    <p className="text-[12px] text-white">{fallbackPositionActions.addText}</p>
                  </>
                )}
              </div>
            </div>
          </Card>
        </div>

        {/* 右侧：情绪指标 - 填满格子高度，消除与 STRATEGY POINTS 之间的空隙 */}
        <div className="flex flex-col self-stretch min-h-full">
          <Card variant="bordered" padding="md" className="!overflow-visible flex-1 flex flex-col min-h-0">
            <div className="text-center flex-1 flex flex-col justify-center">
              <h3 className="text-sm font-medium text-white mb-4">Market Sentiment</h3>
              <ScoreGauge score={summary.sentimentScore} size="lg" />
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};
