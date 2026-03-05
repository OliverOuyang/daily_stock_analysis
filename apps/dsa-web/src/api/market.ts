import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  MarketDiscoverResponse,
  MarketPrescoreStartResponse,
  MarketPrescoreStatusResponse,
} from '../types/market';

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

  startPrescore: async (params?: {
    topN?: number;
    leadersPerSector?: number;
    minScore?: number;
    sectorKeyword?: string;
    minChangePct?: number;
  }): Promise<MarketPrescoreStartResponse> => {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/market/discover/prescore/start', null, {
      params: {
        top_n: params?.topN ?? 5,
        leaders_per_sector: params?.leadersPerSector ?? 3,
        min_score: params?.minScore ?? 70,
        sector_keyword: params?.sectorKeyword,
        min_change_pct: params?.minChangePct,
      },
    });
    return toCamelCase<MarketPrescoreStartResponse>(response.data);
  },

  getPrescoreStatus: async (runId: string): Promise<MarketPrescoreStatusResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(`/api/v1/market/discover/prescore/${encodeURIComponent(runId)}`);
    return toCamelCase<MarketPrescoreStatusResponse>(response.data);
  },
};
