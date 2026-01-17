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

# eBay API Endpoints
FINDING_API_URL = "https://svcs.ebay.com/services/search/FindingService/v1"
SHOPPING_API_URL = "https://open.api.ebay.com/shopping"
TRADING_API_URL = "https://api.ebay.com/ws/api.dll"


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

    async def search_items(
        self,
        query: str,
        site_id: str | None = None,
        category_id: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        listing_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search for items on eBay using Finding API."""
        try:
            params = {
                "OPERATION-NAME": "findItemsAdvanced",
                "SERVICE-VERSION": "1.0.0",
                "SECURITY-APPNAME": self._app_id,
                "RESPONSE-DATA-FORMAT": "JSON",
                "keywords": query,
            }

            if category_id:
                params["categoryId"] = category_id

            # Add item filters
            filter_index = 0
            if min_price:
                params[f"itemFilter({filter_index}).name"] = "MinPrice"
                params[f"itemFilter({filter_index}).value"] = str(min_price)
                filter_index += 1

            if max_price:
                params[f"itemFilter({filter_index}).name"] = "MaxPrice"
                params[f"itemFilter({filter_index}).value"] = str(max_price)
                filter_index += 1

            if listing_type and listing_type != "All":
                params[f"itemFilter({filter_index}).name"] = "ListingType"
                params[f"itemFilter({filter_index}).value"] = listing_type

            async with self._session.get(FINDING_API_URL, params=params) as response:
                if response.status != 200:
                    raise HomeAssistantError(f"eBay API error: {response.status}")

                data = await response.json()
                
                # Parse response
                items = []
                search_result = data.get("findItemsAdvancedResponse", [{}])[0].get("searchResult", [{}])[0]
                
                if search_result.get("@count", "0") != "0":
                    item_list = search_result.get("item", [])
                    for item in item_list:
                        items.append(self._parse_finding_item(item))

                return items

        except Exception as err:
            _LOGGER.error("Error searching eBay: %s", err)
            return []

    async def get_my_ebay_buying(self) -> dict[str, list[dict[str, Any]]]:
        """Get all buying activity (bids, watchlist, purchases) using Trading API."""
        try:
            # Build XML request
            xml_request = f"""<?xml version="1.0" encoding="utf-8"?>
<GetMyeBayBuyingRequest xmlns="urn:ebay:apis:eBLBaseComponents">
  <RequesterCredentials>
    <eBayAuthToken>{self._token}</eBayAuthToken>
  </RequesterCredentials>
  <BidList>
    <Include>true</Include>
  </BidList>
  <WatchList>
    <Include>true</Include>
  </WatchList>
  <WonList>
    <Include>true</Include>
  </WonList>
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

            async with self._session.post(
                TRADING_API_URL, data=xml_request, headers=headers
            ) as response:
                if response.status != 200:
                    _LOGGER.error("eBay Trading API error: %s", response.status)
                    return {"bids": [], "watchlist": [], "purchases": []}

                xml_text = await response.text()
                root = ET.fromstring(xml_text)

                result = {
                    "bids": self._parse_bid_list(root),
                    "watchlist": self._parse_watch_list(root),
                    "purchases": self._parse_won_list(root),
                }

                return result

        except Exception as err:
            _LOGGER.error("Error fetching MyeBay data: %s", err)
            return {"bids": [], "watchlist": [], "purchases": []}

    async def get_item(self, item_id: str) -> dict[str, Any]:
        """Get detailed information about a specific item."""
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
                if response.status != 200:
                    return {}

                data = await response.json()
                if "Item" in data:
                    return self._parse_shopping_item(data["Item"])

                return {}

        except Exception as err:
            _LOGGER.error("Error fetching item %s: %s", item_id, err)
            return {}

    def _parse_finding_item(self, item: dict) -> dict[str, Any]:
        """Parse a Finding API item."""
        seller_info = item.get("sellerInfo", [{}])[0]
        selling_status = item.get("sellingStatus", [{}])[0]
        listing_info = item.get("listingInfo", [{}])[0]
        
        result = {
            ATTR_ITEM_ID: item.get("itemId", [""])[0],
            ATTR_TITLE: item.get("title", [""])[0],
            ATTR_SELLER_USERNAME: seller_info.get("sellerUserName", [""])[0],
            ATTR_SELLER_FEEDBACK_SCORE: int(seller_info.get("feedbackScore", ["0"])[0]),
            ATTR_SELLER_POSITIVE_PERCENT: float(seller_info.get("positiveFeedbackPercent", ["0"])[0]),
            ATTR_CURRENT_PRICE: {
                "value": float(selling_status.get("currentPrice", [{"__value__": "0"}])[0].get("__value__", "0")),
                "currency": selling_status.get("currentPrice", [{"@currencyId": "GBP"}])[0].get("@currencyId", "GBP"),
            },
            ATTR_END_TIME: listing_info.get("endTime", [""])[0],
            ATTR_ITEM_URL: item.get("viewItemURL", [""])[0],
            ATTR_LISTING_TYPE: listing_info.get("listingType", [""])[0],
            ATTR_BID_COUNT: int(selling_status.get("bidCount", ["0"])[0]),
        }

        # Add seller URL
        if result[ATTR_SELLER_USERNAME]:
            result[ATTR_SELLER_URL] = f"https://www.ebay.co.uk/usr/{result[ATTR_SELLER_USERNAME]}"

        # Add image
        if "pictureURLLarge" in item:
            result[ATTR_IMAGE_URL] = item["pictureURLLarge"][0]
        elif "galleryURL" in item:
            result[ATTR_IMAGE_URL] = item["galleryURL"][0]

        return result

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

        parsed = {
            ATTR_ITEM_ID: get_text("ns:ItemID"),
            ATTR_TITLE: get_text("ns:Title"),
            ATTR_LISTING_TYPE: get_text("ns:ListingType"),
        }

        # Current price
        price_elem = item_elem.find("ns:SellingStatus/ns:CurrentPrice", namespace)
        if price_elem is not None:
            parsed[ATTR_CURRENT_PRICE] = {
                "value": float(price_elem.text) if price_elem.text else 0.0,
                "currency": price_elem.get("currencyID", "GBP"),
            }

        # End time and time remaining
        end_time = get_text("ns:ListingDetails/ns:EndTime")
        if end_time:
            parsed[ATTR_END_TIME] = end_time
            parsed[ATTR_TIME_REMAINING] = self._calculate_time_remaining(end_time)

        # Item URL
        parsed[ATTR_ITEM_URL] = get_text("ns:ListingDetails/ns:ViewItemURL")

        # Seller info
        seller_username = get_text("ns:Seller/ns:UserID")
        if seller_username:
            parsed[ATTR_SELLER_USERNAME] = seller_username
            parsed[ATTR_SELLER_FEEDBACK_SCORE] = int(get_text("ns:Seller/ns:FeedbackScore", "0"))
            parsed[ATTR_SELLER_POSITIVE_PERCENT] = float(get_text("ns:Seller/ns:PositiveFeedbackPercent", "0"))
            parsed[ATTR_SELLER_URL] = f"https://www.ebay.co.uk/usr/{seller_username}"
            parsed[ATTR_SELLER_LOCATION] = get_text("ns:Seller/ns:RegistrationAddress/ns:Country")

        # Image
        picture_url = get_text("ns:PictureDetails/ns:PictureURL")
        if picture_url:
            parsed[ATTR_IMAGE_URL] = picture_url

        # Bid-specific fields
        if item_type == "bid":
            # Check if high bidder - this is simplified, in reality you'd need to compare usernames
            parsed[ATTR_IS_HIGH_BIDDER] = get_text("ns:SellingStatus/ns:HighBidder/ns:UserID") != ""
            parsed[ATTR_RESERVE_MET] = get_text("ns:ReserveMet") == "true"
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

        # Transaction price
        price_elem = txn_elem.find("ns:TransactionPrice", namespace)
        if price_elem is not None:
            parsed[ATTR_CURRENT_PRICE] = {
                "value": float(price_elem.text) if price_elem.text else 0.0,
                "currency": price_elem.get("currencyID", "GBP"),
            }

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

        # Shipping status
        order_elem_parent = order_elem.find("ns:Order", namespace)
        if order_elem_parent is not None:
            status = get_text("ns:OrderStatus", elem=order_elem_parent)
            if "Shipped" in status:
                parsed[ATTR_SHIPPING_STATUS] = "shipped"
            elif "Delivered" in status:
                parsed[ATTR_SHIPPING_STATUS] = "delivered"
            else:
                parsed[ATTR_SHIPPING_STATUS] = "pending"

            # Tracking number
            tracking = get_text("ns:ShippingDetails/ns:ShipmentTrackingDetails/ns:ShipmentTrackingNumber", elem=order_elem_parent)
            if tracking:
                parsed[ATTR_TRACKING_NUMBER] = tracking

        return parsed

    def _parse_shopping_item(self, item: dict) -> dict[str, Any]:
        """Parse Shopping API item."""
        return {
            ATTR_ITEM_ID: item.get("ItemID", ""),
            ATTR_TITLE: item.get("Title", ""),
            ATTR_DESCRIPTION: item.get("Description", ""),
        }

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
