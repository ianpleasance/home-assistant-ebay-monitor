# eBay Integration - Implementation Details

## Overview

This is a complete, production-ready Home Assistant custom integration for monitoring eBay account activity. It supports multiple accounts, custom searches, and comprehensive automation capabilities.

## Architecture

### Core Components

1. **ebay_api.py** - eBay API wrapper
   - Uses `ebaysdk-python` library
   - Implements Finding API (searches)
   - Implements Shopping API (item details)
   - Implements Trading API (account data)
   - Handles authentication and rate limiting

2. **coordinator.py** - Data coordinators
   - `EbayBidsCoordinator` - Active bids with change detection
   - `EbayWatchlistCoordinator` - Watched items
   - `EbayPurchasesCoordinator` - Purchase history with shipping tracking
   - `EbaySearchCoordinator` - Custom search results
   - All inherit from `DataUpdateCoordinator`

3. **config_flow.py** - UI configuration
   - OAuth credential collection
   - Search management interface
   - Add/edit/delete searches via UI
   - Multi-step flow with validation

4. **sensor.py** - Sensor entities
   - One sensor per account for bids/watchlist/purchases
   - One sensor per search
   - Rich attributes with full item details
   - Real-time state updates

5. **__init__.py** - Integration setup
   - Service registration
   - Storage management
   - Coordinator initialization
   - Multi-account support

### Data Flow

```
eBay API
    ↓
ebay_api.py (API wrapper)
    ↓
coordinator.py (Data coordinators with change detection)
    ↓
sensor.py (Sensor entities)
    ↓
Home Assistant Core
    ↓
Events (for automations) + State updates (for dashboards)
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

### ✅ Active Bid Monitoring
- Current bid status
- High bidder detection
- Reserve met status
- Time remaining calculations
- Bid count tracking
- Automatic state change events

### ✅ Watchlist Tracking
- All watched items
- Price monitoring
- Watcher count
- Automatic updates

### ✅ Purchase Tracking
- Recent purchase history
- Shipping status (pending/shipped/delivered)
- Tracking number extraction
- Seller information
- Automatic status change events

### ✅ Seller Information
For all items:
- Username
- Feedback score
- Positive feedback percentage
- Location (country)
- Profile URL

### ✅ Event System
8 event types for automations:
- `ebay_new_search_result`
- `ebay_became_high_bidder`
- `ebay_outbid`
- `ebay_auction_ending_soon` (15 min threshold)
- `ebay_auction_won`
- `ebay_auction_lost`
- `ebay_item_shipped`
- `ebay_item_delivered`

### ✅ Services
9 services for control:
- `refresh_bids`
- `refresh_watchlist`
- `refresh_purchases`
- `refresh_search`
- `refresh_account`
- `refresh_all`
- `create_search`
- `update_search`
- `delete_search`

### ✅ Sample Dashboards
- Simple bids dashboard (clean view)
- Complete dashboard (all features)
- Both use Markdown for flexibility
- Status indicators with emoji
- Time remaining displays
- Quick refresh buttons
- Responsive layouts

### ✅ Automation Blueprints
5 ready-to-use blueprints:
- Outbid notifications
- Auction ending alerts
- New search result alerts
- Shipping notifications
- Won/lost auction results

### ✅ HACS Compatible
- Proper manifest.json
- hacs.json configuration
- Semantic versioning
- Standard directory structure

## Technical Decisions

### Why ebaysdk-python?
- Mature, maintained library
- Handles eBay's complex XML responses
- Built-in authentication
- Support for all eBay APIs

### Why DataUpdateCoordinator?
- Built-in rate limiting
- Automatic retry logic
- Prevents duplicate API calls
- Efficient state management
- Integration with HA lifecycle

### Why Store for searches?
- Persists across restarts
- Efficient read/write
- Per-config-entry isolation
- Automatic cleanup on removal

### Why separate coordinators?
- Independent update intervals
- Isolated error handling
- Better performance (parallel updates)
- Cleaner code organization

### Why events over state changes?
- Better for one-time actions
- Carries full item context
- No state pollution
- Works with blueprint system

## API Usage Optimization

### Rate Limiting Strategy
1. Configurable update intervals per search
2. Default intervals by data type:
   - Bids: 5 minutes (fast-changing)
   - Watchlist: 10 minutes
   - Purchases: 30 minutes (slow-changing)
   - Searches: 15 minutes (user-configurable)
3. Manual refresh services for on-demand updates
4. Change detection to minimize event spam

### Data Efficiency
1. Uses `outputSelector` to limit response size
2. Only fetches changed data when possible
3. Caches previous state for comparison
4. Batches related API calls

## Storage Structure

### Per-Account Storage
```python
{
    "search_id_1": {
        "search_query": "vintage camera",
        "site": "uk",
        "category_id": "625",
        "min_price": 50.0,
        "max_price": 500.0,
        "listing_type": "both",
        "update_interval": 15
    },
    "search_id_2": {...}
}
```

## Entity ID Structure

```
sensor.ebay_{account_name}_active_bids
sensor.ebay_{account_name}_watchlist
sensor.ebay_{account_name}_purchases
sensor.ebay_{account_name}_search_{search_id}
```

Account names are slugified for entity IDs.

## Extensibility

The integration is designed for easy extension:

### Adding New Data Types
1. Create new coordinator in `coordinator.py`
2. Add sensor class in `sensor.py`
3. Initialize in `__init__.py`
4. Add service for manual refresh

### Adding New Event Types
1. Define constant in `const.py`
2. Add detection logic in relevant coordinator
3. Fire event using `hass.bus.async_fire()`
4. Document in README

### Adding New Services
1. Define service in `services.yaml`
2. Implement handler in `__init__.py`
3. Register in `_async_register_services()`
4. Add to README

## Testing Considerations

### Manual Testing Checklist
- [ ] Add account with valid credentials
- [ ] Create search via UI
- [ ] Create search via service
- [ ] Edit search
- [ ] Delete search
- [ ] Manual refresh services
- [ ] Multi-account setup
- [ ] Event firing on state changes
- [ ] Dashboard rendering
- [ ] Blueprint automation creation

### Edge Cases Handled
- Empty search results
- Missing optional item attributes
- Expired tokens (error handling)
- API timeouts (coordinator retry)
- Invalid search parameters (validation)
- Concurrent search updates
- Account removal cleanup

## Known Limitations

1. **eBay Token Expiration**
   - User tokens expire periodically
   - Must be manually regenerated
   - Future: Implement OAuth refresh flow

2. **API Rate Limits**
   - eBay has call limits (5000/day free tier)
   - Multiple searches consume quota
   - Solution: Adjustable intervals

3. **Historical Data**
   - Only recent purchases shown
   - eBay API limits history depth
   - No built-in archiving

4. **Real-time Updates**
   - Polling-based (not webhooks)
   - Minimum 5-minute intervals
   - Trade-off: API quota vs freshness

## Future Enhancements

### Potential Additions
1. OAuth 2.0 refresh token flow
2. Historical data export
3. Price history graphs
4. Automatic bidding integration
5. Seller blacklist/whitelist
6. Category browser helper
7. Image caching for offline viewing
8. Multi-currency conversion
9. Saved seller searches
10. Advanced filtering (condition, shipping, etc.)

## Dependencies

```python
# From manifest.json
"requirements": [
    "ebaysdk-python==2.2.0"
]

# Home Assistant core (minimum)
"homeassistant": "2024.1.0"
```

## File Structure

```
custom_components/ebay/
├── __init__.py          # Integration setup & services
├── config_flow.py       # UI configuration
├── const.py            # Constants
├── coordinator.py      # Data coordinators
├── ebay_api.py         # API wrapper
├── sensor.py           # Sensor entities
├── manifest.json       # Integration metadata
├── services.yaml       # Service definitions
└── strings.json        # UI translations

dashboards/
├── ebay_bids_simple.yaml    # Simple dashboard
└── ebay_complete.yaml       # Full dashboard

blueprints/automation/
├── ebay_outbid_notification.yaml
├── ebay_auction_ending_soon.yaml
├── ebay_new_search_result.yaml
├── ebay_item_shipped.yaml
└── ebay_auction_result.yaml

Documentation/
├── README.md           # Main documentation
├── USAGE_GUIDE.md     # Detailed usage
├── QUICK_START.md     # Quick setup
└── INFO.md            # This file
```

## Code Quality

### Standards Followed
- Type hints throughout
- Comprehensive docstrings
- Async/await properly used
- Error handling at all API boundaries
- Logging at appropriate levels
- Constants for all magic values
- No hardcoded credentials
- Secure token storage

### Home Assistant Best Practices
- Uses ConfigEntry for setup
- Implements OptionsFlow for configuration
- Uses DataUpdateCoordinator
- Proper entity unique IDs
- Follows naming conventions
- Implements all standard methods
- No blocking I/O in event loop
- Proper cleanup on removal

## Maintenance

### Regular Updates Needed
1. ebaysdk-python version bumps
2. Home Assistant version compatibility
3. eBay API changes (rare)
4. Documentation updates
5. Blueprint improvements

### Version Scheme
Following semantic versioning:
- MAJOR: Breaking changes
- MINOR: New features
- PATCH: Bug fixes

## Performance Characteristics

### Memory Usage
- Minimal (stores config only)
- Item data in coordinator cache
- No persistent image storage
- ~1-2MB per account

### API Calls Per Hour
Default configuration (1 account, 3 searches):
- Bids: 12/hour (5 min interval)
- Watchlist: 6/hour (10 min)
- Purchases: 2/hour (30 min)
- Searches: 12/hour (15 min each × 3)
- **Total: ~32 calls/hour, ~768/day**

Well within free tier limits.

### CPU Usage
- Negligible (mostly I/O wait)
- Async operations
- No heavy processing
- Event firing is lightweight

## Security

### Credential Handling
- Stored in HA's secure config entry
- Never logged
- Not exposed in entity attributes
- Token scoped to user account

### Data Privacy
- All data from user's own account
- No data sent to third parties
- No telemetry
- Runs entirely locally

## License

MIT License - See LICENSE file
Free for personal and commercial use
