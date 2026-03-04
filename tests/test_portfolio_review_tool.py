# -*- coding: utf-8 -*-
"""Tests for portfolio_review agent tool."""

import unittest
from unittest.mock import MagicMock, patch

from src.agent.tools.data_tools import _handle_portfolio_review


class PortfolioReviewToolTestCase(unittest.TestCase):
    @patch("src.agent.tools.data_tools._handle_get_stock_info")
    @patch("src.agent.tools.data_tools._get_fetcher_manager")
    @patch("src.agent.tools.data_tools._get_db")
    def test_portfolio_review_returns_risk_and_bullet_plan(self, mock_get_db, mock_get_manager, mock_get_info) -> None:
        fake_db = MagicMock()
        fake_db.list_portfolio_profiles.return_value = [
            {
                "stock_code": "000933",
                "stock_name": "神火股份",
                "position_pct": 40,
                "buy_price": 30.2,
                "shares": 1000,
            },
            {
                "stock_code": "600519",
                "stock_name": "贵州茅台",
                "position_pct": 25,
                "buy_price": 1500,
                "shares": 100,
            },
        ]
        fake_db.get_latest_sentiment_scores.return_value = {
            "000933": {"sentiment_score": 77, "operation_advice": "减仓"},
            "600519": {"sentiment_score": 66, "operation_advice": "持有"},
        }
        mock_get_db.return_value = fake_db

        fake_manager = MagicMock()
        fake_manager.get_main_indices.return_value = [
            {"name": "上证指数", "change_pct": 1.2},
            {"name": "深证成指", "change_pct": 0.8},
        ]
        fake_manager.get_market_stats.return_value = {"up_count": 3200, "down_count": 1800}
        mock_get_manager.return_value = fake_manager

        mock_get_info.side_effect = [
            {"行业": "有色金属"},
            {"行业": "白酒"},
        ]

        fake_discover = MagicMock()
        fake_discover.sectors = [
            MagicMock(
                sector_name="有色金属",
                leaders=[MagicMock(stock_code="000933", stock_name="神火股份", latest_score=77)],
            )
        ]

        with patch("api.v1.endpoints.market.run_market_discover_scan", return_value=fake_discover):
            result = _handle_portfolio_review(available_cash=100000, min_score=70)

        self.assertEqual(result["holdings_count"], 2)
        self.assertIn("risk_diversification", result)
        self.assertIn("position_recommendation", result)
        self.assertGreaterEqual(len(result["bullet_plan"]["buy_list"]), 1)
        self.assertEqual(result["bullet_plan"]["buy_list"][0]["stock_code"], "000933")


if __name__ == "__main__":
    unittest.main()

