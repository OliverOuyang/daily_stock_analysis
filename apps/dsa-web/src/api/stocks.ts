import apiClient from './index';
import { toCamelCase } from './utils';

export type ExtractFromImageResponse = {
  codes: string[];
  rawText?: string;
};

export interface StockQuote {
  stockCode: string;
  stockName?: string;
  currentPrice: number;
  change?: number;
  changePercent?: number;
  open?: number;
  high?: number;
  low?: number;
  prevClose?: number;
  volume?: number;
  amount?: number;
  updateTime?: string;
}

export interface StockQuotesResponse {
  items: StockQuote[];
}

export const stocksApi = {
  async extractFromImage(file: File): Promise<ExtractFromImageResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const headers: { [key: string]: string | undefined } = { 'Content-Type': undefined };
    const response = await apiClient.post(
      '/api/v1/stocks/extract-from-image',
      formData,
      {
        headers,
        timeout: 60000, // Vision API can be slow; 60s
      },
    );

    const data = response.data as { codes?: string[]; raw_text?: string };
    return {
      codes: data.codes ?? [],
      rawText: data.raw_text,
    };
  },

  async getBatchQuotes(codes: string[]): Promise<StockQuotesResponse> {
    if (codes.length === 0) return { items: [] };
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/stocks/quotes', {
      params: { codes: codes.join(',') },
    });
    return toCamelCase<StockQuotesResponse>(response.data);
  },
};
