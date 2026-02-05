# eBay Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![License](https://img.shields.io/github/license/ianpleasance/home-assistant-ebay-monitor)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](https://github.com/ianpleasance/home-assistant-ebay-monitor/releases)

A comprehensive Home Assistant integration for monitoring your eBay account activity. Track active bids, watchlist items, purchases, and create custom search alerts - all from your Home Assistant dashboard.

## ✨ What's New in v2.0

- 🎯 **Formatted Prices** - All prices now display as `£3.20` instead of `3.2 GBP`
- 🔄 **Reliable Events** - Events fire correctly after Home Assistant restarts
- 📊 **Unlimited Items** - No more 16KB database limits (100+ watchlist items supported)
- ⚡ **Smart Sorting** - Items automatically sorted by urgency (ending soonest first)
- 🔥 **All Events Working** - Became high bidder, won, lost, shipped, delivered events now reliable

⚠️ **Important:** v2.0 includes breaking changes. See [Migration Guide](#migrating-from-v1x) below.

## Features

- 🔍 **Saved Searches** - Create and manage multiple eBay searches with automatic updates
- 🚀 **Modern Browse API** - Uses eBay's latest API with better rate limits and OAuth 2.0
- 🎯 **Active Bids** - Monitor all your active bids with real-time status updates
- 👁️ **Watchlist** - Track unlimited items (no 10-item limit)
- 📦 **Purchases** - Keep tabs on your purchase history and shipping status
- 🔔 **Smart Alerts** - Automated notifications for bid changes, auction endings, and shipping updates
- 🔄 **Multi-Account Support** - Manage multiple eBay accounts from one integration
- 🎨 **Beautiful Dashboards** - Pre-built dashboard templates included
- 📊 **API Tracking** - Monitor your API usage and avoid rate limits
- 💾 **Persistent State** - Events work reliably even after restarts
- 💰 **Formatted Prices** - Clean price display with currency symbols

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/ianpleasance/home-assistant-ebay-monitor`
6. Select category "Integration"
7. Click "Add"
8. Search for "eBay" in HACS
9. Click "Download"
10. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/ebay` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant

## Configuration

### Getting eBay API Credentials

Before you can use this integration, you need to obtain eBay API credentials:

1. Go to [eBay Developer Program](https://developer.ebay.com/)
2. Sign in or create an account
3. Navigate to "My Account" → "Application Keys"
4. Create a new application (choose **Production** environment)
5. You'll receive:
   - **App ID (Client ID)**
   - **Dev ID**
   - **Cert ID (Client Secret)**
6. Generate a **User Token** for your account (under "User Tokens" section)
   - Select scopes: `api_scope`, `sell.account`, `sell.inventory`
   - Token expires after 18 months - set a reminder!

📖 **Detailed guide:** See `HOW_TO_GET_API_KEYS.md` in the integration folder

### Adding the Integration

1. In Home Assistant, go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "eBay"
4. Enter a name for your account (e.g., "My Personal eBay")
5. Enter your API credentials:
   - App ID (Client ID)
   - Dev ID
   - Cert ID (Client Secret)
   - User Token
6. Click Submit

## Managing Searches

### Via UI (Recommended)

1. Go to **Settings** → **Devices & Services**
2. Find your eBay integration
3. Click **Configure**
4. Select "Add New Search" or edit existing searches
5. Configure search parameters:
   - **Search Query**: Keywords to search for
   - **eBay Site**: Which country's eBay to search (UK, US, etc.)
   - **Category ID**: Optional category filter
   - **Price Range**: Min/max price filters
   - **Listing Type**: Auction, Buy It Now, or both
   - **Update Interval**: How often to check (in minutes)

### Via Services

You can also create searches programmatically using services:

```yaml
service: ebay.create_search
data:
  account: "My Personal eBay"
  search_query: "vintage camera"
  site: "uk"
  min_price: 50
  max_price: 200
  listing_type: "auction"
  update_interval: 15
```

## Sensors

### Main Sensors (v2.0)

The integration creates main sensors that show counts and chunk information:

- `sensor.ebay_{account}_active_bids` - Total count of active bids
- `sensor.ebay_{account}_watchlist` - Total count of watched items
- `sensor.ebay_{account}_purchases` - Total count of recent purchases
- `sensor.ebay_{account}_search_{query}` - Total results for each saved search
- `sensor.ebay_{account}_api_usage` - API rate limit tracking

**Main sensor attributes include:**
- `item_count` - Total number of items
- `chunk_count` - Number of chunk sensors created
- `chunk_sensors` - List of chunk sensor entity IDs

### Chunk Sensors (v2.0)

Items are stored in chunk sensors (20 items each) to avoid database limits:

- `sensor.ebay_{account}_active_bids_chunk_1` - First 20 bids (ending soonest)
- `sensor.ebay_{account}_active_bids_chunk_2` - Next 20 bids
- `sensor.ebay_{account}_watchlist_chunk_1` - First 20 watchlist items
- `sensor.ebay_{account}_search_{query}_chunk_1` - First 20 search results

**Chunk sensor attributes include:**
- `items` - Array of up to 20 items (with formatted_price!)
- `chunk_number` - Which chunk this is (1, 2, 3, etc.)
- `chunk_start` / `chunk_end` - Item range in this chunk
- `parent_sensor` - Link back to main sensor

**Example:** 97 watchlist items creates:
- 1 main sensor (`item_count: 97`)
- 5 chunk sensors (20+20+20+20+17 items)

## Services

### Refresh Services

```yaml
# Refresh specific data
ebay.refresh_bids
ebay.refresh_watchlist
ebay.refresh_purchases
ebay.refresh_search

# Refresh all data for an account
ebay.refresh_account

# Refresh everything
ebay.refresh_all

# Check API usage (NEW in v2.0)
ebay.refresh_api_usage
ebay.get_rate_limits
```

### Search Management Services

```yaml
# Create a new search
ebay.create_search

# Update existing search
ebay.update_search

# Delete a search
ebay.delete_search
```

## Events

The integration fires events that you can use for automations. **All events now work reliably after Home Assistant restarts (v2.0):**

- `ebay_new_search_result` - New item matches your search
- `ebay_became_high_bidder` - You became the high bidder ✅ Now works after restart
- `ebay_outbid` - You were outbid
- `ebay_auction_ending_soon` - Auction ending in 1 hour
- `ebay_auction_won` - You won an auction ✅ Now works after restart
- `ebay_auction_lost` - You lost an auction ✅ Now works after restart
- `ebay_item_shipped` - Purchase was shipped ✅ Now works after restart
- `ebay_item_delivered` - Purchase was delivered ✅ Now works after restart

**All events now include `formatted_price` field!**

## Dashboards

Updated dashboards are included in the `dashboards/` folder:

### Activity Dashboard (`dashboard_updated.yaml`)

Comprehensive view with tabs for:
- Overview with summary statistics
- Active bids with status (using chunk sensors)
- Watchlist items (unlimited items supported)
- Purchase history with tracking
- Formatted prices throughout

### Searches Dashboard (`searches_dashboard_updated.yaml`)

Focused search view with:
- Search results grid
- Top results from all searches
- Search management
- Statistics and API usage

To use these dashboards:

1. Copy the desired YAML file content
2. Go to Home Assistant → **Settings** → **Dashboards**
3. Create a new dashboard or edit an existing one
4. Switch to YAML mode
5. Paste the content
6. Update entity IDs to match your account name

## Example Automations (v2.0)

### Alert When Outbid

```yaml
automation:
  - alias: "eBay - Notify When Outbid"
    trigger:
      - platform: event
        event_type: ebay_outbid
    action:
      - service: notify.mobile_app
        data:
          title: "You've been outbid!"
          message: "🔨 {{ trigger.event.data.item.title }} - Current price: {{ trigger.event.data.item.formatted_price }}"
          data:
            url: "{{ trigger.event.data.item.item_url }}"
```

### Alert for New Search Results

```yaml
automation:
  - alias: "eBay - New Search Result"
    trigger:
      - platform: event
        event_type: ebay_new_search_result
    condition:
      - condition: template
        value_template: "{{ trigger.event.data.search_query == 'vintage camera' }}"
    action:
      - service: notify.mobile_app
        data:
          title: "New eBay listing found!"
          message: "🔍 {{ trigger.event.data.item.title }} - {{ trigger.event.data.item.formatted_price }}"
          data:
            image: "{{ trigger.event.data.item.image_url }}"
            url: "{{ trigger.event.data.item.item_url }}"
```

### Auction Ending Soon Reminder

```yaml
automation:
  - alias: "eBay - Auction Ending Soon"
    trigger:
      - platform: event
        event_type: ebay_auction_ending_soon
    action:
      - service: notify.mobile_app
        data:
          title: "Auction ending soon!"
          message: "⏰ {{ trigger.event.data.item.title }} - {{ trigger.event.data.item.formatted_price }} - {{ trigger.event.data.minutes_remaining }} minutes left"
          data:
            url: "{{ trigger.event.data.item.item_url }}"
            tag: "ebay_ending_{{ trigger.event.data.item.item_id }}"
```

### Package Shipped Notification

```yaml
automation:
  - alias: "eBay - Package Shipped"
    trigger:
      - platform: event
        event_type: ebay_item_shipped
    action:
      - service: notify.mobile_app
        data:
          title: "Your eBay package has shipped!"
          message: "📦 {{ trigger.event.data.item.title }}{% if trigger.event.data.item.tracking_number %} - Tracking: {{ trigger.event.data.item.tracking_number }}{% endif %}"
```

## Item Attributes (v2.0)

Each item (bid, watchlist item, or purchase) includes the following attributes:

```yaml
item_id: "123456789"
title: "Vintage Camera"
seller_username: "camera_shop_uk"
seller_feedback_score: 1247
seller_positive_percent: 99.8
seller_location: "United Kingdom"
seller_url: "https://www.ebay.co.uk/usr/camera_shop_uk"
current_price:
  value: 125.50
  currency: "GBP"
formatted_price: "£125.50"  # NEW in v2.0 - Use this for display!
is_high_bidder: true  # For bids only
reserve_met: true  # For auctions
end_time: "2025-01-20T15:30:00Z"
time_remaining: "2 days 4 hours"
image_url: "https://..."
item_url: "https://www.ebay.co.uk/itm/123456789"
listing_type: "Auction"
bid_count: 12  # For bids
watchers: 45  # For watchlist
shipping_status: "shipped"  # For purchases: pending/shipped/delivered
tracking_number: "1Z999..."  # For purchases
```

## Migrating from v1.x

⚠️ **v2.0 includes breaking changes** that require updates to your dashboards and automations.

### Dashboard Changes Required

**Old (broken):**
```yaml
{% set items = state_attr('sensor.ebay_account_active_bids', 'items') %}
{% for item in items %}
  {{ item.current_price.value }}
{% endfor %}
```

**New (required):**
```yaml
{% set chunk_sensors = state_attr('sensor.ebay_account_active_bids', 'chunk_sensors') %}
{% for chunk_sensor in chunk_sensors %}
  {% set items = state_attr(chunk_sensor, 'items') %}
  {% for item in items %}
    {{ item.formatted_price }}
  {% endfor %}
{% endfor %}
```

### Automation Changes Required

**Old (broken):**
```yaml
message: "Price: {{ trigger.event.data.item.current_price.value }}"
```

**New (required):**
```yaml
message: "Price: {{ trigger.event.data.item.formatted_price }}"
```

### Event Name Changes

- `ebay_won` → `ebay_auction_won`
- `ebay_lost` → `ebay_auction_lost`

📖 **Detailed migration guide:** See `DASHBOARD_MIGRATION.md` and `AUTOMATION_UPDATES.md`

## Troubleshooting

### Integration Not Loading

- Ensure you've restarted Home Assistant after installation
- Check the Home Assistant logs for error messages
- Verify your API credentials are correct
- Ensure you selected **Production** environment when creating your eBay app

### No Data Appearing

- Make sure your eBay token has the correct scopes (`api_scope`, `sell.account`, `sell.inventory`)
- Check that you have active bids/watchlist items
- Try manually refreshing using the `ebay.refresh_account` service
- Check logs for API errors

### Events Not Firing

- **v2.0 fixed this!** Events now persist across restarts
- On first run after upgrade, all existing items will trigger events once (expected)
- Check Home Assistant logs for event firing confirmations
- Verify automation trigger event types match exactly

### Rate Limiting

The eBay API has rate limits (5000 calls/day on free tier). If you're experiencing issues:
- Increase the update intervals for your searches (default: 15 minutes)
- Reduce the number of saved searches
- Avoid calling refresh services too frequently
- Use `ebay.get_rate_limits` to monitor your usage

### Chunk Sensors Not Updating

- Chunk sensors are created at integration startup
- If item count changes significantly, reload the integration
- Check that main sensor shows correct `chunk_count`

## Performance

### API Usage (Default Configuration)

With 1 account and 3 searches:
- **Bids:** 12 calls/hour (5 min intervals)
- **Watchlist:** 6 calls/hour (10 min)
- **Purchases:** 2 calls/hour (30 min)
- **Searches:** 12 calls/hour (15 min × 3)
- **Total:** ~32 calls/hour, ~768 calls/day

Well within the 5000/day free tier limit.

### Memory & Storage

- Base integration: ~1-3MB per account
- State persistence: ~100KB per account
- Chunk sensors: Minimal overhead (~50KB each)
- No database size issues regardless of item count

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the Apache 2.0 License - see the LICENSE file for details.

## Disclaimer

This integration is not affiliated with or endorsed by eBay. Use at your own risk.

## Support

For issues, feature requests, or questions, please [open an issue](https://github.com/ianpleasance/home-assistant-ebay-monitor/issues) on GitHub.

## Changelog

### Version 2.0.0 (Current)
- ✅ **Formatted Prices** - All items include `formatted_price` field (e.g., `£3.20`)
- ✅ **Persistent State** - Events fire reliably after Home Assistant restarts (60-day retention)
- ✅ **Chunked Sensors** - Support unlimited items (20 per chunk, no database limits)
- ✅ **Auto Sorting** - Items sorted by urgency (bids/watchlist/searches by end_time, purchases by date)
- ✅ **Reliable Events** - All 8 event types now work correctly after restart
- ✅ **Updated Dashboards** - New templates using chunk sensors and formatted prices
- ✅ **Updated Automations** - Examples using formatted prices
- ⚠️ **Breaking Changes** - Dashboard and automation templates require updates
- 📊 **Code Quality** - +583 lines of code (+28%), comprehensive documentation

### Version 1.0.0 (Previous)
- Multi-account support
- Saved search management with UI
- Active bids monitoring
- Watchlist tracking
- Purchase history with shipping status
- Event-driven automation system
- Pre-built dashboards
- Comprehensive services for manual refresh
- Seller information including location and feedback

## Credits

Developed by [@ianpleasance](https://github.com/ianpleasance)

If you find this integration useful, consider starring the repository on GitHub! ⭐
