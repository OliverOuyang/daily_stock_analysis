# -*- coding: utf-8 -*-
"""Tests for analysis status API response payload."""

import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import src.auth as auth
from api.app import create_app
from src.config import Config


class AnalysisStatusApiTestCase(unittest.TestCase):
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

    @patch("api.v1.endpoints.analysis.get_task_queue")
    @patch("src.storage.DatabaseManager.get_instance")
    def test_status_completed_includes_position_actions(self, mock_db_get_instance, mock_get_task_queue) -> None:
        mock_task_queue = MagicMock()
        mock_task_queue.get_task.return_value = None
        mock_get_task_queue.return_value = mock_task_queue

        raw_result = {
            "strategy": {
                "position_actions": {
                    "reduce_price": 35.0,
                    "reduce_ratio_pct": 50,
                    "add_price": 31.2,
                    "add_ratio_pct": 20,
                    "basis": "前高压力位 + 回踩MA20",
                    "confidence": 82,
                }
            }
        }
        record = SimpleNamespace(
            id=101,
            code="000933",
            name="神火股份",
            report_type="detailed",
            created_at=datetime(2026, 3, 4, 10, 30, 0),
            sentiment_score=72,
            operation_advice="持有",
            trend_prediction="震荡偏多",
            analysis_summary="等待确认突破",
            ideal_buy=31.0,
            secondary_buy=30.2,
            stop_loss=29.2,
            take_profit=35.0,
            raw_result=json.dumps(raw_result, ensure_ascii=False),
        )

        mock_db = MagicMock()
        mock_db.get_analysis_history.return_value = [record]
        mock_db_get_instance.return_value = mock_db

        resp = self.client.get("/api/v1/analysis/status/task_demo_001")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()

        self.assertEqual(payload["status"], "completed")
        strategy = payload["result"]["report"]["strategy"]
        self.assertIsNotNone(strategy)
        self.assertIn("position_actions", strategy)

        pa = strategy["position_actions"]
        self.assertEqual(pa["reduce_price"], 35.0)
        self.assertEqual(pa["reduce_ratio_pct"], 50.0)
        self.assertEqual(pa["add_price"], 31.2)
        self.assertEqual(pa["add_ratio_pct"], 20.0)
        self.assertEqual(pa["basis"], "前高压力位 + 回踩MA20")
        self.assertEqual(pa["confidence"], 82)


if __name__ == "__main__":
    unittest.main()
