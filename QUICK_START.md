# Quick Start Guide

Get up and running with the eBay integration v2.0 in 10 minutes.

## Prerequisites

- Home Assistant 2024.1.0 or newer
- eBay account
- eBay Developer account (free)

## 5-Step Setup

### 1. Get eBay API Credentials (5 minutes)

1. Go to https://developer.ebay.com/
2. Sign in → "My Account" → "Application Keys"
3. Create new application (**Production** environment - important!)
4. Save these 4 values:
   - **App ID** (Client ID)
   - **Dev ID** (Developer ID)
   - **Cert ID** (Client Secret)
   - **User Token** (generate under "User Tokens" tab)
     - Select scopes: `api_scope`, `sell.account`, `sell.inventory`
     - Token expires in 18 months - set a reminder!

💡 **Tip:** See `HOW_TO_GET_API_KEYS.md` for detailed instructions with screenshots

### 2. Install Integration (2 minutes)

**Via HACS:**
1. HACS → Integrations → "⋮" → Custom repositories
2. Add: `https://github.com/ianpleasance/home-assistant-ebay-monitor`
3. Category: Integration
4. Install "eBay"
5. Restart Home Assistant

**Manual:**
1. Copy `custom_components/ebay` to your HA config
2. Restart Home Assistant

### 3. Add Your Account (1 minute)

1. Settings → Devices & Services → "+ Add Integration"
2. Search "eBay"
3. Enter:
   - Account Name: "My eBay"
   - Your 4 API credentials
4. Submit

**Result**: Sensors created instantly!

**Main Sensors (v2.0):**
- `sensor.ebay_my_ebay_active_bids` - Count of active bids
- `sensor.ebay_my_ebay_watchlist` - Count of watched items
- `sensor.ebay_my_ebay_purchases` - Count of purchases
- `sensor.ebay_my_ebay_api_usage` - API rate limit tracking

**Chunk Sensors (created automatically):**
- `sensor.ebay_my_ebay_active_bids_chunk_1` - First 20 bids (items with formatted prices!)
- `sensor.ebay_my_ebay_watchlist_chunk_1` - First 20 watchlist items
- `sensor.ebay_my_ebay_purchases_chunk_1` - First 20 purchases

### 4. Create Your First Search (1 minute)

1. Settings → Devices & Services
2. Find "eBay - My eBay" → Configure
3. "Add New Search"
4. Enter:
   ```
   Search Query: vintage camera
   eBay Site: United Kingdom
   Listing Type: Both
   Update Interval: 15
   ```
5. Submit

**Result**: New sensors created!
- `sensor.ebay_my_ebay_search_{id}` - Main sensor (count)
- `sensor.ebay_my_ebay_search_{id}_chunk_1` - First 20 results

### 5. Add Dashboard (1 minute)

⚠️ **Important:** Use the updated v2.0 dashboard!

1. Copy from `dashboards/dashboard_updated.yaml`
2. Settings → Dashboards → Create new
3. Switch to YAML mode → Paste
4. Replace "atariian" with "my_ebay" (your account name, lowercase with underscores)

**Done!** You're now tracking eBay with all v2.0 features!

## What's Different in v2.0?

### ✨ New Features You'll Love

1. **Formatted Prices** - See `£3.20` instead of `3.2 GBP` everywhere
2. **Unlimited Items** - No more 10-item limit on watchlist!
3. **Smart Sorting** - Items ending soonest always show first
4. **Reliable Events** - All automations work after restart
5. **Chunk Sensors** - Items split across sensors (20 per chunk)

### 📊 Understanding Chunk Sensors

**Example:** If you have 45 active bids:
- Main sensor: `sensor.ebay_my_ebay_active_bids` 
  - State: `45` (total count)
  - Attributes: `chunk_count: 3`, list of chunk sensors
- Chunk 1: `sensor.ebay_my_ebay_active_bids_chunk_1`
  - State: `20` (items in this chunk)
  - Attributes: Items 1-20 (ending soonest!)
- Chunk 2: `sensor.ebay_my_ebay_active_bids_chunk_2`
  - State: `20`
  - Attributes: Items 21-40
- Chunk 3: `sensor.ebay_my_ebay_active_bids_chunk_3`
  - State: `5`
  - Attributes: Items 41-45

💡 **Tip:** Most urgent items are always in chunk_1!

## Quick Automations (v2.0)

### Get Outbid Alert

Developer Tools → Services:

```yaml
service: notify.mobile_app_yourphone
data:
  title: "You've been outbid!"
  message: "{{ trigger.event.data.item.title }} - {{ trigger.event.data.item.formatted_price }}"
```

Then create automation:
```yaml
automation:
  - alias: "eBay - Outbid Alert"
    trigger:
      - platform: event
        event_type: ebay_outbid
    action:
      - service: notify.mobile_app_yourphone
        data:
          title: "You've been outbid!"
          message: "🔨 {{ trigger.event.data.item.title }} - {{ trigger.event.data.item.formatted_price }}"
          data:
            url: "{{ trigger.event.data.item.item_url }}"
```

### Auction Ending Alert

```yaml
automation:
  - alias: "eBay - Ending Soon"
    trigger:
      - platform: event
        event_type: ebay_auction_ending_soon
    action:
      - service: notify.mobile_app_yourphone
        data:
          title: "Auction ending soon!"
          message: "⏰ {{ trigger.event.data.item.title }} - {{ trigger.event.data.item.formatted_price }}"
```

### New Search Result Alert

```yaml
automation:
  - alias: "eBay - New Result"
    trigger:
      - platform: event
        event_type: ebay_new_search_result
    action:
      - service: notify.mobile_app_yourphone
        data:
          title: "New eBay listing!"
          message: "🔍 {{ trigger.event.data.item.title }} - {{ trigger.event.data.item.formatted_price }}"
          data:
            image: "{{ trigger.event.data.item.image_url }}"
```

💡 **See `automations_updated.yaml` for complete examples!**

## Common First Searches

```yaml
# Vintage cameras under £500
Search: vintage Leica camera
Category: 625
Max Price: 500
Type: Auction

# Electronics deals
Search: iPhone 14 Pro
Category: 293
Type: Buy It Now

# Collectibles
Search: vintage Star Wars
Category: 1
Min Price: 20
Type: Both
```

## View Your Data (v2.0)

### Check Main Sensors
Developer Tools → States → Filter: `ebay`

Click `sensor.ebay_my_ebay_active_bids` to see:
- Total count
- Chunk count
- List of chunk sensors

### Check Chunk Sensors (See Actual Items)
Click `sensor.ebay_my_ebay_active_bids_chunk_1` to see:
- First 20 items (ending soonest!)
- Each item has `formatted_price` field
- Full item details

### Using Formatted Prices
In templates, use:
```yaml
{{ item.formatted_price }}  # Shows: £3.20
```

Instead of:
```yaml
{{ item.current_price.value }}  # Shows: 3.2 (old way)
```

## Refresh Data Manually

Developer Tools → Services:
```yaml
# Refresh all data for one account
service: ebay.refresh_account
data:
  account: "My eBay"

# Refresh specific data type
service: ebay.refresh_bids
data:
  account: "My eBay"

# Check API usage
service: ebay.get_rate_limits
data:
  account: "My eBay"
```

## Test Your Setup

### 1. Check Sensors Created
Developer Tools → States → Filter: `ebay`

You should see:
- Main sensors (count only)
- Chunk sensors (with items)
- API usage sensor

### 2. Test an Event
Place a test bid on eBay, then check:

Home Assistant → Developer Tools → Events → Listen:
- Event type: `ebay_became_high_bidder`
- Click "Start Listening"

You should see the event fire with `formatted_price` field!

### 3. View Dashboard
Navigate to your new dashboard - you should see:
- Formatted prices everywhere (`£3.20`)
- All your bids/watchlist items (no limits!)
- Items sorted by ending soonest

## Next Steps

- 📖 Read [README.md](README.md) for complete documentation
- 🔄 See [DASHBOARD_MIGRATION.md](DASHBOARD_MIGRATION.md) to update old dashboards
- 🤖 Check [AUTOMATION_UPDATES.md](AUTOMATION_UPDATES.md) for automation examples
- 📊 Read [INFO.md](INFO.md) for technical details

## Troubleshooting

### No data appearing?
- Wait 5 minutes for first update
- Check logs: Settings → System → Logs
- Manually refresh: `ebay.refresh_account` service
- Verify API credentials are for **Production** environment

### No chunk sensors created?
- Check if you have any bids/watchlist items
- Chunk sensors only create if you have items
- Reload the integration after adding items

### Token expired?
- Regenerate token at developer.ebay.com (expires every 18 months)
- Select same scopes: `api_scope`, `sell.account`, `sell.inventory`
- Update integration configuration with new token

### Events not firing?
- **v2.0 fixed this!** Events now work after restart
- On first run, all items will trigger events once (expected)
- Check logs for event confirmations
- Verify event names: `ebay_auction_won` (not `ebay_won`)

### Search returns nothing?
- Try broader search terms
- Remove price filters temporarily
- Check on ebay.co.uk that results exist
- Wait 15 minutes for first update

### Dashboard broken after upgrade?
- You need to update dashboard templates for v2.0
- See [DASHBOARD_MIGRATION.md](DASHBOARD_MIGRATION.md)
- Main change: Use chunk sensors instead of main sensor items
- Use `formatted_price` instead of `current_price.value`

### "Items" attribute empty in main sensor?
- **This is correct in v2.0!** Items moved to chunk sensors
- Check chunk sensors like `sensor.ebay_account_bids_chunk_1`
- Main sensors only show counts and chunk info

## Performance Tips

### API Usage
Default setup uses ~768 API calls/day (well within 5000/day free tier):
- Bids: every 5 minutes
- Watchlist: every 10 minutes
- Purchases: every 30 minutes
- Searches: every 15 minutes (configurable)

### Optimize if Needed
- Increase search intervals (15 → 30 minutes)
- Reduce number of searches
- Check usage: `ebay.get_rate_limits` service

### Memory Usage
- Base: ~1-3MB per account
- State files: ~100KB per account
- Chunk sensors: ~50KB each
- 100 watchlist items = ~300KB total (no problem!)

## Support

- 🐛 Issues: [GitHub Issues](https://github.com/ianpleasance/home-assistant-ebay-monitor/issues)
- 📖 Documentation: [README.md](README.md)
- 💡 Examples: Check `dashboards/` and `automations/` folders
- ⭐ Like it? Star the repo on GitHub!

## Version Info

**Current Version:** 2.0.0

**What Changed:**
- ✅ Formatted prices (`£3.20`)
- ✅ Chunked sensors (unlimited items)
- ✅ Persistent state (events work after restart)
- ✅ Auto sorting (ending soonest first)
- ⚠️ Breaking changes (see migration guides)

**Upgrading from v1.x?**
See [DASHBOARD_MIGRATION.md](DASHBOARD_MIGRATION.md) for required template updates.
