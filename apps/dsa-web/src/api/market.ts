import apiClient from './index';
import { toCamelCase } from './utils';
import type { MarketDiscoverResponse } from '../types/market';

export const marketApi = {
  discover: async (params?: {
    topN?: number;
    leadersPerSector?: number;
    triggerAnalysis?: boolean;
  }): Promise<MarketDiscoverResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/market/discover', {
      params: {
        top_n: params?.topN ?? 5,
        leaders_per_sector: params?.leadersPerSector ?? 2,
        trigger_analysis: params?.triggerAnalysis ?? true,
      },
    });
    return toCamelCase<MarketDiscoverResponse>(response.data);
  },
};
