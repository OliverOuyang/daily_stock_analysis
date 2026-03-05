# -*- coding: utf-8 -*-
"""Tests for StockService.batch_get_realtime_quotes behavior."""

import unittest
from unittest.mock import patch

from src.services.stock_service import StockService


class StockServiceBatchQuotesTestCase(unittest.TestCase):
    def test_batch_quotes_deduplicate_and_keep_order(self) -> None:
        service = StockService()
        calls: list[str] = []

        def _fake_get_quote(code: str):
            calls.append(code)
            return {"stock_code": code, "current_price": 1.0}

        with patch.object(service, "get_realtime_quote", side_effect=_fake_get_quote):
            result = service.batch_get_realtime_quotes(["000933", "000933", "600941"])

        # Deduplicated request calls
        self.assertEqual(calls, ["000933", "600941"])
        # Keep original first-seen order in output
        self.assertEqual([x["stock_code"] for x in result], ["000933", "600941"])


if __name__ == "__main__":
    unittest.main()
