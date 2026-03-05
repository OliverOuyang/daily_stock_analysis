export type PortfolioStatus = 'holding' | 'watch' | 'candidate' | 'archived';

export interface PortfolioProfile {
  id: number;
  stockCode: string;
  stockName?: string;
  status: PortfolioStatus;
  isFavorite: boolean;
  buyPrice?: number;
  positionPct?: number;
  shares?: number;
  totalInvestment?: number;
  targetBuyPrice?: number;
  targetSellPrice?: number;
  stopLossPrice?: number;
  tags: string[];
  actionHistory?: string[];
  notes?: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface PortfolioProfileListResponse {
  total: number;
  items: PortfolioProfile[];
}

export interface PortfolioUpsertRequest {
  stockCode: string;
  stockName?: string;
  status: PortfolioStatus;
  isFavorite: boolean;
  buyPrice?: number;
  positionPct?: number;
  shares?: number;
  totalInvestment?: number;
  targetBuyPrice?: number;
  targetSellPrice?: number;
  stopLossPrice?: number;
  tags?: string[];
  actionHistory?: string[];
  notes?: string;
}

export interface PortfolioReviewResult {
  availableCash: number;
  holdingsCount: number;
  holdings?: Array<{
    stockCode: string;
    stockName?: string;
    positionPct?: number;
    latestScore?: number;
    latestAdvice?: string;
  }>;
  riskDiversification?: {
    industryConcentration?: string;
    topIndustryExposurePct?: number;
    assessment?: string;
  };
  positionRecommendation?: {
    marketFearGreed?: {
      score?: number;
      label?: string;
    };
    totalPositionPct?: number;
    assessment?: string;
    suggestedRangePct?: string;
  };
  bulletPlan?: {
    buyList?: Array<{
      stockCode: string;
      stockName?: string;
      sectorName?: string;
      latestScore?: number;
      reason?: string;
    }>;
    availableCashUsageHint?: string;
  };
  message?: string;
}
