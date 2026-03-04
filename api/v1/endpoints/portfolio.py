# -*- coding: utf-8 -*-
"""
===================================
自选与交易档案接口
===================================
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_database_manager
from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.portfolio import (
    PortfolioProfile,
    PortfolioProfileListResponse,
    PortfolioProfileUpsertRequest,
)
from data_provider.base import canonical_stock_code
from src.storage import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter()

VALID_STATUS = {"holding", "watch", "candidate", "archived"}


@router.get(
    "/profiles",
    response_model=PortfolioProfileListResponse,
    responses={500: {"model": ErrorResponse}},
    summary="获取交易档案列表",
)
def list_profiles(
    status: Optional[str] = Query(None, description="状态筛选: holding/watch/candidate/archived"),
    favorite_only: bool = Query(False, description="仅收藏"),
    keyword: Optional[str] = Query(None, description="关键词（股票代码/名称）"),
    limit: int = Query(200, ge=1, le=1000),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> PortfolioProfileListResponse:
    if status and status not in VALID_STATUS:
        raise HTTPException(status_code=400, detail={"error": "validation_error", "message": "无效 status"})

    try:
        items = db_manager.list_portfolio_profiles(
            status=status,
            favorite_only=favorite_only,
            keyword=keyword,
            limit=limit,
        )
        return PortfolioProfileListResponse(total=len(items), items=[PortfolioProfile(**x) for x in items])
    except Exception as e:
        logger.error("查询交易档案失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": "查询交易档案失败"})


@router.get(
    "/profiles/{stock_code}",
    response_model=PortfolioProfile,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="获取单只股票交易档案",
)
def get_profile(
    stock_code: str,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> PortfolioProfile:
    code = canonical_stock_code(stock_code)
    try:
        profile = db_manager.get_portfolio_profile(code)
        if profile is None:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": f"{code} 尚未建立档案"})
        return PortfolioProfile(**profile)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取交易档案失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": "获取交易档案失败"})


@router.put(
    "/profiles/{stock_code}",
    response_model=PortfolioProfile,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="创建/更新交易档案",
)
def upsert_profile(
    stock_code: str,
    request: PortfolioProfileUpsertRequest,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> PortfolioProfile:
    code_path = canonical_stock_code(stock_code)
    code_body = canonical_stock_code(request.stock_code)

    if code_path != code_body:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": "path stock_code 与请求体 stock_code 不一致"},
        )

    try:
        data = db_manager.upsert_portfolio_profile(
            stock_code=code_body,
            stock_name=request.stock_name,
            status=request.status,
            is_favorite=request.is_favorite,
            buy_price=request.buy_price,
            position_pct=request.position_pct,
            shares=request.shares,
            total_investment=request.total_investment,
            target_buy_price=request.target_buy_price,
            target_sell_price=request.target_sell_price,
            stop_loss_price=request.stop_loss_price,
            tags=request.tags,
            action_history=request.action_history,
            notes=request.notes,
        )
        return PortfolioProfile(**data)
    except Exception as e:
        logger.error("保存交易档案失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": "保存交易档案失败"})


@router.delete(
    "/profiles/{stock_code}",
    responses={200: {"description": "删除成功"}, 404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="删除交易档案",
)
def delete_profile(
    stock_code: str,
    db_manager: DatabaseManager = Depends(get_database_manager),
):
    code = canonical_stock_code(stock_code)
    try:
        ok = db_manager.delete_portfolio_profile(code)
        if not ok:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": f"{code} 不存在"})
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("删除交易档案失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": "删除交易档案失败"})
