import apiClient from './index';
import { toCamelCase } from './utils';
import type { MarketDiscoverResponse } from '../types/market';

export const marketApi = {
  discover: async (params?: {
    topN?: number;
    leadersPerSector?: number;
    triggerAnalysis?: boolean;
    minScore?: number;
    sectorKeyword?: string;
    minChangePct?: number;
  }): Promise<MarketDiscoverResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/market/discover', {
      params: {
        top_n: params?.topN ?? 5,
        leaders_per_sector: params?.leadersPerSector ?? 2,
        trigger_analysis: params?.triggerAnalysis ?? true,
        min_score: params?.minScore ?? 70,
        sector_keyword: params?.sectorKeyword,
        min_change_pct: params?.minChangePct,
      },
    });
    return toCamelCase<MarketDiscoverResponse>(response.data);
  },
};
