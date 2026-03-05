# -*- coding: utf-8 -*-
"""
===================================
市场发现接口
===================================

GET /api/v1/market/discover
1. 获取今日热门行业与龙头股
2. 自动触发一次 simple 分析任务
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query

from api.v1.schemas.common import ErrorResponse, SuccessResponse
from api.v1.schemas.market import MarketDiscoverResponse, MarketLeader, SectorDiscoverItem
from data_provider.base import canonical_stock_code
from src.storage import get_db
from src.services.task_queue import DuplicateTaskError, get_task_queue

logger = logging.getLogger(__name__)

router = APIRouter()

# Cache TTL defaults to 20 minutes.
_MARKET_DISCOVER_CACHE_TTL_SECONDS = int(os.getenv("MARKET_DISCOVER_CACHE_TTL_SECONDS", "1200"))
_MIN_MARKET_CAP_BILLION = float(os.getenv("MARKET_DISCOVER_MIN_MARKET_CAP_BILLION", "30"))
_CACHE_LOCK = threading.Lock()
_DISCOVER_CACHE: Dict[Tuple[int, int, Optional[int]], Dict[str, Any]] = {}


_MOCK_HOT_SECTORS: List[Dict[str, Any]] = [
    {
        "sector_name": "人工智能",
        "change_pct": 1.8,
        "leaders": [
            {"stock_code": "300308", "stock_name": "中际旭创", "change_pct": 2.4},
            {"stock_code": "002230", "stock_name": "科大讯飞", "change_pct": 1.6},
            {"stock_code": "688111", "stock_name": "金山办公", "change_pct": 1.3},
        ],
    },
    {
        "sector_name": "半导体",
        "change_pct": 1.5,
        "leaders": [
            {"stock_code": "688981", "stock_name": "中芯国际", "change_pct": 2.0},
            {"stock_code": "603986", "stock_name": "兆易创新", "change_pct": 1.4},
            {"stock_code": "300474", "stock_name": "景嘉微", "change_pct": 1.1},
        ],
    },
    {
        "sector_name": "高股息",
        "change_pct": 0.9,
        "leaders": [
            {"stock_code": "600941", "stock_name": "中国移动", "change_pct": 0.8},
            {"stock_code": "601398", "stock_name": "工商银行", "change_pct": 0.5},
            {"stock_code": "600900", "stock_name": "长江电力", "change_pct": 0.6},
        ],
    },
]


def _get_col(row: Dict[str, Any], names: List[str]) -> Any:
    for n in names:
        if n in row and row[n] is not None:
            return row[n]
    return None


def _to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


def _to_market_cap_billion(v: Any) -> Optional[float]:
    """Normalize market cap into billion CNY (亿元)."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        num = float(v)
    else:
        s = str(v).strip().replace(",", "")
        if not s:
            return None
        # Handle textual units from data sources.
        if "万亿" in s:
            m = re.search(r"[-+]?\d*\.?\d+", s)
            return float(m.group()) * 10000 if m else None
        if "亿" in s:
            m = re.search(r"[-+]?\d*\.?\d+", s)
            return float(m.group()) if m else None
        m = re.search(r"[-+]?\d*\.?\d+", s)
        if not m:
            return None
        num = float(m.group())

    # Heuristic:
    # - very large numbers are likely yuan -> convert to 亿元
    # - small numbers are likely already in 亿元
    if num >= 1e8:
        return num / 1e8
    return num


def _build_mock_hot_sectors(top_n: int, leaders_per_sector: int) -> List[Dict[str, Any]]:
    take_n = max(2, leaders_per_sector)
    sectors = []
    for sec in _MOCK_HOT_SECTORS[:top_n]:
        sectors.append({
            "sector_name": sec["sector_name"],
            "change_pct": sec["change_pct"],
            "leaders": sec["leaders"][:take_n],
        })
    return sectors


def _cache_key(
    top_n: int,
    leaders_per_sector: int,
    min_score: Optional[int],
    sector_keyword: Optional[str],
    min_change_pct: Optional[float],
) -> Tuple[int, int, Optional[int], str, Optional[float]]:
    return top_n, leaders_per_sector, min_score, (sector_keyword or "").strip().lower(), min_change_pct


def _get_cached_discover_result(key: Tuple[int, int, Optional[int]], ttl_seconds: int) -> Optional[Dict[str, Any]]:
    now = time.time()
    with _CACHE_LOCK:
        item = _DISCOVER_CACHE.get(key)
        if not item:
            return None
        age_seconds = int(now - item["ts"])
        if age_seconds > ttl_seconds:
            _DISCOVER_CACHE.pop(key, None)
            return None
        # Return shallow copy to avoid accidental mutation.
        return {
            "source": item["source"],
            "sectors": [dict(x) for x in item["sectors"]],
            "analysis_triggered": bool(item.get("analysis_triggered", False)),
            "cache_age_seconds": age_seconds,
        }


def _set_cached_discover_result(
    key: Tuple[int, int, Optional[int]],
    source: str,
    sectors: List[Dict[str, Any]],
    analysis_triggered: bool = False,
) -> None:
    with _CACHE_LOCK:
        _DISCOVER_CACHE[key] = {
            "ts": time.time(),
            "source": source,
            "sectors": [dict(x) for x in sectors],
            "analysis_triggered": analysis_triggered,
        }


def _mark_cached_analysis_triggered(key: Tuple[int, int, Optional[int]]) -> None:
    with _CACHE_LOCK:
        item = _DISCOVER_CACHE.get(key)
        if item:
            item["analysis_triggered"] = True


def _clear_discover_cache() -> int:
    with _CACHE_LOCK:
        count = len(_DISCOVER_CACHE)
        _DISCOVER_CACHE.clear()
    return count


def _discover_hot_sectors(top_n: int, leaders_per_sector: int) -> Tuple[str, List[Dict[str, Any]]]:
    """
    使用 Akshare 获取热门行业与龙头股。
    返回 (source, sectors)
    """
    import pandas as pd  # noqa: F401
    import akshare as ak

    # 临时禁用代理，防止 Akshare 访问国内接口失败 (如常见的 ProxyError)
    old_http_proxy = os.environ.get("http_proxy")
    old_https_proxy = os.environ.get("https_proxy")
    if old_http_proxy: os.environ["http_proxy"] = ""
    if old_https_proxy: os.environ["https_proxy"] = ""

    try:
        source = "akshare_em"
        board_df = None
        
        # 尝试多源获取板块排行
        try:
            board_df = ak.stock_board_industry_name_em()
        except Exception as e:
            logger.warning("Akshare 东财板块排行接口失败: %s, 尝试新浪接口...", e)
            try:
                board_df = ak.stock_sector_spot(indicator="新浪行业")
                source = "akshare_sina"
            except Exception as e2:
                logger.error("Akshare 新浪板块排行接口也失败: %s", e2)

        if board_df is None or board_df.empty:
            return source, []

        # 统一字段名识别
        name_col = None
        for col in ["板块名称", "名称", "板块", "label", "name"]:
            if col in board_df.columns:
                name_col = col
                break
        
        change_col = None
        for col in ["涨跌幅", "涨跌", "change_pct", "百分比", "涨幅"]:
            if col in board_df.columns:
                change_col = col
                break

        if not name_col or not change_col:
            logger.error("无法识别板块接口列名: %s", board_df.columns.tolist())
            return source, []

        board_df[change_col] = pd.to_numeric(board_df[change_col], errors='coerce')
        board_df = board_df.dropna(subset=[change_col])
        board_df = board_df.sort_values(change_col, ascending=False).head(top_n)

        sectors: List[Dict[str, Any]] = []
        for _, row in board_df.iterrows():
            sector_name = str(row.get(name_col) or "").strip()
            if not sector_name:
                continue

            leaders: List[Dict[str, Any]] = []
            # 尝试获取龙头
            try:
                cons_df = None
                if source == "akshare_em":
                    cons_df = ak.stock_board_industry_cons_em(symbol=sector_name)
                else:
                    cons_df = ak.stock_sector_detail(sector=sector_name)
                
                if cons_df is not None and not cons_df.empty:
                    cand_df = cons_df.copy()

                    leader_name_col = None
                    for c in ["名称", "股票名称", "name"]:
                        if c in cand_df.columns:
                            leader_name_col = c
                            break
                    if leader_name_col:
                        # 排除 ST/*ST
                        cand_df = cand_df[~cand_df[leader_name_col].astype(str).str.contains(r"(?:\*?ST)", regex=True, na=False)]

                    change_col = None
                    for c in ["涨跌幅", "涨跌", "change_pct", "涨幅"]:
                        if c in cand_df.columns:
                            change_col = c
                            break
                    volume_col = None
                    for c in ["成交量", "volume", "成交量(手)", "量比成交量"]:
                        if c in cand_df.columns:
                            volume_col = c
                            break
                    turnover_col = None
                    for c in ["换手率", "turnover_rate", "换手", "换手率(%)"]:
                        if c in cand_df.columns:
                            turnover_col = c
                            break
                    market_cap_col = None
                    for c in ["总市值", "total_mv", "总市值(元)", "流通市值"]:
                        if c in cand_df.columns:
                            market_cap_col = c
                            break

                    cand_df["__change"] = pd.to_numeric(cand_df[change_col], errors="coerce") if change_col else None
                    cand_df["__volume"] = pd.to_numeric(cand_df[volume_col], errors="coerce") if volume_col else None
                    cand_df["__turnover"] = pd.to_numeric(cand_df[turnover_col], errors="coerce") if turnover_col else None
                    if market_cap_col:
                        cand_df["__market_cap_b"] = cand_df[market_cap_col].apply(_to_market_cap_billion)
                        # 市值可用时，过滤掉 30 亿以下微盘股
                        cand_df = cand_df[
                            cand_df["__market_cap_b"].isna() | (cand_df["__market_cap_b"] >= _MIN_MARKET_CAP_BILLION)
                        ]

                    # 若存在换手率，优先保留前 50% 活跃票；否则尝试市值前 50%
                    take_n = max(2, leaders_per_sector)
                    original_candidates = cand_df.copy()
                    turnover_series = cand_df.get("__turnover")
                    if turnover_series is not None and turnover_series.notna().sum() >= take_n:
                        threshold = turnover_series.dropna().quantile(0.5)
                        cand_df = cand_df[cand_df["__turnover"] >= threshold]
                    else:
                        cap_series = cand_df.get("__market_cap_b")
                        if cap_series is not None and cap_series.notna().sum() >= take_n:
                            threshold = cap_series.dropna().quantile(0.5)
                            cand_df = cand_df[cand_df["__market_cap_b"] >= threshold]

                    if len(cand_df) < take_n:
                        cand_df = original_candidates

                    sort_cols: List[str] = []
                    ascending: List[bool] = []
                    if "__volume" in cand_df.columns:
                        sort_cols.append("__volume")
                        ascending.append(False)
                    if "__turnover" in cand_df.columns:
                        sort_cols.append("__turnover")
                        ascending.append(False)
                    if "__change" in cand_df.columns:
                        sort_cols.append("__change")
                        ascending.append(False)
                    if sort_cols:
                        cand_df = cand_df.sort_values(sort_cols, ascending=ascending, na_position="last")

                    cand_df = cand_df.head(take_n)
                    for _, r in cand_df.iterrows():
                        r_dict = r.to_dict()
                        code_raw = _get_col(r_dict, ["代码", "股票代码", "symbol", "code"])
                        name = _get_col(r_dict, ["名称", "股票名称", "name", leader_name_col or ""])
                        if not code_raw:
                            continue
                        code = canonical_stock_code(str(code_raw))
                        leaders.append({
                            "stock_code": code,
                            "stock_name": str(name) if name else None,
                            "change_pct": _to_float(_get_col(r_dict, ["涨跌幅", "change_pct", "涨幅"])),
                        })
            except Exception as e:
                logger.warning("获取板块成分失败 %s: %s", sector_name, e)

            sectors.append({
                "sector_name": sector_name,
                "change_pct": _to_float(row.get(change_col)),
                "leaders": leaders,
            })

        return source, sectors
    finally:
        # 还原代理设置
        if old_http_proxy is not None: os.environ["http_proxy"] = old_http_proxy
        if old_https_proxy is not None: os.environ["https_proxy"] = old_https_proxy


def run_market_discover_scan(
    top_n: int,
    leaders_per_sector: int,
    trigger_analysis: bool,
    use_cache: bool = True,
    min_score: Optional[int] = None,
    sector_keyword: Optional[str] = None,
    min_change_pct: Optional[float] = None,
) -> MarketDiscoverResponse:
    """Core discover+trigger logic for API and scheduler reuse."""
    cache_key = _cache_key(top_n, leaders_per_sector, min_score, sector_keyword, min_change_pct)
    source = "akshare_em"
    sectors_raw: List[Dict[str, Any]] = []
    analysis_triggered_on_cache = False
    cache_hit = False
    cache_age_seconds: Optional[int] = None

    if use_cache:
        cached = _get_cached_discover_result(cache_key, _MARKET_DISCOVER_CACHE_TTL_SECONDS)
        if cached:
            source = cached["source"]
            sectors_raw = cached["sectors"]
            analysis_triggered_on_cache = bool(cached["analysis_triggered"])
            cache_hit = True
            cache_age_seconds = cached.get("cache_age_seconds")
            logger.debug("Market discover cache hit: top_n=%s leaders=%s", top_n, leaders_per_sector)

    if not sectors_raw:
        try:
            source, sectors_raw = _discover_hot_sectors(top_n=top_n, leaders_per_sector=leaders_per_sector)
        except Exception as e:
            logger.warning("市场扫描上游数据源失败，启用 mock 兜底: %s", e)
            source, sectors_raw = "mock_fallback", []

        if not sectors_raw:
            source = "mock_fallback"
            sectors_raw = _build_mock_hot_sectors(top_n=top_n, leaders_per_sector=leaders_per_sector)
        elif not any(sec.get("leaders") for sec in sectors_raw):
            logger.warning("市场扫描结果仅有板块无龙头，启用 mock 龙头兜底")
            source = "mock_fallback"
            sectors_raw = _build_mock_hot_sectors(top_n=top_n, leaders_per_sector=leaders_per_sector)
        if use_cache:
            _set_cached_discover_result(cache_key, source, sectors_raw, analysis_triggered=False)

    # Optional sector filters.
    if sector_keyword:
        kw = sector_keyword.strip().lower()
        if kw:
            sectors_raw = [sec for sec in sectors_raw if kw in str(sec.get("sector_name", "")).lower()]
    if min_change_pct is not None:
        sectors_raw = [
            sec for sec in sectors_raw
            if (sec.get("change_pct") is not None and float(sec.get("change_pct")) >= float(min_change_pct))
        ]

    # Optional high-score filter from latest analysis history.
    if min_score is not None:
        all_codes = []
        for sec in sectors_raw:
            for leader in sec.get("leaders", []):
                code = str(leader.get("stock_code") or "").strip().upper()
                if code:
                    all_codes.append(code)
        latest_scores = get_db().get_latest_sentiment_scores(all_codes, days=30) if all_codes else {}
        if latest_scores:
            original_sectors = sectors_raw
            filtered: List[Dict[str, Any]] = []
            for sec in sectors_raw:
                leaders = []
                for leader in sec.get("leaders", []):
                    code = str(leader.get("stock_code") or "").strip().upper()
                    score = latest_scores.get(code, {}).get("sentiment_score")
                    if score is None or score < min_score:
                        continue
                    leader_new = dict(leader)
                    leader_new["latest_score"] = score
                    leaders.append(leader_new)
                if leaders:
                    sec_new = dict(sec)
                    sec_new["leaders"] = leaders
                    filtered.append(sec_new)
            if filtered:
                sectors_raw = filtered
            else:
                logger.info("min_score=%s 过滤后为空，保留原始异动结果避免空白页", min_score)
                sectors_raw = original_sectors
        else:
            logger.info("min_score=%s 已启用，但历史评分为空，暂不执行过滤", min_score)

    task_queue = get_task_queue()
    triggered_tasks = 0
    duplicate_tasks = 0

    should_trigger_analysis = trigger_analysis and (not use_cache or not analysis_triggered_on_cache)
    sectors: List[SectorDiscoverItem] = []
    for sec in sectors_raw:
        leaders: List[MarketLeader] = []
        for leader in sec.get("leaders", []):
            task_id: Optional[str] = None
            if should_trigger_analysis:
                try:
                    task = task_queue.submit_task(
                        stock_code=leader["stock_code"],
                        stock_name=leader.get("stock_name"),
                        report_type="simple",
                        force_refresh=False,
                    )
                    task_id = task.task_id
                    triggered_tasks += 1
                except DuplicateTaskError:
                    duplicate_tasks += 1
                except Exception as e:
                    logger.warning("自动触发 simple 分析失败 %s: %s", leader.get("stock_code"), e)

            leaders.append(MarketLeader(
                stock_code=leader["stock_code"],
                stock_name=leader.get("stock_name"),
                change_pct=leader.get("change_pct"),
                latest_score=leader.get("latest_score"),
                task_id=task_id,
            ))

        sectors.append(SectorDiscoverItem(
            sector_name=sec.get("sector_name", ""),
            change_pct=sec.get("change_pct"),
            leaders=leaders,
        ))

    if should_trigger_analysis and use_cache:
        _mark_cached_analysis_triggered(cache_key)

    return MarketDiscoverResponse(
        source=source,
        total_sectors=len(sectors),
        triggered_tasks=triggered_tasks,
        duplicate_tasks=duplicate_tasks,
        sectors=sectors,
        cache_hit=cache_hit,
        cache_age_seconds=cache_age_seconds,
        cache_ttl_seconds=_MARKET_DISCOVER_CACHE_TTL_SECONDS,
    )


@router.get(
    "/discover",
    response_model=MarketDiscoverResponse,
    responses={500: {"model": ErrorResponse}},
    summary="发现今日热门行业与龙头并触发 simple 分析",
)
def discover_market(
    top_n: int = Query(5, ge=1, le=20, description="行业数量"),
    leaders_per_sector: int = Query(2, ge=1, le=10, description="每个行业的龙头数量"),
    trigger_analysis: bool = Query(True, description="是否自动触发 simple 分析"),
    min_score: Optional[int] = Query(70, ge=0, le=100, description="最低历史评分过滤阈值"),
    sector_keyword: Optional[str] = Query(None, description="板块关键词过滤"),
    min_change_pct: Optional[float] = Query(None, description="板块最小涨跌幅过滤"),
) -> MarketDiscoverResponse:
    try:
        return run_market_discover_scan(
            top_n=top_n,
            leaders_per_sector=leaders_per_sector,
            trigger_analysis=trigger_analysis,
            use_cache=True,
            min_score=min_score,
            sector_keyword=sector_keyword,
            min_change_pct=min_change_pct,
        )
    except HTTPException:
        raise
    except Exception as e:
        # Final guard rail: return mock fallback instead of 500 to keep UI stable.
        logger.error("市场发现失败（最终兜底）: %s", e, exc_info=True)
        return MarketDiscoverResponse(
            source="mock_fallback",
            total_sectors=3,
            triggered_tasks=0,
            duplicate_tasks=0,
            cache_hit=False,
            cache_age_seconds=None,
            cache_ttl_seconds=_MARKET_DISCOVER_CACHE_TTL_SECONDS,
            sectors=[
                SectorDiscoverItem(
                    sector_name=x["sector_name"],
                    change_pct=x["change_pct"],
                    leaders=[MarketLeader(**leader) for leader in x["leaders"][:2]],
                )
                for x in _MOCK_HOT_SECTORS
            ],
        )


@router.post(
    "/discover/cache/invalidate",
    response_model=SuccessResponse,
    summary="清空市场发现缓存",
)
def invalidate_discover_cache() -> SuccessResponse:
    removed = _clear_discover_cache()
    return SuccessResponse(
        success=True,
        message="market discover cache invalidated",
        data={"removed_entries": removed, "ttl_seconds": _MARKET_DISCOVER_CACHE_TTL_SECONDS},
    )
