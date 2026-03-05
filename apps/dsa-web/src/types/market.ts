export interface MarketLeader {
  stockCode: string;
  stockName?: string;
  changePct?: number;
  latestScore?: number;
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
  cacheHit?: boolean;
  cacheAgeSeconds?: number;
  cacheTtlSeconds?: number;
}

export interface MarketPrescoreStartResponse {
  runId: string;
  totalTasks: number;
  triggeredTasks: number;
  duplicateTasks: number;
  status: 'pending' | 'running' | 'completed';
}

export interface MarketPrescoreStatusResponse {
  runId: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  totalTasks: number;
  completedTasks: number;
  failedTasks: number;
  diagnostics?: string;
  result?: MarketDiscoverResponse;
}
