# -*- coding: utf-8 -*-
"""
Data tools — wraps DataFetcherManager methods as agent-callable tools.

Tools:
- get_realtime_quote: real-time stock quote
- get_daily_history: historical OHLCV data
- get_chip_distribution: chip distribution analysis
- get_analysis_context: historical analysis context from DB
"""

import json
import logging
from typing import Optional, Dict, Any, List

from src.agent.tools.registry import ToolParameter, ToolDefinition

logger = logging.getLogger(__name__)


def _get_fetcher_manager():
    """Lazy import to avoid circular deps."""
    from data_provider import DataFetcherManager
    return DataFetcherManager()


def _get_db():
    """Lazy import for DatabaseManager."""
    from src.storage import get_db
    return get_db()


# ============================================================
# get_realtime_quote
# ============================================================

def _handle_get_realtime_quote(stock_code: str) -> dict:
    """Get real-time stock quote."""
    manager = _get_fetcher_manager()
    quote = manager.get_realtime_quote(stock_code)
    if quote is None:
        return {"error": f"No realtime quote available for {stock_code}"}

    return {
        "code": quote.code,
        "name": quote.name,
        "price": quote.price,
        "change_pct": quote.change_pct,
        "change_amount": quote.change_amount,
        "volume": quote.volume,
        "amount": quote.amount,
        "volume_ratio": quote.volume_ratio,
        "turnover_rate": quote.turnover_rate,
        "amplitude": quote.amplitude,
        "open": quote.open_price,
        "high": quote.high,
        "low": quote.low,
        "pre_close": quote.pre_close,
        "pe_ratio": quote.pe_ratio,
        "pb_ratio": quote.pb_ratio,
        "total_mv": quote.total_mv,
        "circ_mv": quote.circ_mv,
        "change_60d": quote.change_60d,
        "source": quote.source.value if hasattr(quote.source, 'value') else str(quote.source),
    }


get_realtime_quote_tool = ToolDefinition(
    name="get_realtime_quote",
    description="Get real-time stock quote including price, change%, volume ratio, "
                "turnover rate, PE, PB, market cap. Returns live market data.",
    parameters=[
        ToolParameter(
            name="stock_code",
            type="string",
            description="Stock code, e.g., '600519' (A-share), 'AAPL' (US), 'hk00700' (HK)",
        ),
    ],
    handler=_handle_get_realtime_quote,
    category="data",
)


# ============================================================
# get_daily_history
# ============================================================

def _handle_get_daily_history(stock_code: str, days: int = 60) -> dict:
    """Get daily OHLCV history data."""
    manager = _get_fetcher_manager()
    df, source = manager.get_daily_data(stock_code, days=days)

    if df is None or df.empty:
        return {"error": f"No historical data available for {stock_code}"}

    # Convert DataFrame to list of dicts (last N records)
    records = df.tail(min(days, len(df))).to_dict(orient="records")
    # Ensure date is string
    for r in records:
        if "date" in r:
            r["date"] = str(r["date"])

    return {
        "code": stock_code,
        "source": source,
        "total_records": len(records),
        "data": records,
    }


get_daily_history_tool = ToolDefinition(
    name="get_daily_history",
    description="Get daily OHLCV (open, high, low, close, volume) historical data "
                "with MA5/MA10/MA20 indicators. Returns the last N trading days.",
    parameters=[
        ToolParameter(
            name="stock_code",
            type="string",
            description="Stock code, e.g., '600519' (A-share), 'AAPL' (US)",
        ),
        ToolParameter(
            name="days",
            type="integer",
            description="Number of trading days to fetch (default: 60)",
            required=False,
            default=60,
        ),
    ],
    handler=_handle_get_daily_history,
    category="data",
)


# ============================================================
# get_chip_distribution
# ============================================================

def _handle_get_chip_distribution(stock_code: str) -> dict:
    """Get chip distribution data."""
    manager = _get_fetcher_manager()
    chip = manager.get_chip_distribution(stock_code)

    if chip is None:
        return {"error": f"No chip distribution data available for {stock_code}"}

    return {
        "code": chip.code,
        "date": chip.date,
        "source": chip.source,
        "profit_ratio": chip.profit_ratio,
        "avg_cost": chip.avg_cost,
        "cost_90_low": chip.cost_90_low,
        "cost_90_high": chip.cost_90_high,
        "concentration_90": chip.concentration_90,
        "cost_70_low": chip.cost_70_low,
        "cost_70_high": chip.cost_70_high,
        "concentration_70": chip.concentration_70,
    }


get_chip_distribution_tool = ToolDefinition(
    name="get_chip_distribution",
    description="Get chip distribution analysis for a stock. Returns profit ratio, "
                "average cost, chip concentration at 90% and 70% levels. "
                "Useful for judging support/resistance and holding structure.",
    parameters=[
        ToolParameter(
            name="stock_code",
            type="string",
            description="A-share stock code, e.g., '600519'",
        ),
    ],
    handler=_handle_get_chip_distribution,
    category="data",
)


# ============================================================
# get_analysis_context
# ============================================================

def _handle_get_analysis_context(stock_code: str) -> dict:
    """Get stored analysis context from database."""
    db = _get_db()
    context = db.get_analysis_context(stock_code)

    if context is None:
        return {"error": f"No analysis context in DB for {stock_code}"}

    # Return safely serializable version (remove raw_data to save tokens)
    safe_context = {}
    for k, v in context.items():
        if k == "raw_data":
            safe_context["has_raw_data"] = True
            safe_context["raw_data_count"] = len(v) if isinstance(v, list) else 0
        else:
            safe_context[k] = v

    return safe_context


get_analysis_context_tool = ToolDefinition(
    name="get_analysis_context",
    description="Get historical analysis context from the database for a stock. "
                "Returns today's and yesterday's OHLCV data, MA alignment status, "
                "volume and price changes. Provides the technical data foundation.",
    parameters=[
        ToolParameter(
            name="stock_code",
            type="string",
            description="Stock code, e.g., '600519'",
        ),
    ],
    handler=_handle_get_analysis_context,
    category="data",
)


# ============================================================
# get_stock_info
# ============================================================

def _handle_get_stock_info(stock_code: str) -> dict:
    """Get stock fundamental information including industry, financials, and valuation."""
    # Try EfinanceFetcher.get_base_info first (most complete)
    try:
        from data_provider.efinance_fetcher import EfinanceFetcher
        fetcher = EfinanceFetcher()
        info = fetcher.get_base_info(stock_code)
        if info:
            # Sanitise: convert non-serialisable types and remove NaN
            import math
            clean: dict = {}
            for k, v in info.items():
                if isinstance(v, float) and math.isnan(v):
                    clean[k] = None
                else:
                    try:
                        import json as _json
                        _json.dumps(v)       # test serialisability
                        clean[k] = v
                    except (TypeError, ValueError):
                        clean[k] = str(v)

            # Also try to get board/sector membership
            try:
                board_df = fetcher.get_belong_board(stock_code)
                if board_df is not None and not board_df.empty:
                    # Typically columns: 板块名称, 板块代码, 涨跌幅, …
                    boards = board_df.to_dict(orient="records")
                    # Keep only name + change columns to limit token usage
                    clean["belong_boards"] = [
                        {k2: (str(v2) if not isinstance(v2, (int, float, str, type(None))) else v2)
                         for k2, v2 in row.items()
                         if any(kw in str(k2) for kw in ["名称", "代码", "涨跌", "板块"])}
                        for row in boards[:10]
                    ]
            except Exception:
                pass

            return clean
    except Exception as e:
        logger.warning(f"get_stock_info via EfinanceFetcher failed for {stock_code}: {e}")

    # Fallback: derive from realtime quote (valuation metrics only)
    manager = _get_fetcher_manager()
    quote = manager.get_realtime_quote(stock_code)
    if quote:
        return {
            "code": quote.code,
            "name": quote.name,
            "pe_ratio": quote.pe_ratio,
            "pb_ratio": quote.pb_ratio,
            "total_mv": quote.total_mv,
            "circ_mv": quote.circ_mv,
            "note": "Basic info only — EfinanceFetcher unavailable",
        }
    return {"error": f"Unable to fetch stock info for {stock_code}"}


get_stock_info_tool = ToolDefinition(
    name="get_stock_info",
    description="Get stock fundamental information: industry classification, ROE, net profit margin, "
                "PE ratio, PB ratio, revenue, earnings, market cap, and sector membership. "
                "Best for fundamental analysis and background research on a stock.",
    parameters=[
        ToolParameter(
            name="stock_code",
            type="string",
            description="A-share stock code, e.g., '600519'",
        ),
    ],
    handler=_handle_get_stock_info,
    category="data",
)


# ============================================================
# portfolio_review
# ============================================================

def _compute_fear_greed_score(indices: List[Dict[str, Any]], market_stats: Dict[str, Any]) -> int:
    """
    Heuristic fear-greed score (0-100), higher means greed/risk-on.
    """
    change_values = []
    for item in indices or []:
        try:
            val = item.get("change_pct")
            if val is not None:
                change_values.append(float(val))
        except Exception:
            continue
    avg_change = sum(change_values) / len(change_values) if change_values else 0.0
    # map -3%..+3% to 0..100
    score_from_change = int(max(0, min(100, (avg_change + 3.0) / 6.0 * 100)))

    breadth_score = 50
    try:
        up_count = float(market_stats.get("up_count", 0) or 0)
        down_count = float(market_stats.get("down_count", 0) or 0)
        total = up_count + down_count
        if total > 0:
            breadth_score = int(max(0, min(100, up_count / total * 100)))
    except Exception:
        breadth_score = 50

    return int(round(score_from_change * 0.6 + breadth_score * 0.4))


def _fear_greed_label(score: int) -> str:
    if score >= 75:
        return "贪婪"
    if score >= 60:
        return "偏乐观"
    if score >= 40:
        return "中性"
    if score >= 25:
        return "偏谨慎"
    return "恐慌"


def _handle_portfolio_review(available_cash: float = 0.0, min_score: int = 70) -> dict:
    """
    Review holding portfolio and provide position/buy-list suggestions.
    """
    db = _get_db()
    manager = _get_fetcher_manager()

    profiles = db.list_portfolio_profiles(status="holding", limit=500)
    if not profiles:
        return {
            "available_cash": float(available_cash or 0.0),
            "holdings_count": 0,
            "message": "当前无 holding 持仓，建议先从高分异动板块里筛选 1-2 只试仓。",
            "risk_diversification": {
                "industry_concentration": "无持仓",
                "top_industry_exposure_pct": 0,
                "assessment": "无集中风险",
            },
            "position_recommendation": {
                "market_fear_greed": {"score": 50, "label": "中性"},
                "total_position_pct": 0,
                "assessment": "空仓",
                "suggested_range_pct": "20-40",
            },
            "bullet_plan": {"buy_list": []},
        }

    codes = [str(p.get("stock_code") or "").upper() for p in profiles if p.get("stock_code")]
    latest_scores = db.get_latest_sentiment_scores(codes, days=30)

    # Build industry concentration map
    industry_weights: Dict[str, float] = {}
    holding_rows: List[Dict[str, Any]] = []
    total_position_pct = 0.0

    for p in profiles:
        code = str(p.get("stock_code") or "").upper()
        position_pct = float(p.get("position_pct") or 0.0)
        total_position_pct += position_pct

        industry = "未知行业"
        try:
            info = _handle_get_stock_info(code)
            for k in ("行业", "所属行业", "industry", "行业板块"):
                if info.get(k):
                    industry = str(info.get(k))
                    break
        except Exception:
            pass

        industry_weights[industry] = industry_weights.get(industry, 0.0) + position_pct
        score_info = latest_scores.get(code, {})
        holding_rows.append({
            "stock_code": code,
            "stock_name": p.get("stock_name"),
            "buy_price": p.get("buy_price"),
            "position_pct": position_pct,
            "shares": p.get("shares"),
            "latest_score": score_info.get("sentiment_score"),
            "latest_advice": score_info.get("operation_advice"),
        })

    top_industry = max(industry_weights.items(), key=lambda x: x[1]) if industry_weights else ("未知行业", 0.0)
    top_industry_name, top_industry_exposure = top_industry
    concentration_assessment = "分散良好"
    if top_industry_exposure >= 45:
        concentration_assessment = "行业集中偏高，建议降低单行业暴露"
    elif top_industry_exposure >= 30:
        concentration_assessment = "行业有一定集中，建议新增非同板块标的对冲"

    # Market regime from indices + breadth
    indices = manager.get_main_indices(region="cn") or []
    market_stats = manager.get_market_stats() or {}
    fear_greed_score = _compute_fear_greed_score(indices, market_stats)
    fear_greed = {"score": fear_greed_score, "label": _fear_greed_label(fear_greed_score)}

    suggested_range = "50-70"
    if fear_greed_score >= 70:
        suggested_range = "65-85"
    elif fear_greed_score <= 35:
        suggested_range = "30-50"

    position_assessment = "仓位健康"
    if total_position_pct > 85:
        position_assessment = "总仓位偏高，优先做减仓与结构优化"
    elif total_position_pct < 35:
        position_assessment = "总仓位偏低，可分批提高仓位"

    # Bullet plan: prefer high-score leaders from market discover
    buy_list: List[Dict[str, Any]] = []
    try:
        from api.v1.endpoints.market import run_market_discover_scan
        discover = run_market_discover_scan(
            top_n=5,
            leaders_per_sector=3,
            trigger_analysis=False,
            use_cache=True,
            min_score=min_score,
        )
        for sec in discover.sectors:
            for leader in sec.leaders:
                buy_list.append({
                    "sector_name": sec.sector_name,
                    "stock_code": leader.stock_code,
                    "stock_name": leader.stock_name,
                    "latest_score": leader.latest_score,
                    "reason": f"异动板块龙头 + 最近评分>= {min_score}",
                })
    except Exception as e:
        logger.warning("portfolio_review 获取异动高分清单失败: %s", e)

    return {
        "available_cash": float(available_cash or 0.0),
        "holdings_count": len(holding_rows),
        "holdings": holding_rows,
        "risk_diversification": {
            "industry_concentration": top_industry_name,
            "top_industry_exposure_pct": round(float(top_industry_exposure), 2),
            "assessment": concentration_assessment,
        },
        "position_recommendation": {
            "market_fear_greed": fear_greed,
            "total_position_pct": round(float(total_position_pct), 2),
            "assessment": position_assessment,
            "suggested_range_pct": suggested_range,
        },
        "bullet_plan": {
            "buy_list": buy_list[:8],
            "available_cash_usage_hint": (
                "建议先用 30%-40% 现金分两笔试仓，再根据次日量价反馈追加。"
                if float(available_cash or 0) > 0 else
                "未提供可用现金，建议先确认可动用子弹后再执行买入清单。"
            ),
        },
    }


portfolio_review_tool = ToolDefinition(
    name="portfolio_review",
    description="Review current holding portfolio from DB. Returns concentration risk, total position "
                "health, market fear-greed context and prioritized buy-list from high-score hot sectors.",
    parameters=[
        ToolParameter(
            name="available_cash",
            type="number",
            description="Available cash amount in CNY for building bullet buy plan.",
            required=False,
            default=0.0,
        ),
        ToolParameter(
            name="min_score",
            type="integer",
            description="Minimum latest sentiment score when selecting hot-sector buy candidates.",
            required=False,
            default=70,
        ),
    ],
    handler=_handle_portfolio_review,
    category="data",
)


# ============================================================
# Export all data tools
# ============================================================

ALL_DATA_TOOLS = [
    get_realtime_quote_tool,
    get_daily_history_tool,
    get_chip_distribution_tool,
    get_analysis_context_tool,
    get_stock_info_tool,
    portfolio_review_tool,
]
