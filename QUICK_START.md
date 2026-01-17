# Quick Start Guide

Get up and running with the eBay integration in 10 minutes.

## Prerequisites

- Home Assistant 2024.1.0 or newer
- eBay account
- eBay Developer account (free)

## 5-Step Setup

### 1. Get eBay API Credentials (5 minutes)

1. Go to https://developer.ebay.com/
2. Sign in → "My Account" → "Application Keys"
3. Create new application (Production environment)
4. Save these 4 values:
   - App ID
   - Dev ID
   - Cert ID
   - User Token (generate under "User Tokens" tab)

### 2. Install Integration (2 minutes)

**Via HACS:**
1. HACS → Integrations → "+" → Custom repositories
2. Add: `https://github.com/planetbuilders/ebay-integration`
3. Install "eBay"
4. Restart Home Assistant

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

**Result**: 3 sensors created instantly!
- `sensor.ebay_my_ebay_active_bids`
- `sensor.ebay_my_ebay_watchlist`
- `sensor.ebay_my_ebay_purchases`

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

**Result**: New sensor `sensor.ebay_my_ebay_search_vintage_camera`

### 5. Add Dashboard (1 minute)

1. Copy from `dashboards/ebay_bids_simple.yaml`
2. Settings → Dashboards → Create new
3. Switch to YAML mode → Paste
4. Replace "My Personal eBay" with "My eBay"

**Done!** You're now tracking eBay!

## Quick Automations

### Get Outbid Alert

Settings → Automations → "+ Create" → "Start with blueprint" → "eBay - Notify When Outbid"

Configure:
- eBay Account: My eBay
- Notification Service: notify.mobile_app_yourphone

### Auction Ending Alert

Settings → Automations → "+ Create" → "eBay - Auction Ending Soon Alert"

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

## View Your Data

Check your sensors:
1. Developer Tools → States
2. Filter: `ebay`
3. Click any sensor to see full details

## Refresh Data Manually

Developer Tools → Services:
```yaml
service: ebay.refresh_account
data:
  account: "My eBay"
```

## Next Steps

- Read the [Usage Guide](USAGE_GUIDE.md) for advanced features
- Browse [README.md](README.md) for complete documentation
- Check `blueprints/automation/` for more automation ideas

## Troubleshooting

**No data appearing?**
- Wait 5 minutes for first update
- Check logs: Settings → System → Logs
- Manually refresh: `ebay.refresh_account` service

**Token expired?**
- Regenerate token at developer.ebay.com
- Update integration configuration

**Search returns nothing?**
- Try broader search terms
- Remove price filters temporarily
- Check on ebay.co.uk that results exist

## Support

- Issues: [GitHub](https://github.com/planetbuilders/ebay-integration/issues)
- Documentation: See README.md and USAGE_GUIDE.md
