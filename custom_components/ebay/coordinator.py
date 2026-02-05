"""Data update coordinators for eBay integration."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.storage import Store

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

# Storage version for event state
STORAGE_VERSION = 1
# Keep state for 60 days
STATE_RETENTION_DAYS = 60


def _clean_old_items(data: dict[str, Any], max_age_days: int = STATE_RETENTION_DAYS) -> dict[str, Any]:
    """Remove items older than max_age_days from stored data.
    
    Args:
        data: Dictionary of items keyed by item_id
        max_age_days: Maximum age in days
        
    Returns:
        Cleaned dictionary with only recent items
    """
    if not data:
        return {}
    
    cutoff = datetime.now() - timedelta(days=max_age_days)
    cleaned = {}
    
    for item_id, item in data.items():
        # Try to get end_time or updated_at to determine age
        time_str = item.get("end_time") or item.get("updated_at")
        if not time_str:
            # No timestamp, keep it (might be recent)
            cleaned[item_id] = item
            continue
        
        try:
            item_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            if item_time.replace(tzinfo=None) > cutoff:
                cleaned[item_id] = item
        except (ValueError, AttributeError):
            # Can't parse, keep it
            cleaned[item_id] = item
    
    if len(cleaned) < len(data):
        _LOGGER.debug("Cleaned %d old items from storage", len(data) - len(cleaned))
    
    return cleaned


def _sort_by_end_time(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort items by end_time, soonest first.
    
    Args:
        items: List of items with end_time field
        
    Returns:
        Sorted list with items ending soonest at the top
    """
    def get_end_time(item: dict[str, Any]) -> datetime:
        """Extract end_time as datetime for sorting."""
        end_time_str = item.get("end_time", "")
        if not end_time_str:
            # No end time, sort to end
            return datetime.max.replace(tzinfo=None)
        
        try:
            return datetime.fromisoformat(end_time_str.replace("Z", "+00:00")).replace(tzinfo=None)
        except (ValueError, AttributeError):
            # Can't parse, sort to end
            return datetime.max.replace(tzinfo=None)
    
    return sorted(items, key=get_end_time)


def _sort_by_purchase_date(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort purchases by date, newest first.
    
    Args:
        items: List of purchase items
        
    Returns:
        Sorted list with newest purchases at the top
    """
    def get_purchase_time(item: dict[str, Any]) -> datetime:
        """Extract purchase/end time as datetime for sorting."""
        # Try various time fields that might indicate purchase time
        time_str = item.get("purchase_date") or item.get("end_time") or item.get("updated_at", "")
        if not time_str:
            # No time, sort to end
            return datetime.min.replace(tzinfo=None)
        
        try:
            return datetime.fromisoformat(time_str.replace("Z", "+00:00")).replace(tzinfo=None)
        except (ValueError, AttributeError):
            # Can't parse, sort to end
            return datetime.min.replace(tzinfo=None)
    
    # Sort in reverse (newest first)
    return sorted(items, key=get_purchase_time, reverse=True)


class EbayBidsCoordinator(DataUpdateCoordinator):
    """Coordinator for eBay bids."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: EbayAPI,
        account_name: str,
        update_interval: timedelta,
        config_entry=None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_bids_{account_name}",
            update_interval=update_interval,
            config_entry=config_entry,
        )
        self.api = api
        self.account_name = account_name
        self._previous_data: dict[str, Any] = {}
        
        # Storage for persisting state across restarts
        self._store = Store(
            hass,
            STORAGE_VERSION,
            f"ebay_bids_state_{account_name.lower().replace(' ', '_')}",
        )
        self._state_loaded = False

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch bid data."""
        # Load previous state from storage on first run
        if not self._state_loaded:
            try:
                stored_data = await self._store.async_load()
                if stored_data:
                    self._previous_data = _clean_old_items(stored_data.get("previous_data", {}))
                    _LOGGER.info(
                        "EbayBidsCoordinator: Loaded %d items from storage for account '%s'",
                        len(self._previous_data),
                        self.account_name
                    )
            except Exception as err:
                _LOGGER.warning("EbayBidsCoordinator: Could not load state: %s", err)
            self._state_loaded = True
        
        _LOGGER.debug("EbayBidsCoordinator: Starting update for account '%s'", self.account_name)
        
        try:
            data = await self.api.get_my_ebay_buying()
            bids = data.get("bids", [])

            _LOGGER.debug("EbayBidsCoordinator: Retrieved %d bids for account '%s'", len(bids), self.account_name)
            
            # Fire events for changes
            self._check_bid_changes(bids)

            # Update previous data
            self._previous_data = {item["item_id"]: item for item in bids}
            
            # Save state to storage
            try:
                await self._store.async_save({
                    "previous_data": self._previous_data,
                    "updated_at": datetime.now().isoformat(),
                })
            except Exception as err:
                _LOGGER.warning("EbayBidsCoordinator: Could not save state: %s", err)

            # Sort by end_time (ending soonest first)
            bids = _sort_by_end_time(bids)

            return bids

        except Exception as err:
            _LOGGER.error("EbayBidsCoordinator: Error fetching bids for account '%s': %s", self.account_name, err)
            raise UpdateFailed(f"Error fetching bids: {err}") from err

    def _check_bid_changes(self, current_bids: list[dict[str, Any]]) -> None:
        """Check for changes in bid status and fire events."""
        current_ids = {item["item_id"] for item in current_bids}
        previous_ids = set(self._previous_data.keys())

        _LOGGER.debug(
            "EbayBidsCoordinator: Checking bid changes - Current: %d, Previous: %d",
            len(current_ids),
            len(previous_ids)
        )

        for bid in current_bids:
            item_id = bid["item_id"]
            previous = self._previous_data.get(item_id)

            if not previous:
                _LOGGER.debug("EbayBidsCoordinator: New bid detected - %s", item_id)
                # New bid - check if auction is ending soon
                self._check_ending_soon(bid)
                continue

            # Check if became high bidder
            current_high = bid.get("is_high_bidder", False)
            previous_high = previous.get("is_high_bidder", False)
            
            if current_high and not previous_high:
                _LOGGER.info(
                    "EbayBidsCoordinator: BECAME HIGH BIDDER - %s (%s)",
                    bid.get("title", "Unknown"),
                    item_id
                )
                self.hass.bus.async_fire(
                    EVENT_BECAME_HIGH_BIDDER,
                    {
                        "account": self.account_name,
                        "item": bid,
                    },
                )

            # Check if outbid
            elif not current_high and previous_high:
                _LOGGER.warning(
                    "EbayBidsCoordinator: OUTBID - %s (%s)",
                    bid.get("title", "Unknown"),
                    item_id
                )
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
        ended_ids = previous_ids - current_ids
        if ended_ids:
            _LOGGER.info(
                "EbayBidsCoordinator: %d auction(s) ended - %s",
                len(ended_ids),
                ended_ids
            )
            
        for item_id in ended_ids:
            previous = self._previous_data[item_id]
            # Auction ended - check if won or lost
            if previous.get("is_high_bidder"):
                _LOGGER.info(
                    "EbayBidsCoordinator: AUCTION WON - %s (%s)",
                    previous.get("title", "Unknown"),
                    item_id
                )
                self.hass.bus.async_fire(
                    EVENT_AUCTION_WON,
                    {
                        "account": self.account_name,
                        "item": previous,
                    },
                )
            else:
                _LOGGER.info(
                    "EbayBidsCoordinator: AUCTION LOST - %s (%s)",
                    previous.get("title", "Unknown"),
                    item_id
                )
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
                    _LOGGER.warning(
                        "EbayBidsCoordinator: AUCTION ENDING SOON - %s (%s) - %.1f minutes remaining",
                        bid.get("title", "Unknown"),
                        bid["item_id"],
                        minutes_remaining
                    )
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
        config_entry=None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_watchlist_{account_name}",
            update_interval=update_interval,
            config_entry=config_entry,
        )
        self.api = api
        self.account_name = account_name

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch watchlist data."""
        _LOGGER.debug("EbayWatchlistCoordinator: Starting update for account '%s'", self.account_name)
        
        try:
            data = await self.api.get_my_ebay_buying()
            watchlist = data.get("watchlist", [])
            
            _LOGGER.debug("EbayWatchlistCoordinator: Retrieved %d items for account '%s'", len(watchlist), self.account_name)
            
            # Sort by end_time (ending soonest first)
            watchlist = _sort_by_end_time(watchlist)
            
            return watchlist

        except Exception as err:
            _LOGGER.error("EbayWatchlistCoordinator: Error fetching watchlist for account '%s': %s", self.account_name, err)
            raise UpdateFailed(f"Error fetching watchlist: {err}") from err


class EbayPurchasesCoordinator(DataUpdateCoordinator):
    """Coordinator for eBay purchases."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: EbayAPI,
        account_name: str,
        update_interval: timedelta,
        config_entry=None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_purchases_{account_name}",
            update_interval=update_interval,
            config_entry=config_entry,
        )
        self.api = api
        self.account_name = account_name
        self._previous_data: dict[str, Any] = {}
        
        # Storage for persisting state across restarts
        self._store = Store(
            hass,
            STORAGE_VERSION,
            f"ebay_purchases_state_{account_name.lower().replace(' ', '_')}",
        )
        self._state_loaded = False

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch purchases data."""
        # Load previous state from storage on first run
        if not self._state_loaded:
            try:
                stored_data = await self._store.async_load()
                if stored_data:
                    self._previous_data = _clean_old_items(stored_data.get("previous_data", {}))
                    _LOGGER.info(
                        "EbayPurchasesCoordinator: Loaded %d items from storage for account '%s'",
                        len(self._previous_data),
                        self.account_name
                    )
            except Exception as err:
                _LOGGER.warning("EbayPurchasesCoordinator: Could not load state: %s", err)
            self._state_loaded = True
        
        _LOGGER.debug("EbayPurchasesCoordinator: Starting update for account '%s'", self.account_name)
        
        try:
            data = await self.api.get_my_ebay_buying()
            purchases = data.get("purchases", [])

            _LOGGER.debug("EbayPurchasesCoordinator: Retrieved %d purchases for account '%s'", len(purchases), self.account_name)
            
            # Fire events for shipping changes
            self._check_shipping_changes(purchases)

            # Update previous data
            self._previous_data = {item["item_id"]: item for item in purchases}
            
            # Save state to storage
            try:
                await self._store.async_save({
                    "previous_data": self._previous_data,
                    "updated_at": datetime.now().isoformat(),
                })
            except Exception as err:
                _LOGGER.warning("EbayPurchasesCoordinator: Could not save state: %s", err)

            # Sort by purchase date (newest first)
            purchases = _sort_by_purchase_date(purchases)

            return purchases

        except Exception as err:
            _LOGGER.error("EbayPurchasesCoordinator: Error fetching purchases for account '%s': %s", self.account_name, err)
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
        config_entry=None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_search_{account_name}_{search_id}",
            update_interval=update_interval,
            config_entry=config_entry,
        )
        self.api = api
        self.account_name = account_name
        self.search_id = search_id
        self.search_config = search_config
        self._previous_item_ids: set[str] = set()
        
        # Storage for persisting state across restarts
        self._store = Store(
            hass,
            STORAGE_VERSION,
            f"ebay_search_state_{search_id}",
        )
        self._state_loaded = False

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch search results."""
        # Load previous state from storage on first run
        if not self._state_loaded:
            try:
                stored_data = await self._store.async_load()
                if stored_data:
                    self._previous_item_ids = set(stored_data.get("previous_item_ids", []))
                    _LOGGER.info(
                        "EbaySearchCoordinator: Loaded %d item IDs from storage for search '%s'",
                        len(self._previous_item_ids),
                        self.search_id
                    )
            except Exception as err:
                _LOGGER.warning("EbaySearchCoordinator: Could not load state: %s", err)
            self._state_loaded = True
        
        _LOGGER.debug(
            "EbaySearchCoordinator: Starting search update - Account: '%s', Search ID: '%s', Query: '%s'",
            self.account_name,
            self.search_id,
            self.search_config["search_query"]
        )
        
        try:
            results = await self.api.search_items(
                query=self.search_config["search_query"],
                site_id=self.search_config.get("site"),
                category_id=self.search_config.get("category_id"),
                min_price=self.search_config.get("min_price"),
                max_price=self.search_config.get("max_price"),
                listing_type=self.search_config.get("listing_type"),
            )

            _LOGGER.debug(
                "EbaySearchCoordinator: Search completed - Account: '%s', Search ID: '%s', Results: %d items",
                self.account_name,
                self.search_id,
                len(results)
            )
            
            # Fire events for new items
            self._check_new_items(results)

            # Update previous item IDs
            self._previous_item_ids = {item["item_id"] for item in results}
            
            # Save state to storage
            try:
                await self._store.async_save({
                    "previous_item_ids": list(self._previous_item_ids),
                    "updated_at": datetime.now().isoformat(),
                })
            except Exception as err:
                _LOGGER.warning("EbaySearchCoordinator: Could not save state: %s", err)

            # Sort by end_time (ending soonest first)
            results = _sort_by_end_time(results)

            return results

        except Exception as err:
            _LOGGER.error(
                "EbaySearchCoordinator: Error fetching search results - Account: '%s', Search ID: '%s', Query: '%s', Error: %s",
                self.account_name,
                self.search_id,
                self.search_config["search_query"],
                err
            )
            raise UpdateFailed(f"Error fetching search results: {err}") from err

    def _check_new_items(self, current_results: list[dict[str, Any]]) -> None:
        """Check for new items in search results and fire events."""
        current_ids = {item["item_id"] for item in current_results}
        new_ids = current_ids - self._previous_item_ids

        _LOGGER.debug(
            "EbaySearchCoordinator: Checking for new items - Current: %d, Previous: %d, New: %d",
            len(current_ids),
            len(self._previous_item_ids),
            len(new_ids)
        )

        if new_ids:
            # On first run (Previous: 0), limit to 5 events to avoid spam
            is_first_run = len(self._previous_item_ids) == 0
            max_events = 5 if is_first_run else len(new_ids)
            
            _LOGGER.info(
                "EbaySearchCoordinator: Found %d NEW item(s) in search '%s'%s - %s",
                len(new_ids),
                self.search_config["search_query"],
                f" (limiting to {max_events} events on first run)" if is_first_run else "",
                list(new_ids)[:max_events] if is_first_run else new_ids
            )

        event_count = 0
        for item in current_results:
            if item["item_id"] in new_ids:
                # On first run, only fire events for first 5 items
                if len(self._previous_item_ids) == 0 and event_count >= 5:
                    continue
                
                event_count += 1
                _LOGGER.info(
                    "EbaySearchCoordinator: NEW SEARCH RESULT - %s (%s) in search '%s'",
                    item.get("title", "Unknown"),
                    item["item_id"],
                    self.search_config["search_query"]
                )
                self.hass.bus.async_fire(
                    EVENT_NEW_SEARCH_RESULT,
                    {
                        "account": self.account_name,
                        "search_id": self.search_id,
                        "search_query": self.search_config["search_query"],
                        "item": item,
                    },
                )
