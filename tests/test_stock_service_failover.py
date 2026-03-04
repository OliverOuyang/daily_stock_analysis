# -*- coding: utf-8 -*-
"""Tests for StockService realtime failover behavior."""

import unittest
from unittest.mock import patch

from src.config import get_config
from src.services.stock_service import StockService


class _FakeQuote:
    def __init__(self, code: str):
        self.code = code
        self.name = "测试股票"
        self.price = 12.34
        self.change_amount = 0.12
        self.change_pct = 0.98
        self.open_price = 12.20
        self.high = 12.50
        self.low = 12.10
        self.pre_close = 12.22
        self.volume = 123456
        self.amount = 12345678.0


class _FakeManager:
    def get_realtime_quote(self, stock_code: str):
        cfg = get_config()
        priority = (cfg.realtime_source_priority or "").lower()
        # Simulate primary source failure and fallback source recovery.
        if "efinance" in priority and "akshare_em" in priority:
            return _FakeQuote(stock_code)
        return None


class StockServiceFailoverTestCase(unittest.TestCase):
    def test_force_fallback_after_consecutive_failures(self) -> None:
        service = StockService()
        cfg = get_config()
        original_priority = cfg.realtime_source_priority
        cfg.realtime_source_priority = "akshare_em"

        try:
            with patch("data_provider.base.DataFetcherManager", return_value=_FakeManager()):
                # first failure: no force fallback yet
                self.assertIsNone(service.get_realtime_quote("000933"))
                # second attempt: force fallback path should kick in and recover
                result = service.get_realtime_quote("000933")
                self.assertIsNotNone(result)
                assert result is not None
                self.assertEqual(result["stock_code"], "000933")
                self.assertEqual(result["stock_name"], "测试股票")
        finally:
            cfg.realtime_source_priority = original_priority


if __name__ == "__main__":
    unittest.main()

