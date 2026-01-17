"""Sensor platform for eBay integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_ITEMS,
    ATTR_ITEM_COUNT,
    ATTR_LAST_UPDATED,
    CONF_ACCOUNT_NAME,
    CONF_SEARCH_QUERY,
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
            ATTR_LAST_UPDATED: self.coordinator.last_update_success_time.isoformat()
            if self.coordinator.last_update_success_time
            else None,
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
            ATTR_LAST_UPDATED: self.coordinator.last_update_success_time.isoformat()
            if self.coordinator.last_update_success_time
            else None,
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
            ATTR_LAST_UPDATED: self.coordinator.last_update_success_time.isoformat()
            if self.coordinator.last_update_success_time
            else None,
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
        if not self.coordinator.data:
            return {
                "search_query": self._search_query,
                "search_id": self._search_id,
            }

        return {
            "search_query": self._search_query,
            "search_id": self._search_id,
            ATTR_ITEM_COUNT: len(self.coordinator.data),
            ATTR_ITEMS: self.coordinator.data,
            ATTR_LAST_UPDATED: self.coordinator.last_update_success_time.isoformat()
            if self.coordinator.last_update_success_time
            else None,
        }
