export interface MarketLeader {
  stockCode: string;
  stockName?: string;
  changePct?: number;
  taskId?: string;
}

export interface SectorDiscoverItem {
  sectorName: string;
  changePct?: number;
  leaders: MarketLeader[];
}

export interface MarketDiscoverResponse {
  source: string;
  totalSectors: number;
  triggeredTasks: number;
  duplicateTasks: number;
  sectors: SectorDiscoverItem[];
}
