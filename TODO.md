# TODO

## Next Backend Optimizations (Requested)

- [x] `src/services/stock_service.py`: optimize `batch_get_realtime_quotes` with `concurrent.futures.ThreadPoolExecutor` for parallel quote fetching.
- [x] `api/v1/endpoints/market.py`: improve `_discover_hot_sectors` leader filtering (exclude `ST`, prefer high turnover rate or top-50% market cap when available).
- [x] `src/scheduler.py` (or related scheduler module): add trading-day cron scans at `10:30` and `14:30` (Mon-Fri) to run market scan + trigger Simple AI analysis.
- [x] `api/v1/endpoints/market.py`: add robust timeout/empty-data fallback handling for Akshare data source.

## Future TODO (Need hardening / verification)

- [ ] `api/v1/endpoints/market.py`: add explicit cache invalidation API/strategy and observability (cache hit ratio, stale age) for discover cache.
- [ ] `api/v1/endpoints/market.py`: tighten leader quality filter with configurable market-cap floor (default 30B CNY), turnover/rank weighting, and min leaders per sector guarantee.
- [ ] `src/scheduler.py`: make 10:30 / 14:30 scan task idempotent across multi-instance deployment (distributed lock).
- [ ] `api/v1/endpoints/market.py`: enrich full-source failure fallback with stable mock pack + source error diagnostics for frontend display.
- [ ] `data_provider/manager` + `src/services/stock_service.py`: add automatic source failover and circuit-breaker when realtime quote fetch fails repeatedly.
