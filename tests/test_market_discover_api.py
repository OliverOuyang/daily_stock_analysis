# -*- coding: utf-8 -*-
"""Integration tests for market discover API."""

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.auth as auth
from api.app import create_app
from src.config import Config


class _FakeTaskQueue:
    def __init__(self) -> None:
        self._idx = 0

    def submit_task(self, stock_code: str, stock_name=None, report_type="simple", force_refresh=False):
        self._idx += 1
        return SimpleNamespace(task_id=f"task_{self._idx}", stock_code=stock_code, stock_name=stock_name, report_type=report_type)


class MarketDiscoverApiTestCase(unittest.TestCase):
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

    @patch("api.v1.endpoints.market.get_task_queue")
    @patch("api.v1.endpoints.market._discover_hot_sectors")
    def test_market_discover_returns_sectors_and_triggers_tasks(self, mock_discover, mock_get_queue) -> None:
        mock_discover.return_value = (
            "akshare",
            [
                {
                    "sector_name": "有色金属",
                    "change_pct": 2.3,
                    "leaders": [
                        {"stock_code": "000933", "stock_name": "神火股份", "change_pct": 5.1},
                        {"stock_code": "601899", "stock_name": "紫金矿业", "change_pct": 3.2},
                    ],
                }
            ],
        )
        mock_get_queue.return_value = _FakeTaskQueue()

        resp = self.client.get("/api/v1/market/discover")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["source"], "akshare")
        self.assertEqual(data["total_sectors"], 1)
        self.assertEqual(data["triggered_tasks"], 2)
        self.assertEqual(len(data["sectors"]), 1)
        self.assertEqual(data["sectors"][0]["sector_name"], "有色金属")
        self.assertEqual(data["sectors"][0]["leaders"][0]["stock_code"], "000933")
        self.assertTrue(data["sectors"][0]["leaders"][0]["task_id"].startswith("task_"))


if __name__ == "__main__":
    unittest.main()

