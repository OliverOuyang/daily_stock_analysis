# Debug Log（V2）

## 2026-03-05 初始化
- 建立 V2 文档目录与一致性基线。
- 分支：`feat/watchlist-market-v2`
- 目标：先完成 Phase 1（排序、历史入自选、名称解析）再推进 prescore 与资产诊断。

## 2026-03-05 Phase 1 完成
- 后端新增 `GET /api/v1/stocks/resolve`，支持名称/代码候选解析。
- 前端输入框支持股票名称分析，重名时展示候选并手动选择。
- 自选池排序改为持仓优先（holding first），并按更新时间降序。
- 历史记录新增“一键加入自选”（默认收藏；已存在档案保留原状态/字段）。
- 自选卡片名称展示增加兜底逻辑（优先档案名，其次行情名）。
- 验证结果：
  - `./venv/bin/pytest -q tests/test_stocks_resolve_api.py tests/test_portfolio_api.py tests/test_market_discover_api.py` 通过。
  - `apps/dsa-web npm run build` 通过。

## 2026-03-05 市场异动筛选增强（阶段中）
- 后端 `GET /api/v1/market/discover` 新增筛选参数：
  - `sector_keyword`
  - `min_change_pct`
- 前端市场异动面板新增：
  - 板块关键词输入
  - 最小涨跌幅输入
  - “预评分扫描”按钮（触发 simple 分析并轮询任务状态，完成后刷新）
- 验证结果：
  - `./venv/bin/pytest -q tests/test_market_discover_api.py tests/test_stocks_resolve_api.py` 通过。
  - `apps/dsa-web npm run build` 通过。

## 2026-03-05 点位一致性 + 资产分析首页化
- 后端：
  - `ReportStrategy` 新增 `ideal_buy_value/secondary_buy_value/stop_loss_value/take_profit_value`
  - 新增 `GET /api/v1/portfolio/review`
- 前端：
  - 配置框点位改为“我的目标 + AI建议(可同步)”双轨
  - 资产诊断按钮改为首页直接拉取诊断，保留“深聊”跳转
- 测试：
  - `./venv/bin/pytest -q tests/test_portfolio_review_api.py tests/test_stocks_resolve_api.py tests/test_market_discover_api.py` 通过。
  - `apps/dsa-web npm run build` 通过。

## 2026-03-05 市场异动预评分 run_id 化
- 后端新增：
  - `POST /api/v1/market/discover/prescore/start`
  - `GET /api/v1/market/discover/prescore/{run_id}`
- 前端市场异动面板已切换为 run_id 轮询，不再直接拼 task_id 轮询。
- 支持筛选参数：`min_score / sector_keyword / min_change_pct`。
- 测试：
  - `./venv/bin/pytest -q tests/test_market_discover_api.py tests/test_portfolio_review_api.py tests/test_stocks_resolve_api.py` 通过。
  - `apps/dsa-web npm run build` 通过。

## Debug 模板
- 问题：
- 复现步骤：
- 根因：
- 修复提交：
- 验证结果：
- 回归风险：
