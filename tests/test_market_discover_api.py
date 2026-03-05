# -*- coding: utf-8 -*-
"""Integration tests for market discover API."""

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

import src.auth as auth
from api.app import create_app
from src.config import Config
from api.v1.endpoints import market as market_endpoint
from api.v1.schemas.market import MarketDiscoverResponse, SectorDiscoverItem, MarketLeader


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
        os.environ.pop("MARKET_DISCOVER_CACHE_TTL_SECONDS", None)
        market_endpoint._DISCOVER_CACHE.clear()
        market_endpoint._PRESCORE_RUNS.clear()
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

    @patch("api.v1.endpoints.market.get_db")
    @patch("api.v1.endpoints.market.get_task_queue")
    @patch("api.v1.endpoints.market._discover_hot_sectors")
    def test_market_discover_min_score_filters_leaders(self, mock_discover, mock_get_queue, mock_get_db) -> None:
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
        fake_db = MagicMock()
        fake_db.get_latest_sentiment_scores.return_value = {
            "000933": {"sentiment_score": 82},
            "601899": {"sentiment_score": 68},
        }
        mock_get_db.return_value = fake_db
        mock_get_queue.return_value = _FakeTaskQueue()

        resp = self.client.get("/api/v1/market/discover?trigger_analysis=false&min_score=70")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_sectors"], 1)
        leaders = data["sectors"][0]["leaders"]
        self.assertEqual(len(leaders), 1)
        self.assertEqual(leaders[0]["stock_code"], "000933")
        self.assertEqual(leaders[0]["latest_score"], 82)

    @patch("api.v1.endpoints.market.get_task_queue")
    @patch("api.v1.endpoints.market._discover_hot_sectors")
    def test_market_discover_uses_cache_to_avoid_refetch_and_retrigger(self, mock_discover, mock_get_queue) -> None:
        os.environ["MARKET_DISCOVER_CACHE_TTL_SECONDS"] = "1800"
        mock_discover.return_value = (
            "akshare",
            [
                {
                    "sector_name": "人工智能",
                    "change_pct": 1.1,
                    "leaders": [
                        {"stock_code": "300308", "stock_name": "中际旭创", "change_pct": 2.2},
                        {"stock_code": "002230", "stock_name": "科大讯飞", "change_pct": 1.2},
                    ],
                }
            ],
        )
        mock_get_queue.return_value = _FakeTaskQueue()

        resp1 = self.client.get("/api/v1/market/discover")
        self.assertEqual(resp1.status_code, 200)
        d1 = resp1.json()
        self.assertEqual(d1["triggered_tasks"], 2)

        resp2 = self.client.get("/api/v1/market/discover")
        self.assertEqual(resp2.status_code, 200)
        d2 = resp2.json()
        self.assertEqual(d2["triggered_tasks"], 0)
        self.assertEqual(mock_discover.call_count, 1)

    @patch("api.v1.endpoints.market.get_task_queue")
    @patch("api.v1.endpoints.market._discover_hot_sectors")
    def test_market_discover_fallback_to_mock_when_upstream_empty(self, mock_discover, mock_get_queue) -> None:
        mock_discover.return_value = ("akshare", [])
        mock_get_queue.return_value = _FakeTaskQueue()

        resp = self.client.get("/api/v1/market/discover?trigger_analysis=false")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["source"], "mock_fallback")
        self.assertGreaterEqual(data["total_sectors"], 1)
        self.assertGreaterEqual(len(data["sectors"][0]["leaders"]), 2)

    @patch("api.v1.endpoints.market.get_task_queue")
    @patch("api.v1.endpoints.market._discover_hot_sectors")
    def test_market_discover_fallback_when_leaders_all_empty(self, mock_discover, mock_get_queue) -> None:
        mock_discover.return_value = (
            "akshare",
            [
                {"sector_name": "人工智能", "change_pct": 1.2, "leaders": []},
                {"sector_name": "半导体", "change_pct": 0.9, "leaders": []},
            ],
        )
        mock_get_queue.return_value = _FakeTaskQueue()

        resp = self.client.get("/api/v1/market/discover?trigger_analysis=false")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["source"], "mock_fallback")
        self.assertGreaterEqual(data["total_sectors"], 1)
        self.assertGreaterEqual(len(data["sectors"][0]["leaders"]), 2)

    @patch("api.v1.endpoints.market.get_task_queue")
    @patch("api.v1.endpoints.market._discover_hot_sectors", side_effect=RuntimeError("network down"))
    def test_market_discover_final_guard_returns_200(self, _mock_discover, mock_get_queue) -> None:
        mock_get_queue.return_value = _FakeTaskQueue()
        resp = self.client.get("/api/v1/market/discover?trigger_analysis=false")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["source"], "mock_fallback")
        self.assertGreaterEqual(data["total_sectors"], 1)

    def test_sector_filter_excludes_st_and_low_market_cap(self) -> None:
        import pandas as pd

        fake_board = pd.DataFrame([
            {"板块名称": "有色金属", "涨跌幅": 2.5},
        ])
        fake_cons = pd.DataFrame([
            {"代码": "000001", "名称": "ST测试", "涨跌幅": 5.0, "成交量": 1000, "换手率": 12.0, "总市值": "200亿"},
            {"代码": "000002", "名称": "大盘龙头A", "涨跌幅": 4.0, "成交量": 8000, "换手率": 10.0, "总市值": "800亿"},
            {"代码": "000003", "名称": "大盘龙头B", "涨跌幅": 3.0, "成交量": 7000, "换手率": 9.0, "总市值": "500亿"},
            {"代码": "000004", "名称": "小盘非ST", "涨跌幅": 6.0, "成交量": 9000, "换手率": 15.0, "总市值": "20亿"},
        ])
        fake_ak = MagicMock()
        fake_ak.stock_board_industry_name_em.return_value = fake_board
        fake_ak.stock_board_industry_cons_em.return_value = fake_cons

        with patch.dict("sys.modules", {"akshare": fake_ak}):
            source, sectors = market_endpoint._discover_hot_sectors(top_n=1, leaders_per_sector=2)

        self.assertEqual(source, "akshare_em")
        self.assertEqual(len(sectors), 1)
        leaders = sectors[0]["leaders"]
        self.assertEqual(len(leaders), 2)
        names = {x["stock_name"] for x in leaders}
        self.assertNotIn("ST测试", names)
        self.assertNotIn("小盘非ST", names)


    @patch("api.v1.endpoints.market.get_task_queue")
    @patch("api.v1.endpoints.market._discover_hot_sectors")
    def test_market_discover_cache_meta_and_invalidate(self, mock_discover, mock_get_queue) -> None:
        os.environ["MARKET_DISCOVER_CACHE_TTL_SECONDS"] = "1800"
        mock_discover.return_value = (
            "akshare",
            [
                {
                    "sector_name": "人工智能",
                    "change_pct": 1.1,
                    "leaders": [
                        {"stock_code": "300308", "stock_name": "中际旭创", "change_pct": 2.2},
                        {"stock_code": "002230", "stock_name": "科大讯飞", "change_pct": 1.2},
                    ],
                }
            ],
        )
        mock_get_queue.return_value = _FakeTaskQueue()

        first = self.client.get("/api/v1/market/discover")
        self.assertEqual(first.status_code, 200)
        first_data = first.json()
        self.assertFalse(first_data["cache_hit"])
        self.assertIsNone(first_data["cache_age_seconds"])
        self.assertGreater(first_data["cache_ttl_seconds"], 0)

        second = self.client.get("/api/v1/market/discover")
        self.assertEqual(second.status_code, 200)
        second_data = second.json()
        self.assertTrue(second_data["cache_hit"])
        self.assertIsInstance(second_data["cache_age_seconds"], int)

        inv = self.client.post("/api/v1/market/discover/cache/invalidate")
        self.assertEqual(inv.status_code, 200)
        inv_data = inv.json()
        self.assertTrue(inv_data["success"])
        self.assertGreaterEqual(inv_data["data"]["removed_entries"], 1)

    @patch("api.v1.endpoints.market.get_task_queue")
    @patch("api.v1.endpoints.market._discover_hot_sectors")
    def test_market_prescore_start_returns_run_id(self, mock_discover, mock_get_queue) -> None:
        mock_discover.return_value = (
            "akshare",
            [
                {
                    "sector_name": "有色金属",
                    "change_pct": 2.3,
                    "leaders": [
                        {"stock_code": "000933", "stock_name": "神火股份", "change_pct": 5.1},
                    ],
                }
            ],
        )
        mock_get_queue.return_value = _FakeTaskQueue()

        resp = self.client.post("/api/v1/market/discover/prescore/start?top_n=3&leaders_per_sector=2&min_score=70")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("run_id", data)
        self.assertIn(data["status"], ("running", "completed"))
        self.assertGreaterEqual(data["total_tasks"], 0)

    @patch("api.v1.endpoints.market.run_market_discover_scan")
    @patch("api.v1.endpoints.market._task_is_done", return_value=(True, False))
    def test_market_prescore_status_completed_with_result(self, _mock_done, mock_scan) -> None:
        mock_scan.return_value = MarketDiscoverResponse(
            source="akshare",
            total_sectors=1,
            triggered_tasks=0,
            duplicate_tasks=0,
            sectors=[
                SectorDiscoverItem(
                    sector_name="有色金属",
                    change_pct=2.3,
                    leaders=[MarketLeader(stock_code="000933", stock_name="神火股份", change_pct=5.1, latest_score=82)],
                )
            ],
            cache_hit=False,
            cache_age_seconds=None,
            cache_ttl_seconds=1200,
        )

        run_id = "run_test_1"
        market_endpoint._PRESCORE_RUNS[run_id] = {
            "ts": 9999999999,
            "status": "running",
            "task_ids": ["task_1"],
            "total_tasks": 1,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "diagnostics": None,
            "params": {"top_n": 5, "leaders_per_sector": 3, "min_score": 70, "sector_keyword": None, "min_change_pct": None},
            "result": None,
        }

        resp = self.client.get(f"/api/v1/market/discover/prescore/{run_id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["progress"], 100)
        self.assertIsNotNone(data["result"])
        self.assertEqual(data["result"]["sectors"][0]["leaders"][0]["stock_code"], "000933")


if __name__ == "__main__":
    unittest.main()
