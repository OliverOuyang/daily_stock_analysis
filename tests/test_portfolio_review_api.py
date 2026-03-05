# -*- coding: utf-8 -*-
"""Tests for portfolio review API."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.auth as auth
from api.app import create_app
from src.config import Config


class PortfolioReviewApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.env_path.write_text(
            "STOCK_LIST=600519\nGEMINI_API_KEY=test\nADMIN_AUTH_ENABLED=false\n",
            encoding="utf-8",
        )
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.data_dir / "test.db")
        Config.reset_instance()

        auth._auth_enabled = None
        self.auth_patcher = patch.object(auth, "_is_auth_enabled_from_env", return_value=False)
        self.auth_patcher.start()

        app = create_app(static_dir=self.data_dir / "empty-static")
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.auth_patcher.stop()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    @patch("src.agent.tools.data_tools._handle_portfolio_review")
    def test_portfolio_review_api(self, mock_review) -> None:
        mock_review.return_value = {
            "available_cash": 20000.0,
            "holdings_count": 1,
            "risk_diversification": {"industry_concentration": "有色", "top_industry_exposure_pct": 50.0},
            "position_recommendation": {"total_position_pct": 60.0, "suggested_range_pct": "50-70"},
            "bullet_plan": {"buy_list": [{"stock_code": "000933", "stock_name": "神火股份"}]},
        }
        resp = self.client.get("/api/v1/portfolio/review?available_cash=20000&min_score=70")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["available_cash"], 20000.0)
        self.assertEqual(data["holdings_count"], 1)
        self.assertEqual(data["bullet_plan"]["buy_list"][0]["stock_code"], "000933")


if __name__ == "__main__":
    unittest.main()
