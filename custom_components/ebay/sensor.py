"""Sensor platform for eBay integration."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_ITEMS,
    ATTR_ITEM_COUNT,
    ATTR_LAST_UPDATED,
    ATTR_LISTING_TYPE,
    CONF_ACCOUNT_NAME,
    CONF_SEARCH_QUERY,
    CONF_SITE,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
)
from .coordinator import (
    EbayBidsCoordinator,
    EbayPurchasesCoordinator,
    EbaySearchCoordinator,
    EbayWatchlistCoordinator,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up eBay sensors from a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    account_name = entry_data["account_name"]

    entities: list[SensorEntity] = []

    # Add API usage sensor (one per account)
    entities.append(
        EbayAPIUsageSensor(
            api=entry_data["api"],
            account_name=account_name,
        )
    )

    # Add base sensors (bids, watchlist, purchases)
    entities.append(
        EbayBidsSensor(
            coordinator=entry_data["bids_coordinator"],
            account_name=account_name,
        )
    )
    entities.append(
        EbayWatchlistSensor(
            coordinator=entry_data["watchlist_coordinator"],
            account_name=account_name,
        )
    )
    entities.append(
        EbayPurchasesSensor(
            coordinator=entry_data["purchases_coordinator"],
            account_name=account_name,
        )
    )

    # Add search sensors
    for search_id, search_data in entry_data["searches"].items():
        entities.append(
            EbaySearchSensor(
                coordinator=search_data["coordinator"],
                account_name=account_name,
                search_id=search_id,
                search_query=search_data["config"][CONF_SEARCH_QUERY],
            )
        )

    async_add_entities(entities)


class EbayBidsSensor(CoordinatorEntity, SensorEntity):
    """Sensor for eBay active bids."""

    _attr_icon = "mdi:gavel"

    def __init__(
        self,
        coordinator: EbayBidsCoordinator,
        account_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._account_name = account_name
        self._attr_name = f"eBay {account_name} Active Bids"
        self._attr_unique_id = f"ebay_{account_name}_bids"

    @property
    def native_value(self) -> int:
        """Return the number of active bids."""
        return len(self.coordinator.data) if self.coordinator.data else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return {}

        return {
            ATTR_ITEM_COUNT: len(self.coordinator.data),
            ATTR_ITEMS: self.coordinator.data,
            ATTR_LAST_UPDATED: dt_util.now().isoformat(),
        }


class EbayWatchlistSensor(CoordinatorEntity, SensorEntity):
    """Sensor for eBay watchlist."""

    _attr_icon = "mdi:eye"

    def __init__(
        self,
        coordinator: EbayWatchlistCoordinator,
        account_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._account_name = account_name
        self._attr_name = f"eBay {account_name} Watchlist"
        self._attr_unique_id = f"ebay_{account_name}_watchlist"

    @property
    def native_value(self) -> int:
        """Return the number of watched items."""
        return len(self.coordinator.data) if self.coordinator.data else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return {}

        return {
            ATTR_ITEM_COUNT: len(self.coordinator.data),
            ATTR_ITEMS: self.coordinator.data,
            ATTR_LAST_UPDATED: dt_util.now().isoformat(),
        }


class EbayPurchasesSensor(CoordinatorEntity, SensorEntity):
    """Sensor for eBay purchases."""

    _attr_icon = "mdi:shopping"

    def __init__(
        self,
        coordinator: EbayPurchasesCoordinator,
        account_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._account_name = account_name
        self._attr_name = f"eBay {account_name} Purchases"
        self._attr_unique_id = f"ebay_{account_name}_purchases"

    @property
    def native_value(self) -> int:
        """Return the number of purchases."""
        return len(self.coordinator.data) if self.coordinator.data else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return {}

        return {
            ATTR_ITEM_COUNT: len(self.coordinator.data),
            ATTR_ITEMS: self.coordinator.data,
            ATTR_LAST_UPDATED: dt_util.now().isoformat(),
        }


class EbaySearchSensor(CoordinatorEntity, SensorEntity):
    """Sensor for eBay search results."""

    _attr_icon = "mdi:magnify"

    def __init__(
        self,
        coordinator: EbaySearchCoordinator,
        account_name: str,
        search_id: str,
        search_query: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._account_name = account_name
        self._search_id = search_id
        self._search_query = search_query
        self._attr_name = f"eBay {account_name} Search {search_query}"
        self._attr_unique_id = f"ebay_{account_name}_search_{search_id}"

    @property
    def native_value(self) -> int:
        """Return the number of search results."""
        return len(self.coordinator.data) if self.coordinator.data else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        items = self.coordinator.data if self.coordinator.data else []
        
        # Count auction vs buy it now
        auction_count = 0
        buy_now_count = 0
        for item in items:
            listing_type = item.get(ATTR_LISTING_TYPE, "")
            if listing_type == "Auction":
                auction_count += 1
            elif listing_type in ["FixedPrice", "Buy It Now"]:
                buy_now_count += 1
        
        # Get config values
        config = self.coordinator.search_config
        site = config.get(CONF_SITE, "uk")
        update_interval = config.get(CONF_UPDATE_INTERVAL, 15)
        
        # Limit items to prevent database size issues (16KB limit)
        # Only store first 10 items in attributes to stay under limit
        limited_items = items[:10] if len(items) > 10 else items
        
        return {
            "search_query": self._search_query,
            "search_id": self._search_id,
            "site": site,
            "update_interval": update_interval,
            ATTR_ITEM_COUNT: len(items),
            "auction_count": auction_count,
            "buy_now_count": buy_now_count,
            ATTR_ITEMS: limited_items,
            "total_results": len(items),
            ATTR_LAST_UPDATED: dt_util.now().isoformat(),
        }


class EbayAPIUsageSensor(SensorEntity):
    """Sensor showing API rate limit usage from eBay Analytics API."""

    _attr_icon = "mdi:api"

    def __init__(self, api, account_name: str) -> None:
        """Initialize the API usage sensor."""
        self._api = api
        self._account_name = account_name
        self._attr_name = f"eBay {account_name} API Usage"
        self._attr_unique_id = f"ebay_{account_name.lower().replace(' ', '_')}_api_usage"
        self._usage_data = None

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if not self._usage_data:
            return "Unknown"
        
        # Show Browse API usage percentage if available
        analytics = self._usage_data.get("ebay_analytics", {})
        if analytics and "browse" in analytics:
            return f"{analytics['browse']['usage_percent']}%"
        
        # Fallback to local tracking
        local = self._usage_data.get("local_tracking", {})
        if "browse" in local:
            return f"{local['browse']['count']} calls"
        
        return "No data"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not self._usage_data:
            return {}
        
        attrs = {}
        
        # eBay Analytics (actual usage from eBay)
        analytics = self._usage_data.get("ebay_analytics")
        if analytics:
            attrs["ebay_analytics"] = analytics
            
            # Add convenient top-level attributes
            if "browse" in analytics:
                attrs["browse_limit"] = analytics["browse"]["limit"]
                attrs["browse_used"] = analytics["browse"]["used"]
                attrs["browse_remaining"] = analytics["browse"]["remaining"]
                attrs["browse_usage_percent"] = analytics["browse"]["usage_percent"]
                attrs["browse_reset"] = analytics["browse"]["reset"]
        
        # Local tracking (our counts)
        local = self._usage_data.get("local_tracking")
        if local:
            attrs["local_tracking"] = local
        
        # Error if any
        if self._usage_data.get("error"):
            attrs["error"] = self._usage_data["error"]
        
        attrs[ATTR_LAST_UPDATED] = dt_util.now().isoformat()
        
        return attrs

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        self._usage_data = await self._api.get_rate_limit_usage()
