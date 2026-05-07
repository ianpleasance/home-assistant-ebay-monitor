# Changelog

## [2.3.0] - 2026-03-18

### Bug Fixes

- **False auction won/lost alerts from API glitches** — When an item disappeared from
  the active bids list, won/lost events were fired immediately based on the cached
  `is_high_bidder` status. Replaced with a grace period queue: items that disappear are
  held for two poll cycles before verification. If they reappear (transient API glitch)
  the pending check is cancelled with no event fired.
- **False auction lost alerts for last-minute bids** — The eBay Shopping API can take
  30–60 seconds after auction end to reflect the final high bidder. Previously, calling
  `GetSingleItem` immediately after an item disappeared could return stale data and fire
  the wrong event. The grace period ensures the API has settled before verification runs.
- **Previously-seen search items re-alerting as new** — The search state trim capped
  stored item IDs at 1000 using `set(list(...)[-1000:])`. Since sets have no guaranteed
  order, the trim discarded random items rather than the oldest ones. When those items
  reappeared on eBay they looked new and triggered alerts. Removed the trim entirely —
  item ID strings are negligible in size and there is no good reason to cap them.
- **HTTP timeouts missing from all API calls** — All six eBay API call sites now pass
  `ClientTimeout(total=30)` to prevent indefinite hangs on network issues.
- **Duplicate `return` statement** in `_get_marketplace_id` removed.

### Enhancements

- **`device_info`** added to all sensor classes — all sensors for an account now appear
  under a shared eBay device in the HA device registry.
- **`SensorStateClass.MEASUREMENT`** added to all count sensors (bids, watchlist,
  purchases, search results).
- **`last_updated`** attribute changed from ISO string to native `datetime` object on
  all sensors, consistent with HA standards.
- **Translations** — 7 new languages added: Danish (da), Finnish (fi), Japanese (ja),
  Norwegian (no), Polish (pl), Portuguese (pt), Swedish (sv). All 13 target languages
  now supported.
- **`homeassistant: "2024.1.0"`** minimum version added to `manifest.json`.
- **Removed unused `_create_chunks()` function** from `sensor.py`.
- **`info.md`** and **`CHANGELOG.md`** added (previously `INFO.md`, now lowercase).
- **`QUICK_START.md`** and **`USAGE_GUIDE.md`** content folded into `README.md` and
  those files removed.

## [2.2.0]

### Features

- `GetSingleItem` API verification for auction won/lost determination
- Pagination support for large bid, watchlist, and purchase lists
- Caching of `GetMyeBayBuying` API responses to avoid duplicate calls when multiple
  coordinators refresh simultaneously
- Per-account and per-search state persistence across HA restarts using HA `Store`
- Six translation languages: de, en, es, fr, it, nl

## [1.0.0]

### Initial Release

- Multi-account support
- Saved search management via UI and services
- Active bids monitoring with change detection
- Watchlist tracking
- Purchase history with shipping status tracking
- Event-driven automation system (8 event types)
- Pre-built dashboards
- Automation blueprints
- Comprehensive refresh services
