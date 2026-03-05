# -*- coding: utf-8 -*-
"""
===================================
股票数据服务层
===================================

职责：
1. 封装股票数据获取逻辑
2. 提供实时行情和历史数据接口
"""

import logging
import re
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from src.repositories.stock_repo import StockRepository

logger = logging.getLogger(__name__)


class StockService:
    """
    股票数据服务
    
    封装股票数据获取的业务逻辑
    """
    
    _FAILOVER_THRESHOLD = 2
    _fallback_lock = threading.Lock()
    _consecutive_failures: Dict[str, int] = {}
    _resolve_cache_lock = threading.Lock()
    _resolve_name_index: Dict[str, str] = {}
    _resolve_cached_at: Optional[datetime] = None
    _RESOLVE_CACHE_TTL_SECONDS = 1800

    def __init__(self):
        """初始化股票数据服务"""
        self.repo = StockRepository()

    @staticmethod
    def _detect_market(stock_code: str) -> str:
        code = (stock_code or "").upper()
        if re.match(r"^\d{6}$", code) or re.match(r"^(SH|SZ)\d{6}$", code):
            return "CN"
        if re.match(r"^\d{5}$", code) or code.startswith("HK"):
            return "HK"
        return "US"

    @classmethod
    def _is_resolve_cache_valid(cls) -> bool:
        if cls._resolve_cached_at is None:
            return False
        return (datetime.now() - cls._resolve_cached_at).total_seconds() <= cls._RESOLVE_CACHE_TTL_SECONDS

    @classmethod
    def _cache_name_index(cls, index: Dict[str, str]) -> None:
        with cls._resolve_cache_lock:
            cls._resolve_name_index = index
            cls._resolve_cached_at = datetime.now()

    @classmethod
    def _get_cached_name_index(cls) -> Optional[Dict[str, str]]:
        with cls._resolve_cache_lock:
            if cls._is_resolve_cache_valid():
                return dict(cls._resolve_name_index)
        return None

    def _build_name_index(self) -> Dict[str, str]:
        cached = self._get_cached_name_index()
        if cached is not None:
            return cached

        index: Dict[str, str] = {}
        try:
            from src.analyzer import STOCK_NAME_MAP

            for code, name in (STOCK_NAME_MAP or {}).items():
                c = str(code or "").strip().upper()
                n = str(name or "").strip()
                if c and n and n != c:
                    index[c] = n
        except Exception:
            pass

        try:
            from data_provider.base import DataFetcherManager

            manager = DataFetcherManager()
            for fetcher in getattr(manager, "_fetchers", []):
                if not hasattr(fetcher, "get_stock_list"):
                    continue
                try:
                    df = fetcher.get_stock_list()
                    if df is None or df.empty:
                        continue

                    for _, row in df.iterrows():
                        code = str(
                            row.get("code")
                            or row.get("代码")
                            or row.get("symbol")
                            or ""
                        ).strip().upper()
                        name = str(
                            row.get("name")
                            or row.get("名称")
                            or row.get("股票名称")
                            or ""
                        ).strip()
                        if code and name and name != code:
                            index[code] = name
                    if len(index) >= 3000:
                        break
                except Exception:
                    continue
        except Exception:
            pass

        self._cache_name_index(index)
        return index

    def resolve_stock_query(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        q = (query or "").strip()
        if not q:
            return []

        normalized_q = q.upper()
        candidates: List[Dict[str, Any]] = []

        # 1) direct code hit
        if re.match(r"^\d{5,6}$", normalized_q) or re.match(r"^[A-Z]{1,6}(\.[A-Z]{1,2})?$", normalized_q):
            try:
                from data_provider.base import DataFetcherManager, canonical_stock_code

                code = canonical_stock_code(normalized_q)
                manager = DataFetcherManager()
                name = manager.get_stock_name(code) or self._build_name_index().get(code)
                candidates.append(
                    {
                        "stock_code": code,
                        "stock_name": name or code,
                        "market": self._detect_market(code),
                        "score": 100,
                    }
                )
                return candidates[:limit]
            except Exception:
                pass

        # 2) fuzzy name/code match from local index
        index = self._build_name_index()
        q_lower = q.lower()
        for code, name in index.items():
            score = 0
            name_lower = name.lower()
            if name == q:
                score = 100
            elif name.startswith(q):
                score = 92
            elif q in name:
                score = 82
            elif code == normalized_q:
                score = 96
            elif code.startswith(normalized_q):
                score = 75
            if score <= 0:
                continue
            candidates.append(
                {
                    "stock_code": code,
                    "stock_name": name,
                    "market": self._detect_market(code),
                    "score": score,
                }
            )

        # 3) ensure deterministic order
        candidates.sort(key=lambda x: (-int(x.get("score") or 0), str(x.get("stock_code") or "")))
        seen = set()
        dedup: List[Dict[str, Any]] = []
        for item in candidates:
            code = item["stock_code"]
            if code in seen:
                continue
            seen.add(code)
            dedup.append(item)
            if len(dedup) >= limit:
                break
        return dedup

    @classmethod
    def _record_fetch_result(cls, stock_code: str, success: bool) -> int:
        with cls._fallback_lock:
            if success:
                cls._consecutive_failures.pop(stock_code, None)
                return 0
            failures = cls._consecutive_failures.get(stock_code, 0) + 1
            cls._consecutive_failures[stock_code] = failures
            return failures

    @classmethod
    def _should_force_fallback(cls, stock_code: str) -> bool:
        with cls._fallback_lock:
            return cls._consecutive_failures.get(stock_code, 0) >= cls._FAILOVER_THRESHOLD

    def _format_quote(self, stock_code: str, quote: Any) -> Dict[str, Any]:
        return {
            "stock_code": getattr(quote, "code", stock_code),
            "stock_name": getattr(quote, "name", None),
            "current_price": getattr(quote, "price", 0.0) or 0.0,
            "change": getattr(quote, "change_amount", None),
            "change_percent": getattr(quote, "change_pct", None),
            "open": getattr(quote, "open_price", None),
            "high": getattr(quote, "high", None),
            "low": getattr(quote, "low", None),
            "prev_close": getattr(quote, "pre_close", None),
            "volume": getattr(quote, "volume", None),
            "amount": getattr(quote, "amount", None),
            "update_time": datetime.now().isoformat(),
        }
    
    def get_realtime_quote(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        获取股票实时行情
        
        Args:
            stock_code: 股票代码
            
        Returns:
            实时行情数据字典
        """
        try:
            from data_provider.base import DataFetcherManager
            from src.config import get_config

            manager = DataFetcherManager()
            quote = manager.get_realtime_quote(stock_code)
            if quote is not None:
                self._record_fetch_result(stock_code, success=True)
                return self._format_quote(stock_code, quote)

            failures = self._record_fetch_result(stock_code, success=False)
            logger.warning("获取 %s 实时行情失败（连续失败=%s）", stock_code, failures)

            # 连续失败后，临时扩展优先级，强制尝试 efinance/akshare_* 切换
            # 通过 try/finally 确保不污染全局配置。
            if self._should_force_fallback(stock_code):
                config = get_config()
                old_priority = getattr(config, "realtime_source_priority", "")
                fallback_chain = "efinance,akshare_em,akshare_sina,tencent,tushare"
                if old_priority:
                    merged = [x.strip() for x in (old_priority + "," + fallback_chain).split(",") if x.strip()]
                    seen = set()
                    merged = [x for x in merged if not (x in seen or seen.add(x))]
                    force_priority = ",".join(merged)
                else:
                    force_priority = fallback_chain

                try:
                    config.realtime_source_priority = force_priority
                    manager = DataFetcherManager()
                    retry_quote = manager.get_realtime_quote(stock_code)
                    if retry_quote is not None:
                        self._record_fetch_result(stock_code, success=True)
                        logger.info("连续失败后切源重试成功: %s", stock_code)
                        return self._format_quote(stock_code, retry_quote)
                finally:
                    config.realtime_source_priority = old_priority

            return None
            
        except ImportError:
            logger.warning("DataFetcherManager 未找到，使用占位数据")
            return self._get_placeholder_quote(stock_code)
        except Exception as e:
            logger.error(f"获取实时行情失败: {e}", exc_info=True)
            return None

    def batch_get_realtime_quotes(self, stock_codes: List[str]) -> List[Dict[str, Any]]:
        """
        批量获取股票实时行情 - 使用多线程并行加速
        """
        import concurrent.futures
        
        results = []
        # 使用线程池并行获取行情，提高自选池刷新速度
        # 限制最大线程数为 10，避免触发 API 频控
        max_workers = min(len(stock_codes), 10) if stock_codes else 1
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_code = {executor.submit(self.get_realtime_quote, code): code for code in stock_codes}
            
            for future in concurrent.futures.as_completed(future_to_code):
                try:
                    quote = future.result()
                    if quote:
                        results.append(quote)
                except Exception as e:
                    code = future_to_code[future]
                    logger.error(f"批量获取 {code} 行情异常: {e}")
                    
        return results
    
    def get_history_data(
        self,
        stock_code: str,
        period: str = "daily",
        days: int = 30
    ) -> Dict[str, Any]:
        """
        获取股票历史行情
        
        Args:
            stock_code: 股票代码
            period: K 线周期 (daily/weekly/monthly)
            days: 获取天数
            
        Returns:
            历史行情数据字典
            
        Raises:
            ValueError: 当 period 不是 daily 时抛出（weekly/monthly 暂未实现）
        """
        # 验证 period 参数，只支持 daily
        if period != "daily":
            raise ValueError(
                f"暂不支持 '{period}' 周期，目前仅支持 'daily'。"
                "weekly/monthly 聚合功能将在后续版本实现。"
            )
        
        try:
            # 调用数据获取器获取历史数据
            from data_provider.base import DataFetcherManager
            
            manager = DataFetcherManager()
            df, source = manager.get_daily_data(stock_code, days=days)
            
            if df is None or df.empty:
                logger.warning(f"获取 {stock_code} 历史数据失败")
                return {"stock_code": stock_code, "period": period, "data": []}
            
            # 获取股票名称
            stock_name = manager.get_stock_name(stock_code)
            
            # 转换为响应格式
            data = []
            for _, row in df.iterrows():
                date_val = row.get("date")
                if hasattr(date_val, "strftime"):
                    date_str = date_val.strftime("%Y-%m-%d")
                else:
                    date_str = str(date_val)
                
                data.append({
                    "date": date_str,
                    "open": float(row.get("open", 0)),
                    "high": float(row.get("high", 0)),
                    "low": float(row.get("low", 0)),
                    "close": float(row.get("close", 0)),
                    "volume": float(row.get("volume", 0)) if row.get("volume") else None,
                    "amount": float(row.get("amount", 0)) if row.get("amount") else None,
                    "change_percent": float(row.get("pct_chg", 0)) if row.get("pct_chg") else None,
                })
            
            return {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "period": period,
                "data": data,
            }
            
        except ImportError:
            logger.warning("DataFetcherManager 未找到，返回空数据")
            return {"stock_code": stock_code, "period": period, "data": []}
        except Exception as e:
            logger.error(f"获取历史数据失败: {e}", exc_info=True)
            return {"stock_code": stock_code, "period": period, "data": []}
    
    def _get_placeholder_quote(self, stock_code: str) -> Dict[str, Any]:
        """
        获取占位行情数据（用于测试）
        
        Args:
            stock_code: 股票代码
            
        Returns:
            占位行情数据
        """
        return {
            "stock_code": stock_code,
            "stock_name": f"股票{stock_code}",
            "current_price": 0.0,
            "change": None,
            "change_percent": None,
            "open": None,
            "high": None,
            "low": None,
            "prev_close": None,
            "volume": None,
            "amount": None,
            "update_time": datetime.now().isoformat(),
        }
