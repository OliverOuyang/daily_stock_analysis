# -*- coding: utf-8 -*-
"""Tests for stock resolve API."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.auth as auth
from api.app import create_app
from src.config import Config


class StocksResolveApiTestCase(unittest.TestCase):
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

    @patch("src.services.stock_service.StockService.resolve_stock_query")
    def test_resolve_stock_query_returns_candidates(self, mock_resolve) -> None:
        mock_resolve.return_value = [
            {
                "stock_code": "000933",
                "stock_name": "神火股份",
                "market": "CN",
                "score": 100,
            },
            {
                "stock_code": "600219",
                "stock_name": "南山铝业",
                "market": "CN",
                "score": 82,
            },
        ]

        resp = self.client.get("/api/v1/stocks/resolve?q=神火&limit=5")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["query"], "神火")
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["items"][0]["stock_code"], "000933")
        self.assertEqual(data["items"][0]["stock_name"], "神火股份")


if __name__ == "__main__":
    unittest.main()
