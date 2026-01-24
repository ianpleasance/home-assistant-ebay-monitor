# eBay Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![License](https://img.shields.io/github/license/ianpleasance/ebay-integration)](LICENSE)

A comprehensive Home Assistant integration for monitoring your eBay account activity. Track active bids, watchlist items, purchases, and create custom search alerts - all from your Home Assistant dashboard.

## Features

- 🔍 **Saved Searches** - Create and manage multiple eBay searches with automatic updates
- 🚀 **Modern Browse API** - Uses eBay's latest API with better rate limits and OAuth 2.0
- 🎯 **Active Bids** - Monitor all your active bids with real-time status updates
- 👁️ **Watchlist** - Track items you're watching
- 📦 **Purchases** - Keep tabs on your purchase history and shipping status
- 🔔 **Smart Alerts** - Automated notifications for bid changes, auction endings, and shipping updates
- 🔄 **Multi-Account Support** - Manage multiple eBay accounts from one integration
- 🎨 **Beautiful Dashboards** - Pre-built dashboard templates included
- 📊 **API Tracking** - Monitor your API usage and avoid rate limits

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click on "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/ianpleasance/ebay-integration`
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
4. Create a new application (choose "Production" environment)
5. You'll receive:
   - **App ID (Client ID)**
   - **Dev ID**
   - **Cert ID (Client Secret)**
6. Generate a **User Token** for your account

### Adding the Integration

1. In Home Assistant, go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "eBay"
4. Enter a name for your account (e.g., "My Personal eBay")
5. Enter your API credentials:
   - App ID
   - Dev ID
   - Cert ID
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

The integration creates the following sensors for each account:

- `sensor.ebay_{account}_active_bids` - Number of active bids
- `sensor.ebay_{account}_watchlist` - Number of watched items
- `sensor.ebay_{account}_purchases` - Number of recent purchases
- `sensor.ebay_{account}_search_{query}` - Results for each saved search

Each sensor includes detailed attributes with full item information.

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

The integration fires events that you can use for automations:

- `ebay_new_search_result` - New item matches your search
- `ebay_became_high_bidder` - You became the high bidder
- `ebay_outbid` - You were outbid
- `ebay_auction_ending_soon` - Auction ending in 15 minutes
- `ebay_auction_won` - You won an auction
- `ebay_auction_lost` - You lost an auction
- `ebay_item_shipped` - Purchase was shipped
- `ebay_item_delivered` - Purchase was delivered

## Dashboards

Two sample dashboards are included in the `dashboards/` folder:

### Simple Bids Dashboard (`ebay_bids_simple.yaml`)

A clean, focused view showing only your active bids with:
- Winning/outbid status indicators
- Countdown timers
- Reserve met status
- Quick refresh button
- Ending soon alerts

### Complete Dashboard (`ebay_complete.yaml`)

Comprehensive view with tabs for:
- Overview with summary statistics
- All saved searches with results
- Active bids with details
- Watchlist items
- Purchase history with tracking

To use these dashboards:

1. Copy the desired YAML file content
2. Go to Home Assistant → **Settings** → **Dashboards**
3. Create a new dashboard or edit an existing one
4. Switch to YAML mode
5. Paste the content
6. Update entity IDs to match your account name

## Example Automations

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
          message: "{{ trigger.event.data.item.title }} - Current price: {{ trigger.event.data.item.current_price.value }}"
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
          message: "{{ trigger.event.data.item.title }} - {{ trigger.event.data.item.current_price.value }} {{ trigger.event.data.item.current_price.currency }}"
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
          message: "{{ trigger.event.data.item.title }} - {{ trigger.event.data.minutes_remaining }} minutes left"
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
          message: "{{ trigger.event.data.item.title }}{% if trigger.event.data.item.tracking_number %} - Tracking: {{ trigger.event.data.item.tracking_number }}{% endif %}"
```

## Item Attributes

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
is_high_bidder: true  # For bids only
reserve_met: true  # For auctions
end_time: "2025-01-20T15:30:00Z"
time_remaining: "2 days 4 hours"
description: "..."
image_url: "https://..."
item_url: "https://www.ebay.co.uk/itm/123456789"
listing_type: "Auction"
bid_count: 12  # For bids
watchers: 45  # For watchlist
shipping_status: "shipped"  # For purchases: pending/shipped/delivered
tracking_number: "1Z999..."  # For purchases
```

## Troubleshooting

### Integration Not Loading

- Ensure you've restarted Home Assistant after installation
- Check the Home Assistant logs for error messages
- Verify your API credentials are correct

### No Data Appearing

- Make sure your eBay token has the correct permissions
- Check that you have active bids/watchlist items
- Try manually refreshing using the `ebay.refresh_account` service

### Rate Limiting

The eBay API has rate limits. If you're experiencing issues:
- Increase the update intervals for your searches
- Reduce the number of saved searches
- Avoid calling refresh services too frequently

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the Apache 2.0 License - see the LICENSE file for details.

## Disclaimer

This integration is not affiliated with or endorsed by eBay. Use at your own risk.

## Support

For issues, feature requests, or questions, please [open an issue](https://github.com/ianpleasance/ebay-integration/issues) on GitHub.

## Changelog

### Version 1.0.0 (Initial Release)
- Multi-account support
- Saved search management with UI
- Active bids monitoring
- Watchlist tracking
- Purchase history with shipping status
- Event-driven automation system
- Pre-built dashboards
- Comprehensive services for manual refresh
- Seller information including location and feedback
