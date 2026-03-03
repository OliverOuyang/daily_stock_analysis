import { validateStockCode } from '../utils/validation';

export interface ParseStockCodesResult {
  codes: string[];
  message?: string;
}

export const parseStockCodesInput = (rawInput: string): ParseStockCodesResult => {
  const chunks = rawInput
    .split(/[,\s，;；]+/)
    .map((v) => v.trim())
    .filter(Boolean);

  if (chunks.length === 0) {
    return { codes: [], message: '请输入至少一个股票代码' };
  }

  const unique: string[] = [];
  for (const part of chunks) {
    const { valid, message, normalized } = validateStockCode(part);
    if (!valid) {
      return { codes: [], message: `${part}: ${message}` };
    }
    if (!unique.includes(normalized)) {
      unique.push(normalized);
    }
  }

  return { codes: unique };
};

export const clampBatchSize = (value: number): number => Math.max(1, Math.min(20, value));

export const clampBatchDelayMs = (value: number): number => Math.max(0, Math.min(5000, value));

