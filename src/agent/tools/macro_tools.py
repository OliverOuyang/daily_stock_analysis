# -*- coding: utf-8 -*-
"""
Macro tools — provides market-level data including macro indicators and money flow.
"""

import logging
from typing import Optional, Dict, Any, List

from src.agent.tools.registry import ToolParameter, ToolDefinition
from data_provider.macro_fetcher import MacroFetcher

logger = logging.getLogger(__name__)

def _get_macro_fetcher():
    """Lazy initialization."""
    return MacroFetcher()

# ============================================================
# get_market_climate
# ============================================================

def _handle_get_market_climate() -> dict:
    """Get overall market macro and liquidity context."""
    fetcher = _get_macro_fetcher()
    return fetcher.get_market_climate()

get_market_climate_tool = ToolDefinition(
    name="get_market_climate",
    description="Get overall A-share market climate: 10Y Bond Yield, USD/CNH exchange rate, "
                "Shibor Overnight, and total market turnover. Use this to understand the "
                "macro background and liquidity environment.",
    parameters=[],
    handler=_handle_get_market_climate,
    category="data",
)

# ============================================================
# get_money_flow
# ============================================================

def _handle_get_money_flow(stock_code: Optional[str] = None, days: int = 5) -> dict:
    """Get northbound and stock-specific money flow."""
    fetcher = _get_macro_fetcher()
    return fetcher.get_money_flow(stock_code=stock_code, days=days)

get_money_flow_tool = ToolDefinition(
    name="get_money_flow",
    description="Get money flow data including Northbound (HSGT) net flow and stock-specific flow. "
                "Helps identify if 'Smart Money' is entering or exiting.",
    parameters=[
        ToolParameter(
            name="stock_code",
            type="string",
            description="Stock code (optional), e.g., '600519'",
            required=False,
        ),
        ToolParameter(
            name="days",
            type="integer",
            description="Lookback days for trend (default: 5)",
            required=False,
            default=5,
        ),
    ],
    handler=_handle_get_money_flow,
    category="data",
)

# ============================================================
# get_lhb_insight
# ============================================================

def _handle_get_lhb_insight(stock_code: str) -> dict:
    """Get Dragon-Tiger List (LHB) details for a stock."""
    fetcher = _get_macro_fetcher()
    lhb_data = fetcher.get_lhb_insight(stock_code)
    return {
        "stock_code": stock_code,
        "count": len(lhb_data),
        "data": lhb_data[:10]  # Limit to save tokens
    }

get_lhb_insight_tool = ToolDefinition(
    name="get_lhb_insight",
    description="Get Dragon-Tiger List (LHB) for a specific stock. Identifies big players, "
                "institutional seats, and famous retail hot-money (游资) activity.",
    parameters=[
        ToolParameter(
            name="stock_code",
            type="string",
            description="Stock code, e.g., '600519'",
        ),
    ],
    handler=_handle_get_lhb_insight,
    category="data",
)

# ============================================================
# Export all macro tools
# ============================================================

ALL_MACRO_TOOLS = [
    get_market_climate_tool,
    get_money_flow_tool,
    get_lhb_insight_tool,
]
