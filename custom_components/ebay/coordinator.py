"""Data update coordinators for eBay integration."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    EVENT_AUCTION_ENDING_SOON,
    EVENT_AUCTION_LOST,
    EVENT_AUCTION_WON,
    EVENT_BECAME_HIGH_BIDDER,
    EVENT_ITEM_DELIVERED,
    EVENT_ITEM_SHIPPED,
    EVENT_NEW_SEARCH_RESULT,
    EVENT_OUTBID,
)
from .ebay_api import EbayAPI

_LOGGER = logging.getLogger(__name__)


class EbayBidsCoordinator(DataUpdateCoordinator):
    """Coordinator for eBay bids."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: EbayAPI,
        account_name: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_bids_{account_name}",
            update_interval=update_interval,
        )
        self.api = api
        self.account_name = account_name
        self._previous_data: dict[str, Any] = {}

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch bid data."""
        try:
            data = await self.api.get_my_ebay_buying()
            bids = data.get("bids", [])

            # Fire events for changes
            self._check_bid_changes(bids)

            # Update previous data
            self._previous_data = {item["item_id"]: item for item in bids}

            return bids

        except Exception as err:
            raise UpdateFailed(f"Error fetching bids: {err}") from err

    def _check_bid_changes(self, current_bids: list[dict[str, Any]]) -> None:
        """Check for changes in bid status and fire events."""
        current_ids = {item["item_id"] for item in current_bids}
        previous_ids = set(self._previous_data.keys())

        for bid in current_bids:
            item_id = bid["item_id"]
            previous = self._previous_data.get(item_id)

            if not previous:
                # New bid - check if auction is ending soon
                self._check_ending_soon(bid)
                continue

            # Check if became high bidder
            if bid.get("is_high_bidder") and not previous.get("is_high_bidder"):
                self.hass.bus.async_fire(
                    EVENT_BECAME_HIGH_BIDDER,
                    {
                        "account": self.account_name,
                        "item": bid,
                    },
                )

            # Check if outbid
            elif not bid.get("is_high_bidder") and previous.get("is_high_bidder"):
                self.hass.bus.async_fire(
                    EVENT_OUTBID,
                    {
                        "account": self.account_name,
                        "item": bid,
                    },
                )

            # Check if auction ending soon
            self._check_ending_soon(bid)

        # Check for ended auctions
        for item_id in previous_ids - current_ids:
            previous = self._previous_data[item_id]
            # Auction ended - check if won or lost
            if previous.get("is_high_bidder"):
                self.hass.bus.async_fire(
                    EVENT_AUCTION_WON,
                    {
                        "account": self.account_name,
                        "item": previous,
                    },
                )
            else:
                self.hass.bus.async_fire(
                    EVENT_AUCTION_LOST,
                    {
                        "account": self.account_name,
                        "item": previous,
                    },
                )

    def _check_ending_soon(self, bid: dict[str, Any]) -> None:
        """Check if auction is ending soon."""
        try:
            end_time = datetime.fromisoformat(
                bid["end_time"].replace("Z", "+00:00")
            )
            now = datetime.now(end_time.tzinfo)
            minutes_remaining = (end_time - now).total_seconds() / 60

            # Fire event if less than 15 minutes remaining
            if 0 < minutes_remaining <= 15:
                # Only fire once by checking if we've already fired
                last_fired = getattr(self, f"_ending_soon_{bid['item_id']}", None)
                if not last_fired or (now - last_fired).total_seconds() > 600:
                    self.hass.bus.async_fire(
                        EVENT_AUCTION_ENDING_SOON,
                        {
                            "account": self.account_name,
                            "item": bid,
                            "minutes_remaining": int(minutes_remaining),
                        },
                    )
                    setattr(self, f"_ending_soon_{bid['item_id']}", now)

        except Exception as err:
            _LOGGER.debug("Error checking ending soon for %s: %s", bid["item_id"], err)


class EbayWatchlistCoordinator(DataUpdateCoordinator):
    """Coordinator for eBay watchlist."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: EbayAPI,
        account_name: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_watchlist_{account_name}",
            update_interval=update_interval,
        )
        self.api = api
        self.account_name = account_name

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch watchlist data."""
        try:
            data = await self.api.get_my_ebay_buying()
            return data.get("watchlist", [])

        except Exception as err:
            raise UpdateFailed(f"Error fetching watchlist: {err}") from err


class EbayPurchasesCoordinator(DataUpdateCoordinator):
    """Coordinator for eBay purchases."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: EbayAPI,
        account_name: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_purchases_{account_name}",
            update_interval=update_interval,
        )
        self.api = api
        self.account_name = account_name
        self._previous_data: dict[str, Any] = {}

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch purchases data."""
        try:
            data = await self.api.get_my_ebay_buying()
            purchases = data.get("purchases", [])

            # Fire events for shipping changes
            self._check_shipping_changes(purchases)

            # Update previous data
            self._previous_data = {item["item_id"]: item for item in purchases}

            return purchases

        except Exception as err:
            raise UpdateFailed(f"Error fetching purchases: {err}") from err

    def _check_shipping_changes(self, current_purchases: list[dict[str, Any]]) -> None:
        """Check for changes in shipping status and fire events."""
        for purchase in current_purchases:
            item_id = purchase["item_id"]
            previous = self._previous_data.get(item_id)

            if not previous:
                continue

            current_status = purchase.get("shipping_status")
            previous_status = previous.get("shipping_status")

            # Check if item was shipped
            if current_status == "shipped" and previous_status != "shipped":
                self.hass.bus.async_fire(
                    EVENT_ITEM_SHIPPED,
                    {
                        "account": self.account_name,
                        "item": purchase,
                    },
                )

            # Check if item was delivered
            elif current_status == "delivered" and previous_status != "delivered":
                self.hass.bus.async_fire(
                    EVENT_ITEM_DELIVERED,
                    {
                        "account": self.account_name,
                        "item": purchase,
                    },
                )


class EbaySearchCoordinator(DataUpdateCoordinator):
    """Coordinator for eBay search."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: EbayAPI,
        account_name: str,
        search_id: str,
        search_config: dict[str, Any],
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_search_{account_name}_{search_id}",
            update_interval=update_interval,
        )
        self.api = api
        self.account_name = account_name
        self.search_id = search_id
        self.search_config = search_config
        self._previous_item_ids: set[str] = set()

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch search results."""
        try:
            results = await self.api.search_items(
                query=self.search_config["search_query"],
                site_id=self.search_config.get("site"),
                category_id=self.search_config.get("category_id"),
                min_price=self.search_config.get("min_price"),
                max_price=self.search_config.get("max_price"),
                listing_type=self.search_config.get("listing_type"),
            )

            # Fire events for new items
            self._check_new_items(results)

            # Update previous item IDs
            self._previous_item_ids = {item["item_id"] for item in results}

            return results

        except Exception as err:
            raise UpdateFailed(f"Error fetching search results: {err}") from err

    def _check_new_items(self, current_results: list[dict[str, Any]]) -> None:
        """Check for new items in search results and fire events."""
        current_ids = {item["item_id"] for item in current_results}
        new_ids = current_ids - self._previous_item_ids

        for item in current_results:
            if item["item_id"] in new_ids:
                self.hass.bus.async_fire(
                    EVENT_NEW_SEARCH_RESULT,
                    {
                        "account": self.account_name,
                        "search_id": self.search_id,
                        "search_query": self.search_config["search_query"],
                        "item": item,
                    },
                )
