# -*- coding: utf-8 -*-
"""
===================================
定时调度模块
===================================

职责：
1. 支持每日定时执行股票分析
2. 支持定时执行大盘复盘
3. 优雅处理信号，确保可靠退出

依赖：
- schedule: 轻量级定时任务库
"""

import logging
import signal
import sys
import time
import threading
from datetime import datetime
from typing import Callable, Optional, List, Tuple

logger = logging.getLogger(__name__)


class GracefulShutdown:
    """
    优雅退出处理器
    
    捕获 SIGTERM/SIGINT 信号，确保任务完成后再退出
    """
    
    def __init__(self):
        self.shutdown_requested = False
        self._lock = threading.Lock()
        
        # 注册信号处理器
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """信号处理函数"""
        with self._lock:
            if not self.shutdown_requested:
                logger.info(f"收到退出信号 ({signum})，等待当前任务完成...")
                self.shutdown_requested = True
    
    @property
    def should_shutdown(self) -> bool:
        """检查是否应该退出"""
        with self._lock:
            return self.shutdown_requested


class Scheduler:
    """
    定时任务调度器
    
    基于 schedule 库实现，支持：
    - 每日定时执行
    - 启动时立即执行
    - 优雅退出
    """
    
    def __init__(self, schedule_time: str = "18:00"):
        """
        初始化调度器
        
        Args:
            schedule_time: 每日执行时间，格式 "HH:MM"
        """
        try:
            import schedule
            self.schedule = schedule
        except ImportError:
            logger.error("schedule 库未安装，请执行: pip install schedule")
            raise ImportError("请安装 schedule 库: pip install schedule")
        
        self.schedule_time = schedule_time
        self.shutdown_handler = GracefulShutdown()
        self._task_callback: Optional[Callable] = None
        self._running = False
        
    def set_daily_task(self, task: Callable, run_immediately: bool = True):
        """
        设置每日定时任务
        
        Args:
            task: 要执行的任务函数（无参数）
            run_immediately: 是否在设置后立即执行一次
        """
        self._task_callback = task
        
        # 设置每日定时任务
        self.schedule.every().day.at(self.schedule_time).do(self._safe_run_task)
        logger.info(f"已设置每日定时任务，执行时间: {self.schedule_time}")
        
        if run_immediately:
            logger.info("立即执行一次任务...")
            self._safe_run_task()
    
    def _safe_run_task(self):
        """安全执行任务（带异常捕获）"""
        if self._task_callback is None:
            return

        self._safe_run_named_task(self._task_callback, "daily_task")

    def _safe_run_named_task(self, task: Callable, task_name: str):
        """安全执行指定任务（带异常捕获）"""
        try:
            logger.info("=" * 50)
            logger.info(
                "定时任务开始执行 [%s] - %s",
                task_name,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            )
            logger.info("=" * 50)

            task()

            logger.info(
                "定时任务执行完成 [%s] - %s",
                task_name,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            )

        except Exception as e:
            logger.exception("定时任务执行失败 [%s]: %s", task_name, e)

    def set_weekday_tasks(self, tasks: List[Tuple[str, Callable, str]], run_immediately: bool = False):
        """
        设置工作日定时任务（周一到周五）

        Args:
            tasks: [(time_str, callback, task_name), ...]
            run_immediately: 是否启动后立即执行一次
        """
        weekdays = [
            self.schedule.every().monday,
            self.schedule.every().tuesday,
            self.schedule.every().wednesday,
            self.schedule.every().thursday,
            self.schedule.every().friday,
        ]

        for time_str, callback, task_name in tasks:
            for day in weekdays:
                day.at(time_str).do(self._safe_run_named_task, callback, task_name)
            logger.info("已设置工作日定时任务 [%s]，执行时间: %s", task_name, time_str)

        if run_immediately:
            for _, callback, task_name in tasks:
                self._safe_run_named_task(callback, task_name)
    
    def run(self):
        """
        运行调度器主循环
        
        阻塞运行，直到收到退出信号
        """
        self._running = True
        logger.info("调度器开始运行...")
        logger.info(f"下次执行时间: {self._get_next_run_time()}")
        
        while self._running and not self.shutdown_handler.should_shutdown:
            self.schedule.run_pending()
            time.sleep(30)  # 每30秒检查一次
            
            # 每小时打印一次心跳
            if datetime.now().minute == 0 and datetime.now().second < 30:
                logger.info(f"调度器运行中... 下次执行: {self._get_next_run_time()}")
        
        logger.info("调度器已停止")
    
    def _get_next_run_time(self) -> str:
        """获取下次执行时间"""
        jobs = self.schedule.get_jobs()
        if jobs:
            next_run = min(job.next_run for job in jobs)
            return next_run.strftime('%Y-%m-%d %H:%M:%S')
        return "未设置"
    
    def stop(self):
        """停止调度器"""
        self._running = False


def run_with_schedule(
    task: Callable,
    schedule_time: str = "18:00",
    run_immediately: bool = True
):
    """
    便捷函数：使用定时调度运行任务
    
    Args:
        task: 要执行的任务函数
        schedule_time: 每日执行时间
        run_immediately: 是否立即执行一次
    """
    scheduler = Scheduler(schedule_time=schedule_time)
    scheduler.set_daily_task(task, run_immediately=run_immediately)
    scheduler.run()


def build_market_discover_scan_task(top_n: int = 5, leaders_per_sector: int = 3) -> Callable:
    """
    构造市场发现扫描任务。

    扫描逻辑：
    1. 发现热点板块和龙头
    2. 为龙头自动触发 simple 分析任务
    """

    def _task() -> None:
        from api.v1.endpoints.market import run_market_discover_scan

        result = run_market_discover_scan(
            top_n=top_n,
            leaders_per_sector=leaders_per_sector,
            trigger_analysis=True,
            use_cache=False,  # 定时扫描应强制拉取最新结果
        )
        logger.info(
            "市场扫描完成: source=%s, sectors=%s, triggered=%s, duplicate=%s",
            result.source,
            result.total_sectors,
            result.triggered_tasks,
            result.duplicate_tasks,
        )

    return _task


def run_market_discover_schedule(
    run_immediately: bool = False,
    top_n: int = 5,
    leaders_per_sector: int = 3,
):
    """
    启动市场发现定时扫描：
    - 每个交易日（周一至周五）10:30
    - 每个交易日（周一至周五）14:30
    """
    scheduler = Scheduler(schedule_time="10:30")
    task = build_market_discover_scan_task(top_n=top_n, leaders_per_sector=leaders_per_sector)
    scheduler.set_weekday_tasks(
        tasks=[
            ("10:30", task, "market_discover_scan_1030"),
            ("14:30", task, "market_discover_scan_1430"),
        ],
        run_immediately=run_immediately,
    )
    scheduler.run()


if __name__ == "__main__":
    # 测试定时调度
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
    )
    
    def test_task():
        print(f"任务执行中... {datetime.now()}")
        time.sleep(2)
        print("任务完成!")
    
    print("启动测试调度器（按 Ctrl+C 退出）")
    run_with_schedule(test_task, schedule_time="23:59", run_immediately=True)
