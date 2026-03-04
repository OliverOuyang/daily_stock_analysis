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
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query

from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.market import MarketDiscoverResponse, MarketLeader, SectorDiscoverItem
from data_provider.base import canonical_stock_code
from src.services.task_queue import DuplicateTaskError, get_task_queue

logger = logging.getLogger(__name__)

router = APIRouter()


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


def _discover_hot_sectors(top_n: int, leaders_per_sector: int) -> Tuple[str, List[Dict[str, Any]]]:
    """
    使用 Akshare 获取热门行业与龙头股。
    返回 (source, sectors)
    sectors: [{sector_name, change_pct, leaders:[{stock_code, stock_name, change_pct}]}]
    """
    import pandas as pd  # noqa: F401
    import akshare as ak

    board_df = ak.stock_board_industry_name_em()
    if board_df is None or board_df.empty:
        return "akshare", []

    change_col = "涨跌幅" if "涨跌幅" in board_df.columns else None
    if change_col is None:
        return "akshare", []

    board_df[change_col] = board_df[change_col].astype(float)
    board_df = board_df.sort_values(change_col, ascending=False).head(top_n)

    sectors: List[Dict[str, Any]] = []
    for _, row in board_df.iterrows():
        sector_name = str(row.get("板块名称") or row.get("名称") or "").strip()
        if not sector_name:
            continue

        leaders: List[Dict[str, Any]] = []
        try:
            cons_df = ak.stock_board_industry_cons_em(symbol=sector_name)
            if cons_df is not None and not cons_df.empty:
                cand_df = cons_df.copy()
                leader_change_col = "涨跌幅" if "涨跌幅" in cand_df.columns else None
                if leader_change_col:
                    cand_df[leader_change_col] = cand_df[leader_change_col].astype(float)
                    cand_df = cand_df.sort_values(leader_change_col, ascending=False)
                cand_df = cand_df.head(leaders_per_sector)

                for _, r in cand_df.iterrows():
                    r_dict = r.to_dict()
                    code_raw = _get_col(r_dict, ["代码", "股票代码", "symbol"])
                    name = _get_col(r_dict, ["名称", "股票名称", "name"])
                    if not code_raw:
                        continue
                    code = canonical_stock_code(str(code_raw))
                    leaders.append({
                        "stock_code": code,
                        "stock_name": str(name) if name else None,
                        "change_pct": _to_float(_get_col(r_dict, ["涨跌幅", "change_pct"])),
                    })
        except Exception as e:
            logger.warning("获取板块成分失败 %s: %s", sector_name, e)

        sectors.append({
            "sector_name": sector_name,
            "change_pct": _to_float(row.get(change_col)),
            "leaders": leaders,
        })

    return "akshare", sectors


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
) -> MarketDiscoverResponse:
    try:
        source, sectors_raw = _discover_hot_sectors(top_n=top_n, leaders_per_sector=leaders_per_sector)
        task_queue = get_task_queue()
        triggered_tasks = 0
        duplicate_tasks = 0

        sectors: List[SectorDiscoverItem] = []
        for sec in sectors_raw:
            leaders: List[MarketLeader] = []
            for leader in sec.get("leaders", []):
                task_id: Optional[str] = None
                if trigger_analysis:
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
                    task_id=task_id,
                ))

            sectors.append(SectorDiscoverItem(
                sector_name=sec.get("sector_name", ""),
                change_pct=sec.get("change_pct"),
                leaders=leaders,
            ))

        return MarketDiscoverResponse(
            source=source,
            total_sectors=len(sectors),
            triggered_tasks=triggered_tasks,
            duplicate_tasks=duplicate_tasks,
            sectors=sectors,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("市场发现失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": "市场发现失败"})

