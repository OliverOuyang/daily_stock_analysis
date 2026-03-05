# TODO（V2）

## Phase 1（先落地）
- [x] 自选池持仓全局置顶（含收藏视图）
- [x] 历史记录一键加入自选（默认观望+收藏）
- [x] 自选池股票名兜底补全
- [x] 输入框支持股票名解析（含重名候选）

## Phase 2
- [x] 点位双轨显示（我的目标 vs AI建议）
- [x] 同步按钮基于数值字段写入
- [x] `ReportStrategy` 增加 `*_value` 字段并前后端透传

## Phase 3
- [ ] 市场异动 prescore start/poll 接口
- [ ] 板块筛选参数 `sector_keyword/min_change_pct`
- [ ] 前端预扫描进度与空结果诊断展示

## Phase 4
- [x] 首页内嵌资产诊断卡
- [x] `/api/v1/portfolio/review` 独立接口
- [x] 跳转 chat 深聊透传摘要

## 验证
- [ ] 后端 pytest 覆盖新增接口与排序逻辑
- [ ] 前端 build + 关键路径手工冒烟
