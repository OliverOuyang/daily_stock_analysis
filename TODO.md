# TODO

## Next Backend Optimizations (Requested)

- [x] `src/services/stock_service.py`: optimize `batch_get_realtime_quotes` with `concurrent.futures.ThreadPoolExecutor` for parallel quote fetching.
- [x] `api/v1/endpoints/market.py`: improve `_discover_hot_sectors` leader filtering (exclude `ST`, prefer high turnover rate or top-50% market cap when available).
- [x] `src/scheduler.py` (or related scheduler module): add trading-day cron scans at `10:30` and `14:30` (Mon-Fri) to run market scan + trigger Simple AI analysis.
- [x] `api/v1/endpoints/market.py`: add robust timeout/empty-data fallback handling for Akshare data source.
