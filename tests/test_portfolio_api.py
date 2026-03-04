# -*- coding: utf-8 -*-
"""Integration tests for portfolio profile API."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.auth as auth
from api.app import create_app
from src.config import Config
from src.storage import DatabaseManager


class PortfolioApiTestCase(unittest.TestCase):
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
        DatabaseManager.reset_instance()

        auth._auth_enabled = None
        self.auth_patcher = patch.object(auth, "_is_auth_enabled_from_env", return_value=False)
        self.auth_patcher.start()

        app = create_app(static_dir=self.data_dir / "empty-static")
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.auth_patcher.stop()
        Config.reset_instance()
        DatabaseManager.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    def test_upsert_and_get_profile(self) -> None:
        response = self.client.put(
            "/api/v1/portfolio/profiles/600519",
            json={
                "stock_code": "600519",
                "stock_name": "贵州茅台",
                "status": "holding",
                "is_favorite": True,
                "buy_price": 1688.5,
                "position_pct": 35,
                "total_investment": 500000,
                "target_buy_price": 1600,
                "target_sell_price": 1888,
                "stop_loss_price": 1550,
                "tags": ["白酒", "核心仓位"],
                "action_history": ["2026-03-01: 1700 买入 100 股", "2026-03-02: 1750 减仓 50 股"],
                "notes": "回调再加仓",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["stock_code"], "600519")
        self.assertEqual(payload["status"], "holding")
        self.assertTrue(payload["is_favorite"])

        get_resp = self.client.get("/api/v1/portfolio/profiles/600519")
        self.assertEqual(get_resp.status_code, 200)
        data = get_resp.json()
        self.assertEqual(data["buy_price"], 1688.5)
        self.assertEqual(data["position_pct"], 35)
        self.assertEqual(data["total_investment"], 500000)
        self.assertIn("白酒", data["tags"])
        self.assertEqual(len(data.get("action_history") or []), 2)

    def test_list_with_filters(self) -> None:
        self.client.put(
            "/api/v1/portfolio/profiles/600519",
            json={"stock_code": "600519", "status": "holding", "is_favorite": True},
        )
        self.client.put(
            "/api/v1/portfolio/profiles/AAPL",
            json={"stock_code": "AAPL", "status": "watch", "is_favorite": False},
        )

        by_status = self.client.get("/api/v1/portfolio/profiles", params={"status": "holding"})
        self.assertEqual(by_status.status_code, 200)
        self.assertEqual(by_status.json()["total"], 1)

        favorite = self.client.get("/api/v1/portfolio/profiles", params={"favorite_only": True})
        self.assertEqual(favorite.status_code, 200)
        self.assertEqual(favorite.json()["total"], 1)

    def test_delete_profile(self) -> None:
        self.client.put(
            "/api/v1/portfolio/profiles/00700",
            json={"stock_code": "00700", "status": "watch"},
        )
        delete_resp = self.client.delete("/api/v1/portfolio/profiles/00700")
        self.assertEqual(delete_resp.status_code, 200)
        self.assertTrue(delete_resp.json()["ok"])

        get_resp = self.client.get("/api/v1/portfolio/profiles/00700")
        self.assertEqual(get_resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
