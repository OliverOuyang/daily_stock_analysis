import apiClient from './index';
import { toCamelCase } from './utils';
import type { PortfolioProfile, PortfolioProfileListResponse, PortfolioUpsertRequest } from '../types/portfolio';

export const portfolioApi = {
  list: async (params?: {
    status?: 'holding' | 'watch' | 'candidate' | 'archived';
    favoriteOnly?: boolean;
    keyword?: string;
    limit?: number;
  }): Promise<PortfolioProfileListResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/portfolio/profiles', {
      params: {
        status: params?.status,
        favorite_only: params?.favoriteOnly ?? false,
        keyword: params?.keyword,
        limit: params?.limit ?? 200,
      },
    });
    return toCamelCase<PortfolioProfileListResponse>(response.data);
  },

  upsert: async (payload: PortfolioUpsertRequest): Promise<PortfolioProfile> => {
    const code = payload.stockCode;
    const response = await apiClient.put<Record<string, unknown>>(
      `/api/v1/portfolio/profiles/${encodeURIComponent(code)}`,
      {
        stock_code: payload.stockCode,
        stock_name: payload.stockName,
        status: payload.status,
        is_favorite: payload.isFavorite,
        buy_price: payload.buyPrice,
        position_pct: payload.positionPct,
        shares: payload.shares,
        total_investment: payload.totalInvestment,
        target_buy_price: payload.targetBuyPrice,
        target_sell_price: payload.targetSellPrice,
        stop_loss_price: payload.stopLossPrice,
        tags: payload.tags ?? [],
        action_history: payload.actionHistory,
        notes: payload.notes,
      }
    );
    return toCamelCase<PortfolioProfile>(response.data);
  },

  remove: async (stockCode: string): Promise<void> => {
    await apiClient.delete(`/api/v1/portfolio/profiles/${encodeURIComponent(stockCode)}`);
  },
};
