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
