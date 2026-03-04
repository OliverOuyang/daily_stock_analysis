# -*- coding: utf-8 -*-
"""市场发现接口 Schema。"""

from typing import List, Optional

from pydantic import BaseModel, Field


class MarketLeader(BaseModel):
    stock_code: str
    stock_name: Optional[str] = None
    change_pct: Optional[float] = None
    latest_score: Optional[int] = Field(None, description="历史最近一次情绪评分")
    task_id: Optional[str] = Field(None, description="自动触发分析时返回的任务ID")


class SectorDiscoverItem(BaseModel):
    sector_name: str
    change_pct: Optional[float] = None
    leaders: List[MarketLeader]


class MarketDiscoverResponse(BaseModel):
    source: str
    total_sectors: int
    triggered_tasks: int
    duplicate_tasks: int
    sectors: List[SectorDiscoverItem]
