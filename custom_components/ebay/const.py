"""Constants for the eBay integration."""
from typing import Final

DOMAIN: Final = "ebay"

# Configuration
CONF_ACCOUNT_NAME: Final = "account_name"
CONF_SEARCHES: Final = "searches"
CONF_SEARCH_QUERY: Final = "search_query"
CONF_SITE: Final = "site"
CONF_CATEGORY_ID: Final = "category_id"
CONF_MIN_PRICE: Final = "min_price"
CONF_MAX_PRICE: Final = "max_price"
CONF_LISTING_TYPE: Final = "listing_type"
CONF_UPDATE_INTERVAL: Final = "update_interval"

# Default values
DEFAULT_UPDATE_INTERVAL: Final = 15  # minutes
DEFAULT_BIDS_INTERVAL: Final = 5  # minutes
DEFAULT_WATCHLIST_INTERVAL: Final = 10  # minutes
DEFAULT_PURCHASES_INTERVAL: Final = 30  # minutes
DEFAULT_SITE: Final = "EBAY-GB"

# eBay Sites
EBAY_SITES: Final = {
    "uk": "EBAY-GB",
    "us": "EBAY-US",
    "de": "EBAY-DE",
    "fr": "EBAY-FR",
    "it": "EBAY-IT",
    "es": "EBAY-ES",
    "au": "EBAY-AU",
    "ca": "EBAY-ENCA",
}

# Listing types
LISTING_TYPE_AUCTION: Final = "Auction"
LISTING_TYPE_BUY_IT_NOW: Final = "FixedPrice"
LISTING_TYPE_BOTH: Final = "All"

LISTING_TYPES: Final = {
    "auction": LISTING_TYPE_AUCTION,
    "buy_it_now": LISTING_TYPE_BUY_IT_NOW,
    "both": LISTING_TYPE_BOTH,
}

# Event types
EVENT_NEW_SEARCH_RESULT: Final = "ebay_new_search_result"
EVENT_BECAME_HIGH_BIDDER: Final = "ebay_became_high_bidder"
EVENT_OUTBID: Final = "ebay_outbid"
EVENT_AUCTION_ENDING_SOON: Final = "ebay_auction_ending_soon"
EVENT_AUCTION_WON: Final = "ebay_auction_won"
EVENT_AUCTION_LOST: Final = "ebay_auction_lost"
EVENT_ITEM_SHIPPED: Final = "ebay_item_shipped"
EVENT_ITEM_DELIVERED: Final = "ebay_item_delivered"

# Service names
SERVICE_REFRESH_BIDS: Final = "refresh_bids"
SERVICE_REFRESH_WATCHLIST: Final = "refresh_watchlist"
SERVICE_REFRESH_PURCHASES: Final = "refresh_purchases"
SERVICE_REFRESH_SEARCH: Final = "refresh_search"
SERVICE_REFRESH_ACCOUNT: Final = "refresh_account"
SERVICE_REFRESH_ALL: Final = "refresh_all"
SERVICE_CREATE_SEARCH: Final = "create_search"
SERVICE_UPDATE_SEARCH: Final = "update_search"
SERVICE_DELETE_SEARCH: Final = "delete_search"
SERVICE_GET_RATE_LIMITS: Final = "get_rate_limits"
SERVICE_REFRESH_API_USAGE: Final = "refresh_api_usage"

# Storage
STORAGE_KEY: Final = "ebay_searches"
STORAGE_VERSION: Final = 1

# Attributes
ATTR_ACCOUNT: Final = "account"
ATTR_SEARCH_ID: Final = "search_id"
ATTR_ITEMS: Final = "items"
ATTR_ITEM_COUNT: Final = "item_count"
ATTR_LAST_UPDATED: Final = "last_updated"

# Item attributes
ATTR_ITEM_ID: Final = "item_id"
ATTR_TITLE: Final = "title"
ATTR_SELLER_USERNAME: Final = "seller_username"
ATTR_SELLER_FEEDBACK_SCORE: Final = "seller_feedback_score"
ATTR_SELLER_POSITIVE_PERCENT: Final = "seller_positive_percent"
ATTR_SELLER_LOCATION: Final = "seller_location"
ATTR_SELLER_URL: Final = "seller_url"
ATTR_CURRENT_PRICE: Final = "current_price"
ATTR_IS_HIGH_BIDDER: Final = "is_high_bidder"
ATTR_RESERVE_MET: Final = "reserve_met"
ATTR_END_TIME: Final = "end_time"
ATTR_TIME_REMAINING: Final = "time_remaining"
ATTR_DESCRIPTION: Final = "description"
ATTR_IMAGE_URL: Final = "image_url"
ATTR_ITEM_URL: Final = "item_url"
ATTR_LISTING_TYPE: Final = "listing_type"
ATTR_SHIPPING_STATUS: Final = "shipping_status"
ATTR_TRACKING_NUMBER: Final = "tracking_number"
ATTR_BID_COUNT: Final = "bid_count"
ATTR_WATCHERS: Final = "watchers"
