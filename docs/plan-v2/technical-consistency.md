# 技术一致性文档（V2）

## 1. 核心接口
- 新增：`POST /api/v1/market/discover/prescore/start`
- 新增：`GET /api/v1/market/discover/prescore/{run_id}`
- 新增：`GET /api/v1/portfolio/review`
- 新增：`GET /api/v1/stocks/resolve?q=...`
- 扩展：`GET /api/v1/market/discover` 支持 `sector_keyword`, `min_change_pct`

## 2. 数据字段约束
- `ReportStrategy` 扩展数值字段：
  - `ideal_buy_value`
  - `secondary_buy_value`
  - `stop_loss_value`
  - `take_profit_value`
- 前端同步点位时优先取 `*_value`，无值时回退字符串解析。

## 3. 排序与过滤规则
- 自选列表排序：`holding first` + `updated_at desc`
- 历史一键入自选默认：`status=watch`, `is_favorite=true`
- 市场异动 prescore 完成后再执行 min_score 与 sector filters

## 4. 兼容性策略
- 保留原 `GET /market/discover` 返回结构，不破坏旧前端。
- 旧字符串点位字段不删除，仅新增数值字段。
- 档案 upsert 为幂等，不覆盖未提交修改字段。

## 5. 观测与诊断
- 市场异动保持缓存诊断字段：`cache_hit`, `cache_age_seconds`, `cache_ttl_seconds`
- prescore 返回 `status/progress/diagnostics`
- debug 日志按 run_id / task_id 关联。
