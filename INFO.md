# eBay Integration - Implementation Details

## Overview

This is a complete, production-ready Home Assistant custom integration for monitoring eBay account activity. It supports multiple accounts, custom searches, comprehensive automation capabilities, and advanced chunked data storage for handling large datasets.

## Architecture

### Core Components

1. **ebay_api.py** - eBay API wrapper
   - Uses Browse API (modern REST API for searches)
   - Uses Trading API (account data)
   - Uses Analytics API (rate limit tracking)
   - Implements OAuth authentication
   - Automatic price formatting with currency symbols
   - Handles authentication and rate limiting

2. **coordinator.py** - Data coordinators with persistence
   - `EbayBidsCoordinator` - Active bids with change detection
   - `EbayWatchlistCoordinator` - Watched items
   - `EbayPurchasesCoordinator` - Purchase history with shipping tracking
   - `EbaySearchCoordinator` - Custom search results
   - **NEW:** Persistent state storage across restarts (60-day retention)
   - **NEW:** Automatic sorting (bids/watchlist/searches by end_time, purchases by date)
   - All inherit from `DataUpdateCoordinator`

3. **config_flow.py** - UI configuration
   - OAuth credential collection
   - Search management interface
   - Add/edit/delete searches via UI
   - Multi-step flow with validation

4. **sensor.py** - Chunked sensor entities
   - **NEW:** Main sensors (count only, no items)
   - **NEW:** Chunk sensors (20 items each, unlimited chunks)
   - One main + N chunk sensors per account for bids/watchlist/purchases
   - One main + N chunk sensors per search
   - Rich attributes with full item details
   - Real-time state updates
   - No 16KB database limit issues

5. **__init__.py** - Integration setup
   - Service registration
   - Storage management
   - Coordinator initialization
   - **NEW:** Dynamic chunk sensor creation
   - Multi-account support

### Data Flow

```
eBay API
    ↓
ebay_api.py (API wrapper + price formatting)
    ↓
coordinator.py (Data coordinators with persistence & sorting)
    ↓
sensor.py (Main sensors + Chunk sensors)
    ↓
Home Assistant Core
    ↓
Events (with formatted prices) + State updates (chunked data)
```

## New Features (v2.0)

### ✅ Formatted Prices
- All items include `formatted_price` field (e.g., `£3.20`, `$15.99`, `€42.50`)
- Available in all events and sensor attributes
- Supports GBP, USD, EUR, AUD, CAD with proper symbols
- Always shows 2 decimal places
- No more manual currency formatting needed

### ✅ Event State Persistence
- Events fire reliably after Home Assistant restarts
- State stored in `.storage/` directory:
  - `ebay_bids_state_<account>.json`
  - `ebay_purchases_state_<account>.json`
  - `ebay_search_state_<search_id>.json`
- 60-day automatic data retention
- Prevents duplicate event firing
- Enables accurate change detection

### ✅ Automatic Sorting
- **Bids:** Sorted by end_time (ending soonest first)
- **Watchlist:** Sorted by end_time (ending soonest first)
- **Searches:** Sorted by end_time (ending soonest first)
- **Purchases:** Sorted by purchase_date (newest first)
- Most urgent items always in chunk_1
- No manual sorting needed in templates

### ✅ Chunked Sensor System
- **Main sensors:** Show count only, list chunk sensors
- **Chunk sensors:** Hold up to 20 items each
- **Unlimited items:** No 16KB database limit
- **Dynamic creation:** Chunks auto-create/remove as needed
- **Example:** 97 watchlist items = 1 main + 5 chunk sensors

**Sensor Structure:**
```
sensor.ebay_account_active_bids        # Main: count=47, chunk_count=3
sensor.ebay_account_active_bids_chunk_1  # Items 1-20 (ending soonest)
sensor.ebay_account_active_bids_chunk_2  # Items 21-40
sensor.ebay_account_active_bids_chunk_3  # Items 41-47
```

## Features Implemented

### ✅ Multi-Account Support
- Add unlimited eBay accounts
- Each account has separate sensors
- Independent update schedules
- Isolated storage per account

### ✅ Saved Searches
- Create/edit/delete via UI or services
- Per-account storage
- Configurable parameters:
  - Search query
  - eBay site (UK, US, etc.)
  - Category filter
  - Price range
  - Listing type (auction/buy it now/both)
  - Update interval
- Real-time result tracking
- New item detection
- **NEW:** Chunk sensors for searches with >20 results

### ✅ Active Bid Monitoring
- Current bid status
- High bidder detection
- Reserve met status
- Time remaining calculations
- Bid count tracking
- **NEW:** Formatted prices in all attributes
- **NEW:** Events fire reliably after restart
- Automatic state change events

### ✅ Watchlist Tracking
- All watched items (no 10-item limit)
- Price monitoring with formatted prices
- Watcher count
- **NEW:** Chunked storage for 100+ items
- **NEW:** Sorted by ending soonest
- Automatic updates

### ✅ Purchase Tracking
- Recent purchase history
- Shipping status (pending/shipped/delivered)
- Tracking number extraction
- Seller information
- **NEW:** Formatted prices
- **NEW:** Sorted by newest first
- Automatic status change events

### ✅ Seller Information
For all items:
- Username
- Feedback score
- Positive feedback percentage
- Location (country)
- Profile URL

### ✅ Event System
8 event types for automations (all now reliable after restart):
- `ebay_new_search_result` - **NEW:** Works after restart
- `ebay_became_high_bidder` - **NEW:** Works after restart
- `ebay_outbid`
- `ebay_auction_ending_soon` (1 hour threshold)
- `ebay_auction_won` - **NEW:** Works after restart
- `ebay_auction_lost` - **NEW:** Works after restart
- `ebay_item_shipped` - **NEW:** Works after restart
- `ebay_item_delivered` - **NEW:** Works after restart

**All events now include formatted_price field!**

### ✅ Services
11 services for control:
- `refresh_bids`
- `refresh_watchlist`
- `refresh_purchases`
- `refresh_search`
- `refresh_account`
- `refresh_all`
- `refresh_api_usage` - **NEW:** Check rate limits
- `create_search`
- `update_search`
- `delete_search`
- `get_rate_limits` - **NEW:** View API usage

### ✅ Sample Dashboards
- Complete dashboard (all features, chunk-aware)
- Searches dashboard (grid view, chunk-aware)
- Both updated for chunk sensors
- Use formatted_price throughout
- Status indicators with emoji
- Time remaining displays
- Quick refresh buttons
- Responsive layouts

### ✅ Automation Examples
8 ready-to-use automations:
- Outbid notifications (with formatted prices)
- Auction ending alerts
- High bidder notifications
- New search result alerts
- Won/lost auction results
- Shipping notifications
- Delivery notifications
- All use formatted_price for cleaner messages

### ✅ HACS Compatible
- Proper manifest.json
- hacs.json configuration
- Semantic versioning
- Standard directory structure

## Technical Decisions

### Why Chunk Sensors?
- **Solves 16KB limit:** Home Assistant limits sensor attributes to 16KB
- **Unlimited items:** Can now display 100+ watchlist items
- **Better performance:** Each chunk updates independently
- **Sorted data:** Most urgent items always in chunk_1
- **Database friendly:** No more state size issues

### Why Persistent State?
- **Reliable events:** Events fire correctly after restarts
- **Change detection:** Accurately detect bid changes, new items, status changes
- **60-day retention:** Keeps relevant data, auto-cleans old items
- **No duplicate events:** Prevents event spam on restart

### Why Formatted Prices?
- **User friendly:** `£3.20` instead of `3.2 GBP`
- **Consistent:** Always 2 decimal places
- **Clean templates:** No complex Jinja currency formatting needed
- **Multi-currency:** Handles GBP, USD, EUR, AUD, CAD automatically

## Breaking Changes in v2.0

### Dashboard Templates
**Old (broken):**
```yaml
{% set items = state_attr('sensor.ebay_account_active_bids', 'items') %}
{{ item.current_price.value }}
```

**New (required):**
```yaml
{% set chunk_sensors = state_attr('sensor.ebay_account_active_bids', 'chunk_sensors') %}
{% for chunk_sensor in chunk_sensors %}
  {% set items = state_attr(chunk_sensor, 'items') %}
  {{ item.formatted_price }}
{% endfor %}
```

### Automation Templates
**Old (broken):**
```yaml
message: "Price: {{ trigger.event.data.item.current_price.value }}"
```

**New (required):**
```yaml
message: "Price: {{ trigger.event.data.item.formatted_price }}"
```

### Event Names
**Fixed:**
- `ebay_won` → `ebay_auction_won`
- `ebay_lost` → `ebay_auction_lost`

## Performance Characteristics

### Memory Usage
- Minimal base (stores config only)
- Item data in coordinator cache
- **NEW:** State persistence adds ~100KB per account
- **NEW:** Chunk sensors add minimal overhead
- ~1-3MB per account (depending on item counts)

### API Calls Per Hour
Default configuration (1 account, 3 searches):
- Bids: 12/hour (5 min interval)
- Watchlist: 6/hour (10 min)
- Purchases: 2/hour (30 min)
- Searches: 12/hour (15 min each × 3)
- **NEW:** API Usage: 1/hour (optional)
- **Total: ~33 calls/hour, ~792/day**

Well within free tier limits (5000/day).

### Database Impact
- **OLD:** Could hit 16KB limit with 100+ items
- **NEW:** Main sensors store minimal data (count + chunk list)
- **NEW:** Each chunk sensor stores max 20 items (~8KB)
- **NEW:** No database size issues regardless of item count

## Version History

### v2.0.0 (Current) - Major Update
- ✅ Chunked sensor system (20 items per chunk)
- ✅ Event state persistence (60-day retention)
- ✅ Formatted prices (`£3.20` format)
- ✅ Automatic sorting (ending soonest first)
- ✅ All 8 events work reliably after restart
- ✅ No 16KB database limits
- ✅ Updated dashboards and automations
- ⚠️ Breaking changes in templates (see migration guide)
- +583 lines of code (+28%)

### v1.0.0 (Previous)
- Initial HACS release
- Multi-account support
- Saved searches
- 8 event types
- Service integration
- Sample dashboards

## License

Apache 2.0 License - See LICENSE file
Free for personal and commercial use
