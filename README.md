# eBay Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![Version](https://img.shields.io/badge/version-2.3.0-blue.svg)](https://github.com/ianpleasance/home-assistant-ebay-monitor)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)

A comprehensive Home Assistant custom integration for monitoring your eBay account activity. Track active bids, watchlist items, purchases, and create custom search alerts — all from your Home Assistant dashboard.

---

## Features

- **Saved Searches** — Create and manage multiple eBay searches with automatic new-item detection
- **Active Bids** — Monitor all your active bids with real-time high bidder and reserve status
- **Watchlist** — Track items you are watching with price and watcher count
- **Purchases** — Keep tabs on your purchase history and shipping status
- **Smart Alerts** — Event-driven notifications for bid changes, auction endings, won/lost results, and shipping updates
- **Multi-Account Support** — Manage multiple eBay accounts independently from one integration
- **Pre-built Dashboards** — Ready-to-use dashboard templates included
- **API Usage Tracking** — Monitor your eBay API usage to avoid rate limits
- **Verified Won/Lost Detection** — Auction results are verified via the eBay API with a grace period to prevent false alerts from transient API glitches or last-minute bids

---

## Requirements

- Home Assistant 2024.1.0 or newer
- An eBay account
- A free eBay Developer account with API credentials

---

## Installation

### Via HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Go to **Integrations** → **⋮** → **Custom repositories**
3. Add `https://github.com/ianpleasance/home-assistant-ebay-monitor` as category **Integration**
4. Search for **eBay** and click **Download**
5. Restart Home Assistant
6. Go to **Settings → Devices & Services → Add Integration** and search for **eBay**

### Manual

1. Copy the `custom_components/ebay` folder to your `<config>/custom_components/` directory
2. Restart Home Assistant
3. Go to **Settings → Devices & Services → Add Integration** and search for **eBay**

---

## Quick Start

### 1. Get eBay API Credentials

1. Go to [https://developer.ebay.com/](https://developer.ebay.com/)
2. Sign in → **My Account** → **Application Keys**
3. Create a new application — choose **Production** environment, not Sandbox
4. Note your four credentials:
   - **App ID** (Client ID)
   - **Dev ID**
   - **Cert ID** (Client Secret)
   - **User Token** — generate this from the **User Tokens** tab

> User tokens expire periodically. You will need to regenerate them at the eBay Developer Portal and update the integration configuration when this happens.

### 2. Add the Integration

1. **Settings → Devices & Services → + Add Integration**
2. Search for **eBay**
3. Enter an **Account Name** (e.g. `Personal` or `Business`)
4. Enter your four API credentials
5. Click **Submit**

Three sensors are created immediately:
- `sensor.ebay_{account}_active_bids`
- `sensor.ebay_{account}_watchlist`
- `sensor.ebay_{account}_purchases`

### 3. Create Your First Search

1. **Settings → Devices & Services** → find your eBay integration → **Configure**
2. Select **Add New Search**
3. Fill in the parameters and click **Submit**

A new sensor is created: `sensor.ebay_{account}_search_{search_id}`

### 4. Add a Dashboard

Copy a dashboard from the `dashboards/` folder, create a new dashboard in Home Assistant, switch to YAML mode, paste the content, and replace the example account name with yours.

---

## Configuration

### Search Parameters

| Parameter | Description |
|---|---|
| Search Query | Keywords to search for (e.g. `vintage Leica camera`) |
| eBay Site | Country site to search — uk, us, de, fr, it, es, au, ca |
| Category ID | Optional eBay category number (find in eBay URLs, e.g. `625` for Cameras) |
| Min Price | Only show items above this price |
| Max Price | Only show items below this price |
| Listing Type | `auction`, `buy_it_now`, or `both` |
| Update Interval | How often to check in minutes (5–1440, default 15) |

### Finding Category IDs

Browse to a category on eBay and look at the URL: `ebay.co.uk/b/Cameras-Photography/625` — the trailing number is the category ID. Common IDs: Electronics (293), Cameras & Photography (625), Collectibles (1), Home & Garden (11700), Sporting Goods (888).

### Managing Searches via Services

```yaml
# Create a search
service: ebay.create_search
data:
  account: "Personal"
  search_query: "vintage Leica camera"
  site: "uk"
  category_id: "625"
  min_price: 100
  max_price: 1000
  listing_type: "auction"
  update_interval: 15

# Update a search
service: ebay.update_search
data:
  account: "Personal"
  search_id: "your_search_id"
  max_price: 800

# Delete a search
service: ebay.delete_search
data:
  account: "Personal"
  search_id: "your_search_id"
```

---

## Sensors

### Summary Sensors

Each account gets these sensors automatically:

| Entity | State | Key Attributes |
|---|---|---|
| `sensor.ebay_{account}_active_bids` | Bid count | `item_count`, `chunk_sensors`, `last_updated` |
| `sensor.ebay_{account}_watchlist` | Watched item count | `item_count`, `chunk_sensors`, `last_updated` |
| `sensor.ebay_{account}_purchases` | Purchase count | `item_count`, `chunk_sensors`, `last_updated` |
| `sensor.ebay_{account}_search_{id}` | Result count | `search_query`, `auction_count`, `buy_now_count`, `last_updated` |
| `sensor.ebay_{account}_api_usage` | Browse API usage % | `browse_used`, `browse_remaining`, `browse_limit` |

### Chunk Sensors

Because HA limits attribute size, item data is split across chunk sensors (up to 20 items each):

- `sensor.ebay_{account}_active_bids_chunk_1`, `_chunk_2`, ...
- `sensor.ebay_{account}_watchlist_chunk_1`, ...
- `sensor.ebay_{account}_purchases_chunk_1`, ...
- `sensor.ebay_{account}_search_{id}_chunk_1`, ...

Each chunk sensor has an `items` attribute containing the full item data for that chunk.

### Item Attributes

All items include:

```yaml
item_id: "123456789"
title: "Vintage Leica M3 Camera"
seller_username: "camera_collector"
seller_feedback_score: 2500
seller_positive_percent: 99.9
seller_location: "United Kingdom"
seller_url: "https://www.ebay.co.uk/usr/camera_collector"
current_price:
  value: 850.00
  currency: "GBP"
formatted_price: "£850.00"
item_url: "https://www.ebay.co.uk/itm/123456789"
image_url: "https://..."
listing_type: "Auction"
end_time: "2025-01-20T18:30:00Z"
time_remaining: "2 days 3 hours"
```

Additional fields by type:

| Type | Additional attributes |
|---|---|
| Bids | `is_high_bidder`, `reserve_met`, `bid_count` |
| Watchlist | `watchers` |
| Purchases | `shipping_status` (pending/shipped/delivered), `tracking_number` |

---

## Events

The integration fires the following events for use in automations:

| Event | When fired |
|---|---|
| `ebay_new_search_result` | A new item appears in a saved search |
| `ebay_became_high_bidder` | You become the highest bidder on an item |
| `ebay_outbid` | Someone outbids you |
| `ebay_auction_ending_soon` | An auction you're bidding on ends within 15 minutes |
| `ebay_auction_won` | You won an auction (verified via eBay API) |
| `ebay_auction_lost` | You lost an auction (verified via eBay API) |
| `ebay_new_purchase` | A new item appears in your purchase history |
| `ebay_item_shipped` | A purchase shipping status changes to shipped |
| `ebay_item_delivered` | A purchase shipping status changes to delivered |

All events include an `account` field and an `item` dict with the full item data. `ebay_new_search_result` also includes `search_id` and `search_query`. `ebay_auction_ending_soon` also includes `minutes_remaining`.

### Won/Lost Verification

When an item disappears from your active bids list, the integration does not fire a won/lost event immediately. Instead it waits two poll cycles (approximately 10 minutes at the default interval) to confirm the item has genuinely gone. This prevents false alerts from transient eBay API glitches. Once the grace period has elapsed, the eBay API is queried for the authoritative final result including the actual high bidder, so last-minute bids that weren't reflected in the last poll are handled correctly.

---

## Services

### Refresh Services

```yaml
ebay.refresh_bids        # Refresh bids for a specific account
ebay.refresh_watchlist   # Refresh watchlist for a specific account
ebay.refresh_purchases   # Refresh purchases for a specific account
ebay.refresh_search      # Refresh a specific search
ebay.refresh_account     # Refresh all data for an account
ebay.refresh_all         # Refresh everything across all accounts
```

### Search Management

```yaml
ebay.create_search   # Create a new saved search
ebay.update_search   # Update an existing search's parameters
ebay.delete_search   # Delete a saved search
```

### Other

```yaml
ebay.get_rate_limits      # Return API usage statistics
ebay.refresh_api_usage    # Refresh the API usage sensor
```

---

## Example Automations

### Outbid Alert

```yaml
automation:
  - alias: "eBay — Outbid notification"
    trigger:
      - platform: event
        event_type: ebay_outbid
    action:
      - service: notify.mobile_app_my_phone
        data:
          title: "You've been outbid!"
          message: >
            {{ trigger.event.data.item.title }}
            — current price: {{ trigger.event.data.item.formatted_price }}
          data:
            url: "{{ trigger.event.data.item.item_url }}"
```

### Auction Ending Soon

```yaml
automation:
  - alias: "eBay — Auction ending soon"
    trigger:
      - platform: event
        event_type: ebay_auction_ending_soon
    action:
      - service: notify.mobile_app_my_phone
        data:
          title: "Auction ending in {{ trigger.event.data.minutes_remaining }} minutes"
          message: "{{ trigger.event.data.item.title }}"
          data:
            url: "{{ trigger.event.data.item.item_url }}"
            tag: "ebay_ending_{{ trigger.event.data.item.item_id }}"
```

### New Search Result

```yaml
automation:
  - alias: "eBay — New search result"
    trigger:
      - platform: event
        event_type: ebay_new_search_result
    condition:
      - condition: template
        value_template: "{{ trigger.event.data.search_query == 'vintage Leica camera' }}"
      - condition: template
        value_template: "{{ trigger.event.data.item.current_price.value < 500 }}"
    action:
      - service: notify.mobile_app_my_phone
        data:
          title: "New eBay listing — {{ trigger.event.data.item.formatted_price }}"
          message: "{{ trigger.event.data.item.title }}"
          data:
            image: "{{ trigger.event.data.item.image_url }}"
            url: "{{ trigger.event.data.item.item_url }}"
```

### Package Shipped

```yaml
automation:
  - alias: "eBay — Package shipped"
    trigger:
      - platform: event
        event_type: ebay_item_shipped
    action:
      - service: notify.mobile_app_my_phone
        data:
          title: "Your eBay package has shipped"
          message: >
            {{ trigger.event.data.item.title }}
            {% if trigger.event.data.item.tracking_number %}
            — Tracking: {{ trigger.event.data.item.tracking_number }}
            {% endif %}
```

### Auction Won/Lost

```yaml
automation:
  - alias: "eBay — Auction result"
    trigger:
      - platform: event
        event_type: ebay_auction_won
      - platform: event
        event_type: ebay_auction_lost
    action:
      - service: notify.mobile_app_my_phone
        data:
          title: >
            {% if trigger.event_type == 'ebay_auction_won' %}
            You won the auction!
            {% else %}
            Auction lost
            {% endif %}
          message: "{{ trigger.event.data.item.title }}"
          data:
            url: "{{ trigger.event.data.item.item_url }}"
```

### Advanced — High Reputation Sellers Only

```yaml
automation:
  - alias: "eBay — High reputation sellers only"
    trigger:
      - platform: event
        event_type: ebay_new_search_result
    condition:
      - condition: template
        value_template: "{{ trigger.event.data.item.seller_feedback_score > 1000 }}"
      - condition: template
        value_template: "{{ trigger.event.data.item.seller_positive_percent > 99.0 }}"
    action:
      - service: notify.mobile_app_my_phone
        data:
          title: "Trusted seller listing found"
          message: "{{ trigger.event.data.item.title }} — {{ trigger.event.data.item.formatted_price }}"
```

### Advanced — Add Auction End to Calendar

```yaml
automation:
  - alias: "eBay — Add auction to calendar"
    trigger:
      - platform: event
        event_type: ebay_auction_ending_soon
    action:
      - service: calendar.create_event
        data:
          calendar: "calendar.ebay_auctions"
          summary: "Auction ending: {{ trigger.event.data.item.title }}"
          description: "{{ trigger.event.data.item.item_url }}"
          start: "{{ trigger.event.data.item.end_time }}"
          end: "{{ trigger.event.data.item.end_time }}"
```

---

## Blueprints

Five ready-to-use automation blueprints are included in the `blueprints/automation/` folder:

- **ebay_outbid_notification** — Alert when outbid
- **ebay_auction_ending_soon** — 15-minute auction warning
- **ebay_new_search_result** — New item matches a search
- **ebay_item_shipped** — Package shipped notification
- **ebay_auction_result** — Won/lost result notification

To use: **Settings → Automations → + Create Automation → Start with a blueprint** and select an eBay blueprint.

---

## Multiple Accounts

Add the integration multiple times with different account names. Each account creates its own independent set of sensors, searches, and storage. You can show all accounts side by side on a single dashboard by referencing both sets of entity IDs.

---

## Troubleshooting

**Integration not loading** — Restart Home Assistant after installation and check the logs under Settings → System → Logs for error details.

**No data in sensors** — Wait up to 5 minutes for the first data fetch. Try a manual refresh via `ebay.refresh_account`. Check that your eBay token has not expired.

**Token expired** — Regenerate your User Token at developer.ebay.com under the User Tokens tab, then update the integration configuration.

**Search returns no results** — Try broader search terms, remove price filters, and verify the search returns results directly on ebay.co.uk.

**False auction won/lost alerts** — These should be rare after version 2.3.0 which introduced API-verified results with a grace period. If you still see them, check whether `GetSingleItem` is returning data in your HA logs.

**Rate limiting (HTTP 429)** — Increase update intervals for your searches and reduce the total number of active searches.

---

## API Usage and Rate Limits

Default API calls with one account and three searches:

| Data type | Interval | Calls/hour |
|---|---|---|
| Bids | 5 min | 12 |
| Watchlist | 10 min | 6 |
| Purchases | 30 min | 2 |
| Each search | 15 min | 4 |

Three searches totals approximately 32 calls/hour, well within eBay's free tier limits.

The `sensor.ebay_{account}_api_usage` sensor shows real-time API usage pulled from eBay's Analytics API (requires OAuth to be working).

---

## Version History

| Version | Changes |
|---|---|
| 2.3.0 | Added `device_info` to all sensor classes; `SensorStateClass.MEASUREMENT` on all count sensors; native datetime `last_updated` on all sensors; HTTP timeouts on all API call sites; removed unused `_create_chunks()` function; grace period queue for won/lost detection to prevent false alerts from API glitches and last-minute bids; removed unbounded search state trim that caused previously-seen items to re-alert; 7 new translation languages (da, fi, ja, no, pl, pt, sv — now all 13 supported); `homeassistant: 2024.1.0` added to manifest; `info.md` and `CHANGELOG.md` added; `QUICK_START.md` and `USAGE_GUIDE.md` folded into README |
| 2.2.0 | GetSingleItem API verification for auction won/lost; pagination support for large bid/watchlist/purchase lists; caching of MyeBay API responses to avoid duplicate calls; per-account and per-search state persistence across restarts; 6 translation languages (de, en, es, fr, it, nl) |
| 1.0.0 | Initial release — multi-account support, saved searches, active bids, watchlist, purchases, event system, dashboards, blueprints |

---

## License

Apache License 2.0 — see [LICENSE](LICENSE)

## Disclaimer

This integration is not affiliated with or endorsed by eBay. Use at your own risk.

## Support

For issues and feature requests please [open an issue](https://github.com/ianpleasance/home-assistant-ebay-monitor/issues) on GitHub.
