# -*- coding: utf-8 -*-
"""
===================================
自选与交易档案 Schema
===================================
"""

from typing import List, Optional, Literal

from pydantic import BaseModel, Field


PortfolioStatus = Literal["holding", "watch", "candidate", "archived"]


class PortfolioProfileUpsertRequest(BaseModel):
    stock_code: str = Field(..., description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    status: PortfolioStatus = Field("watch", description="状态")
    is_favorite: bool = Field(False, description="是否收藏关注")

    buy_price: Optional[float] = Field(None, ge=0, description="买入价")
    position_pct: Optional[float] = Field(None, ge=0, le=100, description="仓位百分比")
    shares: Optional[float] = Field(None, ge=0, description="持仓股数")
    target_buy_price: Optional[float] = Field(None, ge=0, description="目标入场价")
    target_sell_price: Optional[float] = Field(None, ge=0, description="目标止盈价")
    stop_loss_price: Optional[float] = Field(None, ge=0, description="止损价")

    tags: List[str] = Field(default_factory=list, description="标签列表")
    notes: Optional[str] = Field(None, description="备注")


class PortfolioProfile(BaseModel):
    id: int
    stock_code: str
    stock_name: Optional[str] = None
    status: PortfolioStatus
    is_favorite: bool = False

    buy_price: Optional[float] = None
    position_pct: Optional[float] = None
    shares: Optional[float] = None
    target_buy_price: Optional[float] = None
    target_sell_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None

    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PortfolioProfileListResponse(BaseModel):
    total: int
    items: List[PortfolioProfile]

