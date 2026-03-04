# -*- coding: utf-8 -*-
"""Tests for action_history injection into analyzer prompt."""

import unittest

from src.analyzer import GeminiAnalyzer


class AnalyzerActionHistoryPromptTestCase(unittest.TestCase):
    def test_format_prompt_contains_action_history(self) -> None:
        analyzer = GeminiAnalyzer()
        context = {
            "code": "600519",
            "stock_name": "贵州茅台",
            "date": "2026-03-03",
            "today": {"close": 1700, "open": 1680, "high": 1712, "low": 1675, "pct_chg": 1.2, "volume": 123456},
            "trader_profile": {
                "status": "holding",
                "position_pct": 35,
                "current_position": 35,
                "buy_price": 1660,
                "total_investment": 500000,
                "action_history": [
                    "2026-03-01: 1660 买入 100 股",
                    "2026-03-02: 1710 卖出 50 股",
                ],
            },
        }
        prompt = analyzer._format_prompt(context=context, name="贵州茅台", news_context=None)
        self.assertIn("最近操作记录", prompt)
        self.assertIn("当前持仓(current_position)", prompt)
        self.assertIn("2026-03-01: 1660 买入 100 股", prompt)
        self.assertIn("必须考虑“最近操作记录”", prompt)


if __name__ == "__main__":
    unittest.main()
