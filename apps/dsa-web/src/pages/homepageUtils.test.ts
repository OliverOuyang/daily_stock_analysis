import { describe, expect, it } from 'vitest';
import { clampBatchDelayMs, clampBatchSize, parseStockCodesInput } from './homepageUtils';

describe('homepageUtils', () => {
  it('parses multiple stock codes and removes duplicates', () => {
    const result = parseStockCodesInput('600519, aapl 00700,600519');
    expect(result.message).toBeUndefined();
    expect(result.codes).toEqual(['600519', 'AAPL', '00700']);
  });

  it('returns validation message when empty', () => {
    const result = parseStockCodesInput('  ');
    expect(result.codes).toEqual([]);
    expect(result.message).toContain('请输入至少一个股票代码');
  });

  it('returns validation message for invalid code', () => {
    const result = parseStockCodesInput('ABCDEF1');
    expect(result.codes).toEqual([]);
    expect(result.message).toContain('股票代码格式不正确');
  });

  it('clamps batch size and delay to supported ranges', () => {
    expect(clampBatchSize(0)).toBe(1);
    expect(clampBatchSize(3)).toBe(3);
    expect(clampBatchSize(99)).toBe(20);

    expect(clampBatchDelayMs(-1)).toBe(0);
    expect(clampBatchDelayMs(800)).toBe(800);
    expect(clampBatchDelayMs(6000)).toBe(5000);
  });
});

