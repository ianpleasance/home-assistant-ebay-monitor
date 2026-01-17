# eBay Integration - Usage Guide

This guide provides detailed instructions on how to use the eBay integration for Home Assistant.

## Table of Contents

1. [Initial Setup](#initial-setup)
2. [Creating Searches](#creating-searches)
3. [Understanding Sensors](#understanding-sensors)
4. [Using Dashboards](#using-dashboards)
5. [Setting Up Automations](#setting-up-automations)
6. [Advanced Usage](#advanced-usage)

## Initial Setup

### Step 1: Get eBay API Credentials

1. Visit [eBay Developer Program](https://developer.ebay.com/)
2. Create an account or sign in
3. Go to "My Account" → "Application Keys"
4. Create a new application:
   - Application Title: "Home Assistant Integration"
   - Environment: **Production** (not Sandbox)
5. Save the following credentials securely:
   - **App ID (Client ID)**: e.g., `YourApp-YourName-PRD-...`
   - **Dev ID**: e.g., `abcd1234-...`
   - **Cert ID (Client Secret)**: e.g., `PRD-abcd1234...`

### Step 2: Generate User Token

1. In eBay Developer Portal, go to "User Tokens"
2. Select "Auth'n'Auth" tab
3. Click "Get a User Token Here"
4. Follow the OAuth flow to authorize your application
5. Copy the generated token (starts with `v^1.1#...`)

**Important**: User tokens expire. You'll need to regenerate them periodically.

### Step 3: Add Integration to Home Assistant

1. Navigate to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "eBay"
4. Enter your account details:
   ```
   Account Name: My Personal eBay
   App ID: [Your App ID]
   Dev ID: [Your Dev ID]
   Cert ID: [Your Cert ID]
   User Token: [Your Token]
   ```
5. Click **Submit**

The integration will create three base sensors immediately:
- Active Bids sensor
- Watchlist sensor
- Purchases sensor

## Creating Searches

### Method 1: Via UI (Recommended)

1. Go to **Settings** → **Devices & Services**
2. Find "eBay - {Your Account Name}"
3. Click **Configure** button
4. You'll see a list of existing searches
5. Select "Add New Search"
6. Fill in the search parameters:

**Example Configuration:**
```
Search Query: vintage Leica camera
eBay Site: United Kingdom
Category ID: 625 (Cameras & Photography)
Minimum Price: 100
Maximum Price: 1000
Listing Type: Both
Update Interval: 15 minutes
```

7. Click **Submit**

A new sensor will be created: `sensor.ebay_my_personal_ebay_search_vintage_leica_camera`

### Method 2: Via Service Call

In **Developer Tools** → **Services**:

```yaml
service: ebay.create_search
data:
  account: "My Personal eBay"
  search_query: "vintage Leica camera"
  site: "uk"
  category_id: "625"
  min_price: 100
  max_price: 1000
  listing_type: "both"
  update_interval: 15
```

### Finding Category IDs

eBay category IDs can be found:
1. Browse to the category on eBay
2. Look at the URL: `ebay.co.uk/b/Cameras-Photography/625`
3. The number at the end (625) is the category ID

Common categories:
- Electronics: 293
- Cameras & Photography: 625
- Collectibles: 1
- Home & Garden: 11700
- Sporting Goods: 888

## Understanding Sensors

### Active Bids Sensor

**Entity ID**: `sensor.ebay_{account}_active_bids`

**State**: Number of active bids

**Attributes**:
```yaml
items:
  - item_id: "123456789"
    title: "Vintage Leica M3 Camera"
    seller_username: "camera_collector"
    seller_feedback_score: 2500
    seller_positive_percent: 99.9
    seller_location: "United Kingdom"
    current_price:
      value: 850.00
      currency: "GBP"
    is_high_bidder: true
    reserve_met: true
    end_time: "2025-01-20T18:30:00Z"
    time_remaining: "2 days 3 hours"
    bid_count: 15
    image_url: "https://..."
    item_url: "https://www.ebay.co.uk/itm/123456789"
```

### Watchlist Sensor

**Entity ID**: `sensor.ebay_{account}_watchlist`

**State**: Number of watched items

Similar attributes to bids, plus:
- `watchers`: Number of other people watching

### Purchases Sensor

**Entity ID**: `sensor.ebay_{account}_purchases`

**State**: Number of recent purchases

Includes all bid attributes, plus:
- `shipping_status`: "pending", "shipped", or "delivered"
- `tracking_number`: Tracking number (if available)

### Search Sensors

**Entity ID**: `sensor.ebay_{account}_search_{query}`

**State**: Number of matching results

**Attributes**:
```yaml
search_query: "vintage Leica camera"
search_id: "a1b2c3d4-..."
items:
  - [Array of matching items]
```

## Using Dashboards

### Simple Bids Dashboard

Perfect for quick checks of your active bids.

**Setup:**
1. Copy content from `dashboards/ebay_bids_simple.yaml`
2. Create new dashboard or edit existing
3. Paste in YAML mode
4. Replace `My Personal eBay` with your account name

**Features:**
- Clean bid list with images
- Status indicators (Winning/Outbid)
- Reserve met status
- Time remaining
- Quick refresh button
- "Ending Soon" alert section

### Complete Dashboard

Comprehensive view of all eBay activity.

**Setup:**
1. Copy content from `dashboards/ebay_complete.yaml`
2. Create new dashboard
3. Paste in YAML mode
4. Update account names throughout

**Features:**
- Overview tab with statistics
- Searches tab with all results
- Active bids with full details
- Watchlist items
- Purchase history with tracking
- Refresh buttons on each tab

### Customizing Dashboards

**Change the account name:**
Find and replace `My Personal eBay` with your account name.

**Add multiple accounts:**
Duplicate sections and update entity IDs:
```yaml
- entity: sensor.ebay_personal_account_active_bids
- entity: sensor.ebay_business_account_active_bids
```

**Adjust refresh intervals:**
Change the `update_interval` parameter in search configurations.

## Setting Up Automations

### Using Blueprints

1. Go to **Settings** → **Automations & Scenes**
2. Click **+ Create Automation**
3. Select **Start with a blueprint**
4. Choose an eBay blueprint
5. Configure parameters
6. Save

### Available Blueprints

1. **Outbid Notification**
   - Alerts when you're outbid
   - Configurable to show price
   - Includes item image

2. **Auction Ending Soon**
   - 15-minute warning before auction ends
   - Filter by winning/losing status
   - Includes quick action button

3. **New Search Result**
   - Alerts for new matching items
   - Price filter option
   - Shows seller info

4. **Package Shipped**
   - Notification when item ships
   - Includes tracking number
   - Links to eBay order

5. **Auction Won/Lost**
   - Results notification
   - Separate control for wins/losses
   - Shows final price

### Custom Automation Example

Monitor a specific search and get SMS alerts for items under £500:

```yaml
automation:
  - alias: "eBay - Cheap Leica Alert"
    trigger:
      - platform: event
        event_type: ebay_new_search_result
    condition:
      - condition: template
        value_template: >-
          {{ trigger.event.data.search_query == 'vintage Leica camera' }}
      - condition: template
        value_template: >-
          {{ trigger.event.data.item.current_price.value < 500 }}
    action:
      - service: notify.sms
        data:
          message: >-
            LEICA DEAL! {{ trigger.event.data.item.title }}
            Price: £{{ trigger.event.data.item.current_price.value }}
            {{ trigger.event.data.item.item_url }}
```

## Advanced Usage

### Multiple Accounts

Add multiple eBay accounts to track business and personal separately:

1. Add integration multiple times with different account names
2. Each creates separate sensors
3. Dashboards can show all accounts or filter by account

### Dynamic Search Creation

Create searches programmatically based on other sensors:

```yaml
automation:
  - alias: "Create search from wishlist"
    trigger:
      - platform: state
        entity_id: input_text.camera_model
    action:
      - service: ebay.create_search
        data:
          account: "My Personal eBay"
          search_query: "{{ states('input_text.camera_model') }}"
          site: "uk"
          max_price: 1000
          listing_type: "auction"
```

### Price Drop Monitoring

Track price changes on watched items:

```yaml
automation:
  - alias: "eBay - Price Drop Alert"
    trigger:
      - platform: state
        entity_id: sensor.ebay_my_personal_ebay_watchlist
    condition:
      - condition: template
        value_template: >-
          {% set old_items = trigger.from_state.attributes.items %}
          {% set new_items = trigger.to_state.attributes.items %}
          {% for new_item in new_items %}
            {% for old_item in old_items %}
              {% if new_item.item_id == old_item.item_id %}
                {% if new_item.current_price.value < old_item.current_price.value %}
                  true
                {% endif %}
              {% endif %}
            {% endfor %}
          {% endfor %}
    action:
      - service: notify.mobile_app
        data:
          title: "Price drop on watched item!"
```

### Seller Reputation Filtering

Only get alerts for highly-rated sellers:

```yaml
automation:
  - alias: "eBay - High Reputation Sellers Only"
    trigger:
      - platform: event
        event_type: ebay_new_search_result
    condition:
      - condition: template
        value_template: >-
          {{ trigger.event.data.item.seller_feedback_score > 1000 }}
      - condition: template
        value_template: >-
          {{ trigger.event.data.item.seller_positive_percent > 99.0 }}
    action:
      - service: notify.mobile_app
        data:
          title: "High-reputation seller found!"
```

### Manual Refresh Scheduling

Create a scheduled refresh during specific hours:

```yaml
automation:
  - alias: "eBay - Hourly Refresh (Business Hours)"
    trigger:
      - platform: time_pattern
        hours: "/1"
    condition:
      - condition: time
        after: "09:00:00"
        before: "18:00:00"
      - condition: state
        entity_id: binary_sensor.workday_sensor
        state: "on"
    action:
      - service: ebay.refresh_account
        data:
          account: "My Personal eBay"
```

### Integration with Calendar

Add auction end times to your calendar:

```yaml
automation:
  - alias: "eBay - Add Auction to Calendar"
    trigger:
      - platform: event
        event_type: ebay_auction_ending_soon
    action:
      - service: calendar.create_event
        data:
          calendar: "calendar.ebay_auctions"
          summary: "Auction Ending: {{ trigger.event.data.item.title }}"
          description: "{{ trigger.event.data.item.item_url }}"
          start: "{{ trigger.event.data.item.end_time }}"
          end: "{{ trigger.event.data.item.end_time }}"
```

## Troubleshooting

### "No data" in sensors

**Cause**: Token may be expired or invalid

**Solution**:
1. Go to eBay Developer Portal
2. Generate new User Token
3. Update integration configuration with new token

### Searches not updating

**Check**:
1. Is the update interval too long?
2. Check Home Assistant logs for API errors
3. Verify search parameters are valid

### Too many API calls

**Solution**:
1. Increase update intervals (30+ minutes)
2. Reduce number of searches
3. Use manual refresh instead of automatic

### Missing seller information

**Cause**: eBay API may not return all fields for all items

**Solution**: This is normal for some listings. The integration includes all available data.

## Tips & Best Practices

1. **Start with longer update intervals** (30 mins) and decrease if needed
2. **Use specific search queries** rather than broad terms for better results
3. **Set price filters** to reduce API calls and get relevant results
4. **Use blueprints** as a starting point, then customize
5. **Monitor the ending soon alerts** rather than checking constantly
6. **Create separate accounts** for business and personal if needed
7. **Use conditional cards** in dashboards to hide empty sections
8. **Tag automations** for easy management: `ebay_alerts`, `ebay_monitoring`

## Support

For issues or questions:
- GitHub Issues: [github.com/planetbuilders/ebay-integration/issues](https://github.com/planetbuilders/ebay-integration/issues)
- Community Forum: Home Assistant Community
