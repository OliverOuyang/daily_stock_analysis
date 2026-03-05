# -*- coding: utf-8 -*-
"""Tests for structured position action extraction."""

import unittest

from src.analyzer import GeminiAnalyzer


class AnalyzerPositionActionsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = GeminiAnalyzer()

    def test_holding_context_applies_default_ratios_when_missing(self) -> None:
        data = {
            "position_actions": {
                "reduce_price": 35.0,
                "add_price": 30.0,
                "basis": "前高压力 + MA20 回踩",
            }
        }
        context = {"trader_profile": {"status": "holding"}}

        parsed = self.analyzer._extract_position_actions(data, dashboard=None, context=context)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["reduce_price"], 35.0)
        self.assertEqual(parsed["add_price"], 30.0)
        self.assertEqual(parsed["reduce_ratio_pct"], 50.0)
        self.assertEqual(parsed["add_ratio_pct"], 20.0)
        self.assertTrue(parsed["is_fallback"])
        self.assertEqual(parsed["completeness"], "defaulted")

    def test_text_rule_extracts_prices_and_ratios(self) -> None:
        data = {
            "operation_advice": "突破35元建议减仓半仓，回踩30元建议补仓2成。",
            "analysis_summary": "以分批执行为主。",
        }

        parsed = self.analyzer._extract_position_actions(data, dashboard=None, context=None)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["reduce_price"], 35.0)
        self.assertEqual(parsed["add_price"], 30.0)
        self.assertEqual(parsed["reduce_ratio_pct"], 50.0)
        self.assertEqual(parsed["add_ratio_pct"], 20.0)
        self.assertEqual(parsed["extraction_source"], "text_rule")
        self.assertEqual(parsed["completeness"], "complete")
        self.assertFalse(parsed["is_fallback"])

    def test_non_holding_without_actions_returns_none(self) -> None:
        data = {"operation_advice": "观望", "analysis_summary": "等待信号"}
        parsed = self.analyzer._extract_position_actions(data, dashboard=None, context=None)
        self.assertIsNone(parsed)


if __name__ == "__main__":
    unittest.main()

