# -*- coding: utf-8 -*-
"""
MacroFetcher - Data source for macro indicators and market sentiment.
Uses Tushare Pro as primary source and Akshare as fallback.
"""

import logging
import os
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
from src.config import get_config

logger = logging.getLogger(__name__)

# Cache for macro indicators to reduce network calls
_MACRO_CACHE: Dict[str, Any] = {
    "data": {},
    "timestamp": 0,
    "ttl": 600  # 10 minutes cache
}

class MacroFetcher:
    """
    Fetcher for macro indicators (Yields, FX, Shibor) and market sentiment (LHB, Limit-up).
    """

    def __init__(self):
        self._api = None
        self._init_tushare()

    def _init_tushare(self):
        config = get_config()
        if config.tushare_token:
            try:
                import tushare as ts
                ts.set_token(config.tushare_token)
                self._api = ts.pro_api()
            except Exception as e:
                logger.error(f"MacroFetcher Tushare init failed: {e}")

    def get_market_climate(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get overall market climate indicators.
        Uses parallel fetching and a 10-minute cache.
        """
        now = time.time()
        if not force_refresh and (now - _MACRO_CACHE["timestamp"] < _MACRO_CACHE["ttl"]):
            if _MACRO_CACHE["data"]:
                logger.debug("[Macro Cache] Using cached market climate data")
                return _MACRO_CACHE["data"]

        res = {
            "yield_10y": None,
            "usd_cnh": None,
            "shibor": None,
            "liquidity": None,
            "turnover": None,
            "market_stats": None,
            "timestamp": datetime.now().isoformat(),
            "partial_data": False
        }

        def fetch_yield():
            try:
                import akshare as ak
                df = ak.bond_zh_us_rate()
                if not df.empty:
                    return float(df.iloc[-1].get('中国国债收益率10年', 0))
            except Exception as e:
                logger.warning(f"Failed to fetch bond yield: {e}")
            return None

        def fetch_fx():
            try:
                import akshare as ak
                df = ak.fx_spot_quote()
                if not df.empty:
                    row = df[df['货币对'] == 'USD/CNY']
                    if not row.empty:
                        return float(row.iloc[0].get('买报价', 0))
            except Exception as e:
                logger.warning(f"Failed to fetch exchange rate: {e}")
            return None

        def fetch_shibor():
            try:
                import akshare as ak
                df = ak.rate_interbank(market="上海银行同业拆借市场", symbol="Shibor人民币", indicator="隔夜")
                if not df.empty:
                    return float(df.iloc[-1].get('利率', 0))
            except Exception as e:
                logger.warning(f"Failed to fetch shibor: {e}")
            return None

        def fetch_turnover():
            try:
                from data_provider import DataFetcherManager
                manager = DataFetcherManager()
                return manager.get_market_stats()
            except Exception as e:
                logger.warning(f"Failed to fetch market stats: {e}")
            return None

        # Execute fetches in parallel
        with ThreadPoolExecutor(max_workers=4) as executor:
            f_yield = executor.submit(fetch_yield)
            f_fx = executor.submit(fetch_fx)
            f_shibor = executor.submit(fetch_shibor)
            f_turnover = executor.submit(fetch_turnover)

            res["yield_10y"] = f_yield.result()
            res["usd_cnh"] = f_fx.result()
            res["shibor"] = f_shibor.result()
            stats = f_turnover.result()
            if stats:
                res["turnover"] = stats.get("total_amount")
                res["market_stats"] = stats

        # Check if we have missing critical fields
        if any(v is None for k, v in res.items() if k in ["yield_10y", "usd_cnh", "turnover"]):
            res["partial_data"] = True
            logger.warning("Market climate data is partially complete.")

        # Update cache
        _MACRO_CACHE["data"] = res
        _MACRO_CACHE["timestamp"] = now
        
        return res

    def get_money_flow(self, stock_code: Optional[str] = None, days: int = 5) -> Dict[str, Any]:
        """
        Get money flow data.
        """
        res = {"northbound_net": None, "stock_flow": None}
        
        # 1. Northbound
        try:
            if self._api:
                # north_money is net flow in million CNY
                df = self._api.moneyflow_hsgt(start_date=(datetime.now() - timedelta(days=days)).strftime('%Y%m%d'))
                if not df.empty:
                    res["northbound_net"] = float(df.iloc[0].get('north_money', 0))
            
            if not res["northbound_net"]:
                import akshare as ak
                df = ak.stock_hsgt_north_net_flow_in_em(symbol="北上")
                if not df.empty:
                    # '当日净流入' column usually
                    res["northbound_net"] = float(df.iloc[-1].get('当日净流入', 0))
        except Exception as e:
            logger.warning(f"Failed to fetch northbound flow: {e}")
            
        return res

    def get_lhb_insight(self, stock_code: str) -> List[Dict[str, Any]]:
        """
        Get Dragon-Tiger List (LHB).
        """
        try:
            import akshare as ak
            # Try to get latest LHB date for this stock
            df_stat = ak.stock_lhb_stock_statistic_em(symbol="近一月")
            if not df_stat.empty:
                # Filter by code
                row = df_stat[df_stat['代码'] == stock_code]
                if not row.empty:
                    # For simplicity, return the summary row
                    return [row.iloc[0].to_dict()]
        except Exception as e:
            logger.warning(f"Failed to fetch LHB insight via akshare: {e}")
        return []

    def get_sentiment_indicators(self) -> Dict[str, Any]:
        """
        Get short-term sentiment indicators.
        """
        return {}
