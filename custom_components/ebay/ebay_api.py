"""eBay API wrapper using REST APIs."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
import xml.etree.ElementTree as ET

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    ATTR_BID_COUNT,
    ATTR_CURRENT_PRICE,
    ATTR_DESCRIPTION,
    ATTR_END_TIME,
    ATTR_IMAGE_URL,
    ATTR_IS_HIGH_BIDDER,
    ATTR_ITEM_ID,
    ATTR_ITEM_URL,
    ATTR_LISTING_TYPE,
    ATTR_RESERVE_MET,
    ATTR_SELLER_FEEDBACK_SCORE,
    ATTR_SELLER_LOCATION,
    ATTR_SELLER_POSITIVE_PERCENT,
    ATTR_SELLER_URL,
    ATTR_SELLER_USERNAME,
    ATTR_SHIPPING_STATUS,
    ATTR_TIME_REMAINING,
    ATTR_TITLE,
    ATTR_TRACKING_NUMBER,
    ATTR_WATCHERS,
)

_LOGGER = logging.getLogger(__name__)


def format_price(price_dict: dict[str, Any]) -> str:
    """Format price with currency symbol and 2 decimal places.
    
    Args:
        price_dict: Dictionary with 'value' and 'currency' keys
        
    Returns:
        Formatted price string like '£3.20' or '$15.99'
    """
    if not price_dict or "value" not in price_dict or "currency" not in price_dict:
        return "N/A"
    
    value = float(price_dict["value"])
    currency = price_dict["currency"]
    
    # Currency symbol mapping
    symbols = {
        "GBP": "£",
        "USD": "$",
        "EUR": "€",
        "AUD": "A$",
        "CAD": "C$",
    }
    
    symbol = symbols.get(currency, f"{currency} ")
    
    # Format with 2 decimal places
    return f"{symbol}{value:.2f}"


# eBay API Endpoints
SHOPPING_API_URL = "https://open.api.ebay.com/shopping"
TRADING_API_URL = "https://api.ebay.com/ws/api.dll"
ANALYTICS_API_URL = "https://api.ebay.com/developer/analytics/v1_beta/rate_limit"
BROWSE_API_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
OAUTH_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"

# Cache Configuration
# Enable/disable caching of MyeBay buying data to reduce redundant API calls
# When enabled, multiple coordinators (bids/watchlist/purchases) share one API call
ENABLE_MY_EBAY_CACHE = True  # Set to False to disable caching

# Cache duration in seconds (only used if ENABLE_MY_EBAY_CACHE is True)
# Default: 30 seconds - enough for startup when coordinators refresh simultaneously
MY_EBAY_CACHE_DURATION = 30


class EbayAPI:
    """Class to interact with eBay API using direct REST calls."""

    def __init__(
        self,
        hass: HomeAssistant,
        app_id: str,
        dev_id: str,
        cert_id: str,
        token: str,
        site_id: str = "EBAY-GB",
    ) -> None:
        """Initialize the API wrapper."""
        self.hass = hass
        self._app_id = app_id
        self._dev_id = dev_id
        self._cert_id = cert_id
        self._token = token
        self._site_id = site_id
        self._session = async_get_clientsession(hass)
        
        # Cache for get_my_ebay_buying to avoid duplicate API calls
        self._my_ebay_cache = None
        self._my_ebay_cache_time = None
        
        # Store the authenticated user's eBay username (extracted from API responses)
        self._ebay_username = None
        
        # OAuth token for Browse API
        self._oauth_token = None
        self._oauth_token_expires = None
        self._oauth_failed = False  # Track if OAuth authentication has failed
        
        # API call tracking
        self._api_calls = {
            "browse": {"count": 0, "last_reset": datetime.now()},
            "trading": {"count": 0, "last_reset": datetime.now()},
            "shopping": {"count": 0, "last_reset": datetime.now()},
        }
        
        # Cache for Analytics API data (rate limit info from eBay)
        self._analytics_cache = None
        self._analytics_cache_time = None

    async def get_rate_limit_usage(self) -> dict[str, Any]:
        """Get actual API rate limit usage from eBay's Analytics API.
        
        Returns combined data:
        - Local tracking (our counts)
        - eBay Analytics (actual usage from eBay)
        
        This requires OAuth token, so only works when Browse API is configured.
        """
        result = {
            "local_tracking": self._api_calls.copy(),
            "ebay_analytics": None,
            "error": None,
        }
        
        # Try to get actual usage from eBay Analytics API
        try:
            # Get OAuth token (same one used for Browse API)
            token = await self._get_oauth_token()
            if not token:
                result["error"] = "No OAuth token available"
                return result
            
            # Check cache (Analytics API has its own rate limits, cache for 5 minutes)
            if self._analytics_cache and self._analytics_cache_time:
                cache_age = (datetime.now() - self._analytics_cache_time).total_seconds()
                if cache_age < 300:  # 5 minutes
                    result["ebay_analytics"] = self._analytics_cache
                    return result
            
            # Call Analytics API
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            
            async with self._session.get(
                ANALYTICS_API_URL,
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    _LOGGER.debug(
                        "eBay Analytics API raw response - Status: %s, Data keys: %s, Full response: %s",
                        response.status,
                        list(data.keys()),
                        data
                    )
                    
                    # Parse rate limits into simpler format
                    parsed = {}
                    for api_limit in data.get("rateLimits", []):
                        api_context = api_limit.get("apiContext", "")
                        api_name = api_limit.get("apiName", "")
                        
                        _LOGGER.debug(
                            "Processing API limit - Context: %s, Name: %s, Full: %s",
                            api_context,
                            api_name,
                            api_limit
                        )
                        
                        # Map to our tracking names based on eBay's actual response format
                        tracking_name = None
                        if api_context == "buy" and api_name == "Browse":
                            tracking_name = "browse"
                        elif api_context == "TradingAPI" and api_name == "TradingAPI":
                            tracking_name = "trading"
                        
                        if tracking_name:
                            resources = api_limit.get("resources", [])
                            for resource in resources:
                                rates = resource.get("rates", [])
                                for rate in rates:
                                    # Look for daily rate limit (timeWindow = 86400 seconds = 1 day)
                                    if rate.get("timeWindow") == 86400:
                                        limit_val = int(rate.get("limit", 0))
                                        count_val = int(rate.get("count", 0))
                                        remaining_val = int(rate.get("remaining", 0))
                                        
                                        # Calculate usage percentage safely
                                        usage_pct = 0.0
                                        if limit_val > 0:
                                            usage_pct = round((count_val / limit_val) * 100, 1)
                                        
                                        parsed[tracking_name] = {
                                            "limit": limit_val,
                                            "remaining": remaining_val,
                                            "used": count_val,
                                            "reset": rate.get("reset"),
                                            "usage_percent": usage_pct
                                        }
                                        
                                        _LOGGER.debug(
                                            "Mapped %s API: %d/%d used (%.1f%%), %d remaining",
                                            tracking_name,
                                            count_val,
                                            limit_val,
                                            usage_pct,
                                            remaining_val
                                        )
                                        break  # Only need first daily rate
                    
                    self._analytics_cache = parsed
                    self._analytics_cache_time = datetime.now()
                    result["ebay_analytics"] = parsed
                    
                    _LOGGER.debug("eBay Analytics API - Rate limits retrieved: %s", parsed)
                else:
                    error_text = await response.text()
                    result["error"] = f"Analytics API returned {response.status}: {error_text[:200]}"
                    _LOGGER.warning("eBay Analytics API error: %s", result["error"])
                    
        except Exception as err:
            result["error"] = f"Failed to fetch analytics: {err}"
            _LOGGER.error("Error fetching eBay Analytics: %s", err)
        
        return result

    def _get_marketplace_id(self, site_id: str) -> str:
        """Map site_id to Browse API marketplace_id.
        
        Site IDs use format: EBAY-GB, EBAY-US, etc.
        Browse API uses: EBAY_GB, EBAY_US, etc.
        UI sends: uk, us, de, etc. (lowercase)
        """
        # Normalize lowercase country codes from UI
        if site_id and len(site_id) == 2 and site_id.islower():
            site_id = f"EBAY-{site_id.upper()}"
        
        marketplace_map = {
            "EBAY-GB": "EBAY_GB",
            "EBAY-US": "EBAY_US",
            "EBAY-DE": "EBAY_DE",
            "EBAY-FR": "EBAY_FR",
            "EBAY-IT": "EBAY_IT",
            "EBAY-ES": "EBAY_ES",
            "EBAY-AU": "EBAY_AU",
            "EBAY-CA": "EBAY_CA",
        }
        
        # Try direct lookup
        if site_id in marketplace_map:
            return marketplace_map[site_id]
        
        # Try converting hyphen to underscore
        converted = site_id.replace("-", "_")
        if converted.startswith("EBAY_"):
            return converted
        
        # Default to US
        _LOGGER.warning(f"Unknown site_id {site_id}, defaulting to EBAY_US")
        return "EBAY_US"
        return "EBAY_US"

    async def _get_oauth_token(self) -> str | None:
        """Get OAuth 2.0 application token for Browse API.
        
        Returns cached token if valid, otherwise requests new one.
        Falls back gracefully if OAuth credentials are invalid.
        """
        from datetime import timedelta
        
        # Check if we have a valid cached token
        if (self._oauth_token and self._oauth_token_expires and 
            datetime.now() < self._oauth_token_expires):
            return self._oauth_token
        
        # If we previously failed to get OAuth token, don't keep trying
        if hasattr(self, '_oauth_failed') and self._oauth_failed:
            return None
        
        _LOGGER.debug("Requesting new OAuth token for Browse API")
        
        try:
            import base64
            
            # Create credentials string
            credentials = f"{self._app_id}:{self._cert_id}"
            b64_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {b64_credentials}"
            }
            
            data = {
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope"
            }
            
            async with self._session.post(
                OAUTH_TOKEN_URL,
                headers=headers,
                data=data
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    _LOGGER.error(
                        "OAuth token request failed: Status %s, Response: %s",
                        response.status,
                        error_text[:500]
                    )
                    
                    # Mark OAuth as failed so we don't keep retrying
                    self._oauth_failed = True
                    
                    if response.status == 401:
                        _LOGGER.warning(
                            "OAuth authentication failed. Your eBay API credentials may not be "
                            "configured for OAuth access. Search functionality requires OAuth/Browse API. "
                            "To enable OAuth, ensure your eBay application has OAuth enabled in the "
                            "eBay Developer Portal, or create a new application with OAuth support."
                        )
                    
                    return None
                
                token_data = await response.json()
                self._oauth_token = token_data.get("access_token")
                expires_in = token_data.get("expires_in", 7200)  # Default 2 hours
                
                # Set expiry time (subtract 5 minutes for safety)
                self._oauth_token_expires = datetime.now() + timedelta(seconds=expires_in - 300)
                
                _LOGGER.info(
                    "OAuth token obtained successfully, expires in %d seconds",
                    expires_in
                )
                
                return self._oauth_token
                
        except Exception as err:
            _LOGGER.error("Error obtaining OAuth token: %s", err)
            self._oauth_failed = True
            return None

    async def _get_authenticated_username(self) -> str | None:
        """Get the authenticated user's eBay username using GetUser API.
        
        This is called once at startup to determine the user's eBay username,
        which is then used to compare with high bidder usernames.
        """
        if self._ebay_username:
            return self._ebay_username
        
        _LOGGER.debug("Fetching authenticated user's eBay username via GetUser API")
        
        try:
            # Build GetUser XML request
            xml_request = f"""<?xml version="1.0" encoding="utf-8"?>
<GetUserRequest xmlns="urn:ebay:apis:eBLBaseComponents">
  <RequesterCredentials>
    <eBayAuthToken>{self._token}</eBayAuthToken>
  </RequesterCredentials>
</GetUserRequest>"""

            headers = {
                "X-EBAY-API-SITEID": "3" if self._site_id == "EBAY-GB" else "0",
                "X-EBAY-API-COMPATIBILITY-LEVEL": "967",
                "X-EBAY-API-CALL-NAME": "GetUser",
                "X-EBAY-API-APP-NAME": self._app_id,
                "X-EBAY-API-DEV-NAME": self._dev_id,
                "X-EBAY-API-CERT-NAME": self._cert_id,
                "Content-Type": "text/xml",
            }

            async with self._session.post(
                TRADING_API_URL, data=xml_request, headers=headers
            ) as response:
                if response.status != 200:
                    _LOGGER.error("GetUser API error: Status %s", response.status)
                    return None

                xml_text = await response.text()
                
                # Log first 1000 chars of response for debugging
                _LOGGER.debug("GetUser API response (first 1000 chars): %s", xml_text[:1000])
                
                root = ET.fromstring(xml_text)
                namespace = {"ns": "urn:ebay:apis:eBLBaseComponents"}
                
                # Check for eBay API errors in the response
                ack_elem = root.find(".//ns:Ack", namespace)
                if ack_elem is not None and ack_elem.text == "Failure":
                    # Extract error details
                    error_code_elem = root.find(".//ns:Errors/ns:ErrorCode", namespace)
                    error_msg_elem = root.find(".//ns:Errors/ns:LongMessage", namespace)
                    
                    error_code = error_code_elem.text if error_code_elem is not None else "unknown"
                    error_msg = error_msg_elem.text if error_msg_elem is not None else "unknown error"
                    
                    if error_code == "931":
                        _LOGGER.warning(
                            "GetUser API failed - eBay Auth Token is invalid (Error 931). "
                            "This may affect 'is_high_bidder' detection in bids. "
                            "The token works for GetMyeBayBuying but not GetUser. "
                            "You may need to regenerate your eBay Auth Token. "
                            "Error: %s", error_msg
                        )
                    else:
                        _LOGGER.error(
                            "GetUser API returned eBay error %s: %s", 
                            error_code, error_msg
                        )
                    
                    return None
                
                # Extract UserID from response - try multiple approaches
                
                # Approach 1: With namespace
                user_id_elem = root.find(".//ns:User/ns:UserID", namespace)
                
                # Approach 2: Without namespace (in case response doesn't use it)
                if user_id_elem is None:
                    user_id_elem = root.find(".//UserID")
                
                # Approach 3: Direct path
                if user_id_elem is None:
                    for elem in root.iter():
                        if elem.tag.endswith("UserID") and elem.text:
                            user_id_elem = elem
                            break
                
                if user_id_elem is not None and user_id_elem.text:
                    self._ebay_username = user_id_elem.text
                    _LOGGER.info("Authenticated eBay username: %s", self._ebay_username)
                    return self._ebay_username
                else:
                    _LOGGER.error("Could not extract UserID from GetUser response")
                    _LOGGER.debug("Root tag: %s, All tags in response: %s", 
                                root.tag, [elem.tag for elem in root.iter()][:20])
                    return None
                    
        except Exception as err:
            _LOGGER.error("Error fetching authenticated username: %s", err)
            return None

    async def search_items(
        self,
        query: str,
        site_id: str | None = None,
        category_id: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        listing_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search for items on eBay.
        
        Uses Browse API which supports both auctions and fixed price listings.
        Note: Browse API defaults to FIXED_PRICE only, so we explicitly set
        buyingOptions:{AUCTION|FIXED_PRICE} to get both types.
        """
        return await self._search_items_browse(
            query, site_id, category_id, min_price, max_price, listing_type
        )


    async def _search_items_browse(
        self,
        query: str,
        site_id: str | None = None,
        category_id: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        listing_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search for items using Browse API (modern, OAuth 2.0)."""
        try:
            # Get OAuth token
            token = await self._get_oauth_token()
            if not token:
                _LOGGER.error("Failed to obtain OAuth token for Browse API")
                return []
            
            # Map site_id to marketplace_id
            marketplace_id = self._get_marketplace_id(site_id or self._site_id)
            
            # Build headers
            headers = {
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": marketplace_id,
                "X-EBAY-C-ENDUSERCTX": f"affiliateCampaignId=<ePNCampaignId>,affiliateReferenceId=<referenceId>",
            }
            
            # Build query parameters
            params = {
                "q": query,
                "limit": "200",  # Max results per page
            }
            
            # Add category filter
            if category_id:
                params["category_ids"] = category_id
            
            # Build filter string
            filters = []
            
            # Price filter
            if min_price is not None or max_price is not None:
                min_val = round(min_price, 2) if min_price is not None else "*"
                max_val = round(max_price, 2) if max_price is not None else "*"
                currency = "GBP" if "GB" in marketplace_id else "USD"
                filters.append(f"price:[{min_val}..{max_val}]")
                filters.append(f"priceCurrency:{currency}")
            
            # Listing type filter
            # Normalize to lowercase for comparison
            listing_type_lower = listing_type.lower() if listing_type else None
            
            if listing_type_lower == "auction":
                # Only auctions
                filters.append("buyingOptions:{AUCTION}")
                _LOGGER.debug("Listing type filter: AUCTION only")
            elif listing_type_lower in ["fixedprice", "buy_it_now"]:
                # Only fixed price
                filters.append("buyingOptions:{FIXED_PRICE}")
                _LOGGER.debug("Listing type filter: FIXED_PRICE only")
            else:
                # Both or None - explicitly request BOTH auction and fixed price
                # Per eBay docs: Browse API defaults to FIXED_PRICE only, so we must specify both
                filters.append("buyingOptions:{AUCTION|FIXED_PRICE}")
                _LOGGER.debug("Listing type filter: AUCTION|FIXED_PRICE (listing_type=%s)", listing_type)
            
            # Add filters to params
            if filters:
                params["filter"] = ",".join(filters)
            
            _LOGGER.debug("eBay Browse API search - Query: %s, Marketplace: %s, Params: %s", 
                         query, marketplace_id, params)
            
            # Track API call
            self._track_api_call("browse")
            
            # Make request
            async with self._session.get(
                BROWSE_API_URL,
                headers=headers,
                params=params
            ) as response:
                _LOGGER.debug(
                    "eBay Browse API call - Status: %s, URL: %s",
                    response.status,
                    response.url
                )
                
                response_text = await response.text()
                
                if response.status != 200:
                    _LOGGER.error(
                        "eBay Browse API error: Status %s, Response: %s",
                        response.status,
                        response_text[:500]
                    )
                    
                    # Check for rate limiting
                    if response.status == 429 or "rate" in response_text.lower():
                        _LOGGER.warning(
                            "eBay Browse API rate limit reached. Search will retry at next interval."
                        )
                    
                    return []
                
                try:
                    data = await response.json()
                    
                    # Debug: log response structure if no items found
                    if "itemSummaries" not in data or not data["itemSummaries"]:
                        _LOGGER.warning(
                            "eBay Browse API returned 0 items for query '%s'. "
                            "Response keys: %s. Total: %s. Full response (first 1000 chars): %s",
                            query,
                            list(data.keys()),
                            data.get("total", "unknown"),
                            response_text[:1000]
                        )
                    
                except Exception as json_err:
                    _LOGGER.error("Failed to parse Browse API JSON: %s. Response: %s", 
                                 json_err, response_text[:500])
                    return []
                
                # Check for errors in response
                if "errors" in data or "warnings" in data:
                    errors = data.get("errors", [])
                    if errors:
                        _LOGGER.error("Browse API returned errors: %s", errors)
                        return []
                
                # Parse results
                items = []
                item_summaries = data.get("itemSummaries", [])
                
                for item in item_summaries:
                    parsed_item = self._parse_browse_item(item)
                    if parsed_item:
                        items.append(parsed_item)
                
                _LOGGER.debug(
                    "eBay Browse API search completed - Query: '%s', Results: %d items",
                    query,
                    len(items)
                )
                
                return items
                
        except Exception as err:
            _LOGGER.error("Error searching eBay with Browse API: %s", err)
            return []

    async def get_my_ebay_buying(self) -> dict[str, list[dict[str, Any]]]:
        """Get all buying activity (bids, watchlist, purchases) using Trading API.
        
        Supports pagination to retrieve all items even with hundreds of entries.
        """
        # Get the authenticated user's username if we don't have it yet
        if not self._ebay_username:
            await self._get_authenticated_username()
        
        # Cache results to avoid redundant API calls when
        # multiple coordinators refresh simultaneously
        from datetime import datetime, timedelta
        
        if ENABLE_MY_EBAY_CACHE:
            now = datetime.now()
            if (self._my_ebay_cache is not None and 
                self._my_ebay_cache_time is not None and 
                now - self._my_ebay_cache_time < timedelta(seconds=MY_EBAY_CACHE_DURATION)):
                cache_age = (now - self._my_ebay_cache_time).total_seconds()
                _LOGGER.debug(
                    "Using cached MyeBay data (age: %.1f seconds, avoiding API call)",
                    cache_age
                )
                return self._my_ebay_cache
        
        _LOGGER.debug("Fetching MyeBay buying data from Trading API (cache %s)", 
                     "disabled" if not ENABLE_MY_EBAY_CACHE else "miss or expired")
        
        # Fetch all pages for each list type
        all_bids = await self._fetch_my_ebay_list("BidList")
        all_watchlist = await self._fetch_my_ebay_list("WatchList")
        all_purchases = await self._fetch_my_ebay_list("WonList")
        
        result = {
            "bids": all_bids,
            "watchlist": all_watchlist,
            "purchases": all_purchases,
        }
        
        _LOGGER.debug(
            "eBay MyeBay data retrieved - Bids: %d, Watchlist: %d, Purchases: %d",
            len(result["bids"]),
            len(result["watchlist"]),
            len(result["purchases"])
        )
        
        # Update cache
        if ENABLE_MY_EBAY_CACHE:
            self._my_ebay_cache = result
            self._my_ebay_cache_time = datetime.now()

        return result

    async def _fetch_my_ebay_list(self, list_type: str) -> list[dict[str, Any]]:
        """Fetch all pages of a specific MyeBay list.
        
        Args:
            list_type: One of "BidList", "WatchList", or "WonList"
            
        Returns:
            Combined list of all items across all pages
        """
        all_items = []
        page_number = 1
        max_pages = 10  # Safety limit to prevent infinite loops
        
        while page_number <= max_pages:
            try:
                xml_request = f"""<?xml version="1.0" encoding="utf-8"?>
<GetMyeBayBuyingRequest xmlns="urn:ebay:apis:eBLBaseComponents">
  <RequesterCredentials>
    <eBayAuthToken>{self._token}</eBayAuthToken>
  </RequesterCredentials>
  <{list_type}>
    <Include>true</Include>
    <Pagination>
      <EntriesPerPage>200</EntriesPerPage>
      <PageNumber>{page_number}</PageNumber>
    </Pagination>
  </{list_type}>
  <DetailLevel>ReturnAll</DetailLevel>
</GetMyeBayBuyingRequest>"""

                headers = {
                    "X-EBAY-API-SITEID": "3" if self._site_id == "EBAY-GB" else "0",
                    "X-EBAY-API-COMPATIBILITY-LEVEL": "967",
                    "X-EBAY-API-CALL-NAME": "GetMyeBayBuying",
                    "X-EBAY-API-APP-NAME": self._app_id,
                    "X-EBAY-API-DEV-NAME": self._dev_id,
                    "X-EBAY-API-CERT-NAME": self._cert_id,
                    "Content-Type": "text/xml",
                }

                self._track_api_call("trading")

                async with self._session.post(
                    TRADING_API_URL, data=xml_request, headers=headers
                ) as response:
                    if response.status != 200:
                        _LOGGER.error("%s page %d error: Status %s", list_type, page_number, response.status)
                        break

                    xml_text = await response.text()
                    root = ET.fromstring(xml_text)
                    namespace = {"ns": "urn:ebay:apis:eBLBaseComponents"}
                    
                    # Parse items from this page
                    if list_type == "BidList":
                        page_items = self._parse_bid_list(root)
                    elif list_type == "WatchList":
                        page_items = self._parse_watch_list(root)
                    else:  # WonList
                        page_items = self._parse_won_list(root)
                    
                    all_items.extend(page_items)
                    
                    # Check pagination to see if there are more pages
                    pagination_elem = root.find(f".//ns:{list_type}/ns:PaginationResult", namespace)
                    if pagination_elem is not None:
                        total_pages_elem = pagination_elem.find("ns:TotalNumberOfPages", namespace)
                        total_entries_elem = pagination_elem.find("ns:TotalNumberOfEntries", namespace)
                        
                        if total_pages_elem is not None:
                            total_pages = int(total_pages_elem.text)
                            total_entries = total_entries_elem.text if total_entries_elem is not None else "unknown"
                            
                            _LOGGER.debug("%s page %d/%d - got %d items (total: %s)",
                                        list_type, page_number, total_pages, len(page_items), total_entries)
                            
                            # Check if we need to fetch more pages
                            if page_number >= total_pages:
                                _LOGGER.info("%s - fetched all %d items across %d pages",
                                           list_type, len(all_items), page_number)
                                break
                        else:
                            # No total pages means this is the last page
                            break
                    else:
                        # No pagination element means single page result
                        break
                    
                    page_number += 1
                    
            except Exception as err:
                _LOGGER.error("Error fetching %s page %d: %s", list_type, page_number, err)
                break
        
        if page_number > max_pages:
            _LOGGER.warning("%s hit page limit (%d pages). Got %d items but there may be more.",
                          list_type, max_pages, len(all_items))
        
        return all_items

    async def get_item(self, item_id: str) -> dict[str, Any]:
        """Get detailed information about a specific item."""
        _LOGGER.debug("Fetching item details for item_id: %s", item_id)
        
        # Track API call
        self._track_api_call("shopping")
        
        try:
            params = {
                "callname": "GetSingleItem",
                "responseencoding": "JSON",
                "appid": self._app_id,
                "siteid": "3" if self._site_id == "EBAY-GB" else "0",
                "version": "967",
                "ItemID": item_id,
                "IncludeSelector": "Details",
            }

            async with self._session.get(SHOPPING_API_URL, params=params) as response:
                _LOGGER.debug(
                    "eBay Shopping API call (GetSingleItem) - Status: %s, Item: %s",
                    response.status,
                    item_id
                )
                
                if response.status != 200:
                    _LOGGER.warning("Failed to fetch item %s: HTTP %s", item_id, response.status)
                    return {}

                data = await response.json()
                if "Item" in data:
                    _LOGGER.debug("Item details retrieved successfully for item_id: %s", item_id)
                    return self._parse_shopping_item(data["Item"])

                _LOGGER.debug("No item data found for item_id: %s", item_id)
                return {}

        except Exception as err:
            _LOGGER.error("Error fetching item %s: %s", item_id, err)
            return {}

    def _track_api_call(self, api_name: str) -> None:
        """Track an API call for rate limit monitoring."""
        if api_name in self._api_calls:
            self._api_calls[api_name]["count"] += 1
            
            # Log every 10th call
            count = self._api_calls[api_name]["count"]
            if count % 10 == 0:
                _LOGGER.info(
                    "API call count - %s: %d calls since %s",
                    api_name.upper(),
                    count,
                    self._api_calls[api_name]["last_reset"].strftime("%Y-%m-%d %H:%M:%S")
                )

    def get_rate_limits(self) -> dict[str, Any]:
        """Get local API call tracking information.
        
        Note: This returns local tracking data, not actual eBay quotas.
        eBay's Analytics API requires OAuth 2.0 which is not available with Auth'n'Auth tokens.
        
        Returns:
            Dictionary containing local API call counts
        """
        now = datetime.now()
        result = {
            "tracking_start": min(
                self._api_calls[api]["last_reset"] 
                for api in self._api_calls
            ).isoformat(),
            "current_time": now.isoformat(),
            "apis": []
        }
        
        total_calls = 0
        
        for api_name, data in self._api_calls.items():
            elapsed = (now - data["last_reset"]).total_seconds() / 3600  # hours
            calls_per_hour = data["count"] / elapsed if elapsed > 0 else 0
            
            api_info = {
                "api_name": api_name,
                "calls_made": data["count"],
                "tracking_since": data["last_reset"].isoformat(),
                "hours_elapsed": round(elapsed, 2),
                "calls_per_hour": round(calls_per_hour, 1),
                "estimated_daily": round(calls_per_hour * 24, 0),
            }
            
            result["apis"].append(api_info)
            total_calls += data["count"]
        
        result["total_calls"] = total_calls
        result["estimated_daily_total"] = sum(api["estimated_daily"] for api in result["apis"])
        
        return result

    def reset_rate_limit_tracking(self) -> None:
        """Reset API call tracking counters."""
        now = datetime.now()
        for api_name in self._api_calls:
            self._api_calls[api_name] = {"count": 0, "last_reset": now}
        _LOGGER.info("API call tracking reset")

    def _parse_browse_item(self, item: dict) -> dict[str, Any]:
        """Parse a Browse API item summary.
        
        Browse API structure:
        - Direct field access (no array wrappers)
        - Price as object with value/currency
        - Seller as nested object
        - For auctions: currentBidPrice contains the current/starting bid
        """
        try:
            # Get price info
            # For Buy It Now: uses 'price' field
            # For Auctions: uses 'currentBidPrice' field (contains starting bid if no bids yet)
            price_obj = item.get("price")
            
            if not price_obj or float(price_obj.get("value", "0")) == 0.0:
                # Try currentBidPrice for auctions
                price_obj = item.get("currentBidPrice")
            
            if not price_obj:
                # Fallback to startingBid if available
                price_obj = item.get("startingBid", {})
            
            price_value = float(price_obj.get("value", "0"))
            price_currency = price_obj.get("currency", "GBP")
            
            # Use convertedFrom if original currency differs (eBay's automatic conversion)
            if "convertedFromValue" in price_obj and "convertedFromCurrency" in price_obj:
                original_value = float(price_obj.get("convertedFromValue", "0"))
                original_currency = price_obj.get("convertedFromCurrency", "GBP")
                # Prefer original currency for UK/EU sellers
                if original_currency in ["GBP", "EUR"]:
                    price_value = original_value
                    price_currency = original_currency
            
            # Get seller info
            seller_obj = item.get("seller", {})
            seller_username = seller_obj.get("username", "")
            seller_feedback_score = int(seller_obj.get("feedbackScore", "0"))
            seller_feedback_percent = float(seller_obj.get("feedbackPercentage", "0"))
            
            # Build result matching our standard format
            result = {
                ATTR_ITEM_ID: item.get("itemId", ""),
                ATTR_TITLE: item.get("title", ""),
                ATTR_SELLER_USERNAME: seller_username,
                ATTR_SELLER_FEEDBACK_SCORE: seller_feedback_score,
                ATTR_SELLER_POSITIVE_PERCENT: seller_feedback_percent,
                ATTR_CURRENT_PRICE: {
                    "value": price_value,
                    "currency": price_currency,
                },
                ATTR_ITEM_URL: item.get("itemWebUrl", ""),
                ATTR_LISTING_TYPE: self._map_browse_buying_options(item.get("buyingOptions", [])),
                ATTR_BID_COUNT: int(item.get("bidCount", "0")),
            }
            
            # Add formatted price for display in automations/events
            result["formatted_price"] = format_price(result[ATTR_CURRENT_PRICE])
            
            # Add end time if it's an auction
            if "itemEndDate" in item:
                result[ATTR_END_TIME] = item["itemEndDate"]
            
            # Add seller URL
            if seller_username:
                result[ATTR_SELLER_URL] = f"https://www.ebay.co.uk/usr/{seller_username}"
            
            # Add image
            image_obj = item.get("image", {})
            if image_obj and "imageUrl" in image_obj:
                result[ATTR_IMAGE_URL] = image_obj["imageUrl"]
            elif "thumbnailImages" in item and item["thumbnailImages"]:
                result[ATTR_IMAGE_URL] = item["thumbnailImages"][0].get("imageUrl", "")
            
            return result
            
        except Exception as err:
            _LOGGER.error("Error parsing Browse API item: %s, Item data: %s", err, item)
            return {}

    def _map_browse_buying_options(self, buying_options: list[str]) -> str:
        """Map Browse API buyingOptions to our listing type format.
        
        Browse API returns: ["AUCTION"], ["FIXED_PRICE"], or ["AUCTION", "FIXED_PRICE"]
        We use: "Auction", "FixedPrice", or "both"
        """
        if not buying_options:
            return "Unknown"
        
        has_auction = "AUCTION" in buying_options
        has_fixed = "FIXED_PRICE" in buying_options or "BUY_NOW" in buying_options
        
        if has_auction and has_fixed:
            return "both"
        elif has_auction:
            return "Auction"
        elif has_fixed:
            return "FixedPrice"
        else:
            return "Unknown"

    def _parse_bid_list(self, root: ET.Element) -> list[dict[str, Any]]:
        """Parse bid list from XML response."""
        namespace = {"ns": "urn:ebay:apis:eBLBaseComponents"}
        items = []

        bid_list = root.find(".//ns:BidList/ns:ItemArray", namespace)
        if bid_list is not None:
            for item_elem in bid_list.findall("ns:Item", namespace):
                items.append(self._parse_trading_item(item_elem, namespace, "bid"))

        return items

    def _parse_watch_list(self, root: ET.Element) -> list[dict[str, Any]]:
        """Parse watch list from XML response."""
        namespace = {"ns": "urn:ebay:apis:eBLBaseComponents"}
        items = []

        watch_list = root.find(".//ns:WatchList/ns:ItemArray", namespace)
        if watch_list is not None:
            for item_elem in watch_list.findall("ns:Item", namespace):
                items.append(self._parse_trading_item(item_elem, namespace, "watch"))

        return items

    def _parse_won_list(self, root: ET.Element) -> list[dict[str, Any]]:
        """Parse won/purchased list from XML response."""
        namespace = {"ns": "urn:ebay:apis:eBLBaseComponents"}
        items = []

        won_list = root.find(".//ns:WonList/ns:OrderTransactionArray", namespace)
        if won_list is not None:
            for order_elem in won_list.findall("ns:OrderTransaction", namespace):
                item = self._parse_purchase_item(order_elem, namespace)
                if item:
                    items.append(item)

        return items

    def _parse_trading_item(
        self, item_elem: ET.Element, namespace: dict, item_type: str
    ) -> dict[str, Any]:
        """Parse a Trading API item element."""
        def get_text(path: str, default: str = "") -> str:
            elem = item_elem.find(path, namespace)
            return elem.text if elem is not None and elem.text else default

        # Get listing type and translate eBay's internal codes
        listing_type_raw = get_text("ns:ListingType")
        listing_type_display = listing_type_raw
        if listing_type_raw == "Chinese":
            listing_type_display = "Auction"
        elif listing_type_raw == "FixedPriceItem":
            listing_type_display = "Buy It Now"
        
        parsed = {
            ATTR_ITEM_ID: get_text("ns:ItemID"),
            ATTR_TITLE: get_text("ns:Title"),
            ATTR_LISTING_TYPE: listing_type_display,
        }

        # Current price
        price_elem = item_elem.find("ns:SellingStatus/ns:CurrentPrice", namespace)
        if price_elem is not None and price_elem.text:
            parsed[ATTR_CURRENT_PRICE] = {
                "value": float(price_elem.text) if price_elem.text else 0.0,
                "currency": price_elem.get("currencyID", "GBP"),
            }
        else:
            # Try alternative price paths for different item types
            # Some items may have price in different locations
            convert_price_elem = item_elem.find("ns:SellingStatus/ns:ConvertedCurrentPrice", namespace)
            if convert_price_elem is not None and convert_price_elem.text:
                parsed[ATTR_CURRENT_PRICE] = {
                    "value": float(convert_price_elem.text),
                    "currency": convert_price_elem.get("currencyID", "GBP"),
                }
            else:
                # Default to 0 if no price found
                parsed[ATTR_CURRENT_PRICE] = {
                    "value": 0.0,
                    "currency": "GBP",
                }
        
        # Always add formatted price for consistency
        parsed["formatted_price"] = format_price(parsed[ATTR_CURRENT_PRICE])

        # End time and time remaining
        end_time = get_text("ns:ListingDetails/ns:EndTime")
        if end_time:
            parsed[ATTR_END_TIME] = end_time
            parsed[ATTR_TIME_REMAINING] = self._calculate_time_remaining(end_time)

        # Item URL - try multiple paths
        item_url = get_text("ns:ListingDetails/ns:ViewItemURL")
        if not item_url:
            item_url = get_text("ns:ListingInfo/ns:ViewItemURL")
        if not item_url:
            # Construct URL from item ID as fallback
            item_id = get_text("ns:ItemID")
            if item_id:
                item_url = f"https://www.ebay.co.uk/itm/{item_id}"
        parsed[ATTR_ITEM_URL] = item_url

        # Seller info
        seller_username = get_text("ns:Seller/ns:UserID")
        if seller_username:
            parsed[ATTR_SELLER_USERNAME] = seller_username
            parsed[ATTR_SELLER_FEEDBACK_SCORE] = int(get_text("ns:Seller/ns:FeedbackScore", "0"))
            
            # Parse positive feedback percentage - try multiple paths
            pos_feedback = get_text("ns:Seller/ns:PositiveFeedbackPercent", "")
            if not pos_feedback:
                # Try alternative path
                pos_feedback = get_text("ns:Seller/ns:FeedbackRatingStar", "")
            
            if pos_feedback and pos_feedback != "0" and pos_feedback != "0.0":
                try:
                    parsed[ATTR_SELLER_POSITIVE_PERCENT] = float(pos_feedback)
                except (ValueError, TypeError):
                    parsed[ATTR_SELLER_POSITIVE_PERCENT] = 0.0
            else:
                # eBay API doesn't return percentage in GetMyeBayBuying
                # We'll leave it as 0 and just show the feedback score
                parsed[ATTR_SELLER_POSITIVE_PERCENT] = 0.0
            
            parsed[ATTR_SELLER_URL] = f"https://www.ebay.co.uk/usr/{seller_username}"
            
            # Try multiple paths for seller location
            seller_loc = get_text("ns:Seller/ns:RegistrationAddress/ns:Country")
            if not seller_loc:
                seller_loc = get_text("ns:Seller/ns:Site")
            if not seller_loc:
                # Try getting from item location as fallback
                seller_loc = get_text("ns:Location")
            if seller_loc:
                parsed[ATTR_SELLER_LOCATION] = seller_loc

        # Image
        picture_url = get_text("ns:PictureDetails/ns:PictureURL")
        if picture_url:
            parsed[ATTR_IMAGE_URL] = picture_url

        # Bid-specific fields
        if item_type == "bid":
            # Check if high bidder by comparing with authenticated user's eBay username
            high_bidder_username = get_text("ns:SellingStatus/ns:HighBidder/ns:UserID")
            
            # Debug logging to troubleshoot is_high_bidder
            _LOGGER.debug(
                "Item %s - High bidder: '%s', Authenticated user: '%s', Match: %s",
                parsed.get(ATTR_ITEM_ID, "unknown"),
                high_bidder_username,
                self._ebay_username,
                high_bidder_username.lower() == self._ebay_username.lower() if high_bidder_username and self._ebay_username else False
            )
            
            parsed[ATTR_IS_HIGH_BIDDER] = (
                high_bidder_username != "" and 
                self._ebay_username is not None and 
                high_bidder_username.lower() == self._ebay_username.lower()
            )
            
            # Check reserve met - try multiple paths
            reserve_met_text = get_text("ns:ReserveMet")
            if not reserve_met_text:
                reserve_met_text = get_text("ns:SellingStatus/ns:ReserveMet")
            parsed[ATTR_RESERVE_MET] = reserve_met_text.lower() == "true" if reserve_met_text else False
            
            parsed[ATTR_BID_COUNT] = int(get_text("ns:SellingStatus/ns:BidCount", "0"))

        # Watchlist-specific fields
        if item_type == "watch":
            parsed[ATTR_WATCHERS] = int(get_text("ns:WatchCount", "0"))

        return parsed

    def _parse_purchase_item(
        self, order_elem: ET.Element, namespace: dict
    ) -> dict[str, Any] | None:
        """Parse a purchase/won item from OrderTransaction."""
        txn_elem = order_elem.find("ns:Transaction", namespace)
        if txn_elem is None:
            return None

        item_elem = txn_elem.find("ns:Item", namespace)
        if item_elem is None:
            return None

        def get_text(path: str, default: str = "", elem: ET.Element = item_elem) -> str:
            found = elem.find(path, namespace)
            return found.text if found is not None and found.text else default

        parsed = {
            ATTR_ITEM_ID: get_text("ns:ItemID"),
            ATTR_TITLE: get_text("ns:Title"),
            ATTR_ITEM_URL: get_text("ns:ListingDetails/ns:ViewItemURL"),
        }
        
        # Debug: Log XML structure for first purchase to help diagnose
        if not hasattr(self, '_logged_purchase_xml'):
            self._logged_purchase_xml = True
            _LOGGER.debug("=== PURCHASE XML STRUCTURE DEBUG ===")
            _LOGGER.debug("Item ID: %s", parsed[ATTR_ITEM_ID])
            _LOGGER.debug("Transaction element tags: %s", 
                         [elem.tag.split('}')[-1] for elem in txn_elem.iter()][:30])
            # Log all elements with 'Price' in their tag name
            for elem in txn_elem.iter():
                tag_name = elem.tag.split('}')[-1]
                if 'Price' in tag_name or 'price' in tag_name:
                    currency = elem.get('currencyID', 'N/A')
                    _LOGGER.debug("Found price element: %s = %s (currency: %s)", 
                                 tag_name, elem.text, currency)
            _LOGGER.debug("=== END PURCHASE XML STRUCTURE DEBUG ===")


        # Transaction price - try multiple paths
        # eBay can return prices in different locations depending on the transaction type
        price_elem = txn_elem.find("ns:TransactionPrice", namespace)
        
        if price_elem is not None and price_elem.text:
            parsed[ATTR_CURRENT_PRICE] = {
                "value": float(price_elem.text),
                "currency": price_elem.get("currencyID", "GBP"),
            }
            _LOGGER.debug("Purchase price found at TransactionPrice: %s %s", 
                         price_elem.text, price_elem.get("currencyID", "GBP"))
        else:
            # Try alternative paths
            # 1. Try ActualPrice (sometimes used for best offers)
            price_elem = txn_elem.find("ns:ActualPrice", namespace)
            if price_elem is not None and price_elem.text:
                parsed[ATTR_CURRENT_PRICE] = {
                    "value": float(price_elem.text),
                    "currency": price_elem.get("currencyID", "GBP"),
                }
                _LOGGER.debug("Purchase price found at ActualPrice: %s %s", 
                             price_elem.text, price_elem.get("currencyID", "GBP"))
            else:
                # 2. Try FinalValueFee/Transaction/TotalPrice path
                total_price_elem = txn_elem.find("ns:TotalPrice", namespace)
                if total_price_elem is not None and total_price_elem.text:
                    parsed[ATTR_CURRENT_PRICE] = {
                        "value": float(total_price_elem.text),
                        "currency": total_price_elem.get("currencyID", "GBP"),
                    }
                    _LOGGER.debug("Purchase price found at TotalPrice: %s %s", 
                                 total_price_elem.text, total_price_elem.get("currencyID", "GBP"))
                else:
                    # 3. Try getting from the item's SellingStatus (fallback)
                    price_elem = item_elem.find("ns:SellingStatus/ns:CurrentPrice", namespace)
                    if price_elem is not None and price_elem.text:
                        parsed[ATTR_CURRENT_PRICE] = {
                            "value": float(price_elem.text),
                            "currency": price_elem.get("currencyID", "GBP"),
                        }
                        _LOGGER.debug("Purchase price found at Item/SellingStatus/CurrentPrice: %s %s", 
                                     price_elem.text, price_elem.get("currencyID", "GBP"))
                    else:
                        # Log warning if we couldn't find price anywhere
                        item_id = get_text("ns:ItemID")
                        _LOGGER.warning(
                            "Could not find price for purchase item %s. "
                            "Tried TransactionPrice, ActualPrice, TotalPrice, and CurrentPrice paths. "
                            "Defaulting to £0.00",
                            item_id
                        )
                        parsed[ATTR_CURRENT_PRICE] = {
                            "value": 0.0,
                            "currency": "GBP",
                        }
        
        # Always add formatted price for consistency
        parsed["formatted_price"] = format_price(parsed[ATTR_CURRENT_PRICE])

        # Seller info
        seller_username = get_text("ns:Seller/ns:UserID")
        if seller_username:
            parsed[ATTR_SELLER_USERNAME] = seller_username
            parsed[ATTR_SELLER_FEEDBACK_SCORE] = int(get_text("ns:Seller/ns:FeedbackScore", "0"))
            parsed[ATTR_SELLER_POSITIVE_PERCENT] = float(get_text("ns:Seller/ns:PositiveFeedbackPercent", "0"))
            parsed[ATTR_SELLER_URL] = f"https://www.ebay.co.uk/usr/{seller_username}"

        # Image
        picture_url = get_text("ns:PictureDetails/ns:PictureURL")
        if picture_url:
            parsed[ATTR_IMAGE_URL] = picture_url

        # Shipping status - try multiple approaches
        parsed[ATTR_SHIPPING_STATUS] = "pending"
        
        # Try to find Order element in the transaction
        order_elem_parent = order_elem.find("ns:Order", namespace)
        
        # Also try at the transaction level
        if order_elem_parent is None:
            # Check if there's shipping info at transaction level
            shipping_status = get_text("ns:Status/ns:ShippingStatus", elem=txn_elem)
            if shipping_status:
                if "Shipped" in shipping_status or "shipped" in shipping_status.lower():
                    parsed[ATTR_SHIPPING_STATUS] = "shipped"
                elif "Delivered" in shipping_status or "delivered" in shipping_status.lower():
                    parsed[ATTR_SHIPPING_STATUS] = "delivered"
        else:
            # Check order status
            status = get_text("ns:OrderStatus", elem=order_elem_parent)
            if status:
                status_lower = status.lower()
                if "shipped" in status_lower or "ship" in status_lower:
                    parsed[ATTR_SHIPPING_STATUS] = "shipped"
                elif "delivered" in status_lower or "deliver" in status_lower:
                    parsed[ATTR_SHIPPING_STATUS] = "delivered"
                elif "complete" in status_lower:
                    parsed[ATTR_SHIPPING_STATUS] = "delivered"
                elif "active" in status_lower:
                    # Active orders are typically shipped
                    parsed[ATTR_SHIPPING_STATUS] = "shipped"

            # Try to get tracking number
            tracking = get_text("ns:ShippingDetails/ns:ShipmentTrackingDetails/ns:ShipmentTrackingNumber", elem=order_elem_parent)
            if not tracking:
                # Try alternative path
                tracking = get_text("ns:ShippingInfo/ns:ShipmentTrackingDetails/ns:ShipmentTrackingNumber", elem=order_elem_parent)
            
            if tracking:
                parsed[ATTR_TRACKING_NUMBER] = tracking
                # If we have a tracking number, it's shipped
                if parsed[ATTR_SHIPPING_STATUS] == "pending":
                    parsed[ATTR_SHIPPING_STATUS] = "shipped"
        
        # Check shipping details at transaction level as another fallback
        if parsed[ATTR_SHIPPING_STATUS] == "pending":
            shipped_time = get_text("ns:ShippedTime", elem=txn_elem)
            if shipped_time:
                parsed[ATTR_SHIPPING_STATUS] = "shipped"

        return parsed

    def _parse_shopping_item(self, item: dict) -> dict[str, Any]:
        """Parse Shopping API item.
        
        Used by get_item() which is called to verify final auction status.
        Must include:
        - high_bidder_username: For won/lost determination
        - listing_status: To verify auction actually ended (vs just removed from bids)
        - end_time: For logging and verification
        """
        parsed = {
            ATTR_ITEM_ID: item.get("ItemID", ""),
            ATTR_TITLE: item.get("Title", ""),
            ATTR_DESCRIPTION: item.get("Description", ""),
        }
        
        # Extract listing status - CRITICAL for preventing false won/lost events
        # Values: Active, Completed, Ended, Cancelled, etc.
        # This prevents firing won/lost when item is just removed from bids (outbid, retracted, etc.)
        parsed["listing_status"] = item.get("ListingStatus", "Unknown")
        
        # Extract end time for verification
        end_time = item.get("EndTime", "")
        if end_time:
            parsed["end_time"] = end_time
        
        # Extract high bidder information for auction verification
        # This is critical for determining if user won an ended auction
        current_price = item.get("CurrentPrice", {})
        if isinstance(current_price, dict):
            parsed[ATTR_CURRENT_PRICE] = {
                "value": float(current_price.get("Value", 0)),
                "currency": current_price.get("CurrencyID", "GBP"),
            }
            parsed["formatted_price"] = format_price(parsed[ATTR_CURRENT_PRICE])
        
        # Get high bidder from SellingStatus
        selling_status = item.get("SellingStatus", {})
        if isinstance(selling_status, dict):
            high_bidder = selling_status.get("HighBidder", {})
            if isinstance(high_bidder, dict):
                # This is the critical field for auction won/lost determination
                parsed["high_bidder_username"] = high_bidder.get("UserID", "")
                
        return parsed

    def _calculate_time_remaining(self, end_time: str) -> str:
        """Calculate human-readable time remaining."""
        try:
            # Handle different date formats
            if "T" in end_time:
                end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            else:
                end = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
                
            now = datetime.now(end.tzinfo) if end.tzinfo else datetime.now()
            delta = end - now

            if delta.total_seconds() < 0:
                return "Ended"

            days = delta.days
            hours = delta.seconds // 3600
            minutes = (delta.seconds % 3600) // 60

            parts = []
            if days > 0:
                parts.append(f"{days} day{'s' if days != 1 else ''}")
            if hours > 0:
                parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
            if minutes > 0 and days == 0:
                parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")

            return " ".join(parts) if parts else "Less than 1 minute"

        except Exception as err:
            _LOGGER.debug("Error calculating time remaining: %s", err)
            return "Unknown"
