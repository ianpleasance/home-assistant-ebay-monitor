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
    CONF_CATEGORY_ID,
    CONF_LISTING_TYPE,
    CONF_MAX_PRICE,
    CONF_MIN_PRICE,
    CONF_SEARCH_QUERY,
    CONF_SITE,
    CONF_UPDATE_INTERVAL,
    DEFAULT_SITE,
    DOMAIN,
)
from .coordinator import (
    EbayBidsCoordinator,
    EbayPurchasesCoordinator,
    EbaySearchCoordinator,
    EbayWatchlistCoordinator,
)

_LOGGER = logging.getLogger(__name__)

# Chunk configuration
CHUNK_SIZE = 20  # Items per chunk sensor


def _create_chunks(items: list[dict[str, Any]], chunk_size: int = CHUNK_SIZE) -> list[list[dict[str, Any]]]:
    """Split items into chunks of specified size.
    
    Args:
        items: List of items to chunk
        chunk_size: Number of items per chunk
        
    Returns:
        List of chunks, each containing up to chunk_size items
    """
    if not items:
        return []
    
    chunks = []
    for i in range(0, len(items), chunk_size):
        chunks.append(items[i:i + chunk_size])
    
    return chunks


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

    # Add main sensors (count only, no items)
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

    # Add main search sensors
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
    
    # Now create chunk sensors based on current data
    # We need to do this after coordinators have fetched data
    
    # Helper to create chunk sensors for a coordinator
    async def create_chunks_for_coordinator(coordinator, sensor_type: str, extra_params: dict = None):
        """Create chunk sensors for a coordinator's current data."""
        await coordinator.async_refresh()  # Ensure we have data
        
        items = coordinator.data if coordinator.data else []
        if not items:
            return  # No chunks needed
        
        chunk_count = (len(items) + CHUNK_SIZE - 1) // CHUNK_SIZE
        chunk_entities = []
        
        for chunk_num in range(1, chunk_count + 1):
            if sensor_type == "bids":
                chunk_entities.append(
                    EbayBidsChunkSensor(
                        coordinator=coordinator,
                        account_name=account_name,
                        chunk_number=chunk_num,
                    )
                )
            elif sensor_type == "watchlist":
                chunk_entities.append(
                    EbayWatchlistChunkSensor(
                        coordinator=coordinator,
                        account_name=account_name,
                        chunk_number=chunk_num,
                    )
                )
            elif sensor_type == "purchases":
                chunk_entities.append(
                    EbayPurchasesChunkSensor(
                        coordinator=coordinator,
                        account_name=account_name,
                        chunk_number=chunk_num,
                    )
                )
            elif sensor_type == "search" and extra_params:
                chunk_entities.append(
                    EbaySearchChunkSensor(
                        coordinator=coordinator,
                        account_name=account_name,
                        search_id=extra_params["search_id"],
                        search_query=extra_params["search_query"],
                        chunk_number=chunk_num,
                    )
                )
        
        if chunk_entities:
            async_add_entities(chunk_entities)
            _LOGGER.info(
                "Created %d chunk sensors for %s %s",
                len(chunk_entities),
                account_name,
                sensor_type
            )
    
    # Create chunks for bids, watchlist, purchases
    await create_chunks_for_coordinator(entry_data["bids_coordinator"], "bids")
    await create_chunks_for_coordinator(entry_data["watchlist_coordinator"], "watchlist")
    await create_chunks_for_coordinator(entry_data["purchases_coordinator"], "purchases")
    
    # Create chunks for each search
    for search_id, search_data in entry_data["searches"].items():
        await create_chunks_for_coordinator(
            search_data["coordinator"],
            "search",
            {
                "search_id": search_id,
                "search_query": search_data["config"][CONF_SEARCH_QUERY],
            }
        )


class EbayBidsSensor(CoordinatorEntity, SensorEntity):
    """Sensor for eBay active bids (main sensor - count only)."""

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
        items = self.coordinator.data if self.coordinator.data else []
        item_count = len(items)
        chunk_count = (item_count + CHUNK_SIZE - 1) // CHUNK_SIZE  # Ceiling division
        
        # Generate list of chunk sensor entity IDs
        chunk_sensors = []
        for i in range(1, chunk_count + 1):
            chunk_sensors.append(f"sensor.ebay_{self._account_name.lower().replace(' ', '_')}_active_bids_chunk_{i}")
        
        return {
            ATTR_ITEM_COUNT: item_count,
            "chunk_count": chunk_count,
            "chunk_sensors": chunk_sensors,
            ATTR_LAST_UPDATED: dt_util.now().isoformat(),
        }


class EbayBidsChunkSensor(CoordinatorEntity, SensorEntity):
    """Chunk sensor for eBay active bids (holds up to 20 items)."""

    _attr_icon = "mdi:gavel"

    def __init__(
        self,
        coordinator: EbayBidsCoordinator,
        account_name: str,
        chunk_number: int,
    ) -> None:
        """Initialize the chunk sensor."""
        super().__init__(coordinator)
        self._account_name = account_name
        self._chunk_number = chunk_number
        self._attr_name = f"eBay {account_name} Active Bids Chunk {chunk_number}"
        self._attr_unique_id = f"ebay_{account_name}_active_bids_chunk_{chunk_number}"

    @property
    def native_value(self) -> int:
        """Return the number of items in this chunk."""
        items = self._get_chunk_items()
        return len(items)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return chunk items and metadata."""
        items = self._get_chunk_items()
        
        # Calculate chunk range
        start_idx = (self._chunk_number - 1) * CHUNK_SIZE
        end_idx = start_idx + len(items) - 1
        
        return {
            "chunk_number": self._chunk_number,
            "chunk_start": start_idx + 1,  # 1-indexed for display
            "chunk_end": end_idx + 1,  # 1-indexed for display
            ATTR_ITEMS: items,
            "parent_sensor": f"sensor.ebay_{self._account_name.lower().replace(' ', '_')}_active_bids",
            ATTR_LAST_UPDATED: dt_util.now().isoformat(),
        }
    
    def _get_chunk_items(self) -> list[dict[str, Any]]:
        """Get the items for this chunk."""
        if not self.coordinator.data:
            return []
        
        start_idx = (self._chunk_number - 1) * CHUNK_SIZE
        end_idx = start_idx + CHUNK_SIZE
        
        return self.coordinator.data[start_idx:end_idx]


class EbayWatchlistSensor(CoordinatorEntity, SensorEntity):
    """Sensor for eBay watchlist (main sensor - count only)."""

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
        items = self.coordinator.data if self.coordinator.data else []
        item_count = len(items)
        chunk_count = (item_count + CHUNK_SIZE - 1) // CHUNK_SIZE
        
        chunk_sensors = []
        for i in range(1, chunk_count + 1):
            chunk_sensors.append(f"sensor.ebay_{self._account_name.lower().replace(' ', '_')}_watchlist_chunk_{i}")
        
        return {
            ATTR_ITEM_COUNT: item_count,
            "chunk_count": chunk_count,
            "chunk_sensors": chunk_sensors,
            ATTR_LAST_UPDATED: dt_util.now().isoformat(),
        }


class EbayWatchlistChunkSensor(CoordinatorEntity, SensorEntity):
    """Chunk sensor for eBay watchlist (holds up to 20 items)."""

    _attr_icon = "mdi:eye"

    def __init__(
        self,
        coordinator: EbayWatchlistCoordinator,
        account_name: str,
        chunk_number: int,
    ) -> None:
        """Initialize the chunk sensor."""
        super().__init__(coordinator)
        self._account_name = account_name
        self._chunk_number = chunk_number
        self._attr_name = f"eBay {account_name} Watchlist Chunk {chunk_number}"
        self._attr_unique_id = f"ebay_{account_name}_watchlist_chunk_{chunk_number}"

    @property
    def native_value(self) -> int:
        """Return the number of items in this chunk."""
        items = self._get_chunk_items()
        return len(items)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return chunk items and metadata."""
        items = self._get_chunk_items()
        
        start_idx = (self._chunk_number - 1) * CHUNK_SIZE
        end_idx = start_idx + len(items) - 1
        
        return {
            "chunk_number": self._chunk_number,
            "chunk_start": start_idx + 1,
            "chunk_end": end_idx + 1,
            ATTR_ITEMS: items,
            "parent_sensor": f"sensor.ebay_{self._account_name.lower().replace(' ', '_')}_watchlist",
            ATTR_LAST_UPDATED: dt_util.now().isoformat(),
        }
    
    def _get_chunk_items(self) -> list[dict[str, Any]]:
        """Get the items for this chunk."""
        if not self.coordinator.data:
            return []
        
        start_idx = (self._chunk_number - 1) * CHUNK_SIZE
        end_idx = start_idx + CHUNK_SIZE
        
        return self.coordinator.data[start_idx:end_idx]


class EbayPurchasesSensor(CoordinatorEntity, SensorEntity):
    """Sensor for eBay purchases (main sensor - count only)."""

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
        items = self.coordinator.data if self.coordinator.data else []
        item_count = len(items)
        chunk_count = (item_count + CHUNK_SIZE - 1) // CHUNK_SIZE
        
        chunk_sensors = []
        for i in range(1, chunk_count + 1):
            chunk_sensors.append(f"sensor.ebay_{self._account_name.lower().replace(' ', '_')}_purchases_chunk_{i}")
        
        return {
            ATTR_ITEM_COUNT: item_count,
            "chunk_count": chunk_count,
            "chunk_sensors": chunk_sensors,
            ATTR_LAST_UPDATED: dt_util.now().isoformat(),
        }


class EbayPurchasesChunkSensor(CoordinatorEntity, SensorEntity):
    """Chunk sensor for eBay purchases (holds up to 20 items)."""

    _attr_icon = "mdi:shopping"

    def __init__(
        self,
        coordinator: EbayPurchasesCoordinator,
        account_name: str,
        chunk_number: int,
    ) -> None:
        """Initialize the chunk sensor."""
        super().__init__(coordinator)
        self._account_name = account_name
        self._chunk_number = chunk_number
        self._attr_name = f"eBay {account_name} Purchases Chunk {chunk_number}"
        self._attr_unique_id = f"ebay_{account_name}_purchases_chunk_{chunk_number}"

    @property
    def native_value(self) -> int:
        """Return the number of items in this chunk."""
        items = self._get_chunk_items()
        return len(items)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return chunk items and metadata."""
        items = self._get_chunk_items()
        
        start_idx = (self._chunk_number - 1) * CHUNK_SIZE
        end_idx = start_idx + len(items) - 1
        
        return {
            "chunk_number": self._chunk_number,
            "chunk_start": start_idx + 1,
            "chunk_end": end_idx + 1,
            ATTR_ITEMS: items,
            "parent_sensor": f"sensor.ebay_{self._account_name.lower().replace(' ', '_')}_purchases",
            ATTR_LAST_UPDATED: dt_util.now().isoformat(),
        }
    
    def _get_chunk_items(self) -> list[dict[str, Any]]:
        """Get the items for this chunk."""
        if not self.coordinator.data:
            return []
        
        start_idx = (self._chunk_number - 1) * CHUNK_SIZE
        end_idx = start_idx + CHUNK_SIZE
        
        return self.coordinator.data[start_idx:end_idx]


class EbaySearchSensor(CoordinatorEntity, SensorEntity):
    """Sensor for eBay search results (main sensor - count only)."""

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
        self._attr_name = f"eBay {account_name} Search {search_id}"
        self._attr_unique_id = f"ebay_{account_name}_search_{search_id}"

    @property
    def native_value(self) -> int:
        """Return the number of search results."""
        return len(self.coordinator.data) if self.coordinator.data else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        items = self.coordinator.data if self.coordinator.data else []
        item_count = len(items)
        
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
        
        # Calculate chunks
        chunk_count = (item_count + CHUNK_SIZE - 1) // CHUNK_SIZE
        
        # Generate chunk sensor IDs using full search_id for accuracy
        chunk_sensors = []
        for i in range(1, chunk_count + 1):
            chunk_sensors.append(
                f"sensor.ebay_{self._account_name.lower().replace(' ', '_')}_search_{self._search_id}_chunk_{i}"
            )
        
        return {
            "search_query": self._search_query,
            "search_id": self._search_id,
            "search_config": {
                CONF_SITE: config.get(CONF_SITE, DEFAULT_SITE),
                CONF_CATEGORY_ID: config.get(CONF_CATEGORY_ID),
                CONF_MIN_PRICE: config.get(CONF_MIN_PRICE),
                CONF_MAX_PRICE: config.get(CONF_MAX_PRICE),
                CONF_LISTING_TYPE: config.get(CONF_LISTING_TYPE),
            },
            "site": site,
            "update_interval": update_interval,
            ATTR_ITEM_COUNT: item_count,
            "auction_count": auction_count,
            "buy_now_count": buy_now_count,
            "chunk_count": chunk_count,
            "chunk_sensors": chunk_sensors,
            ATTR_LAST_UPDATED: dt_util.now().isoformat(),
        }


class EbaySearchChunkSensor(CoordinatorEntity, SensorEntity):
    """Chunk sensor for eBay search results (holds up to 20 items)."""

    _attr_icon = "mdi:magnify"

    def __init__(
        self,
        coordinator: EbaySearchCoordinator,
        account_name: str,
        search_id: str,
        search_query: str,
        chunk_number: int,
    ) -> None:
        """Initialize the chunk sensor."""
        super().__init__(coordinator)
        self._account_name = account_name
        self._search_id = search_id
        self._search_query = search_query
        self._chunk_number = chunk_number
        self._attr_name = f"eBay {account_name} Search {search_id} Chunk {chunk_number}"
        self._attr_unique_id = f"ebay_{account_name}_search_{search_id}_chunk_{chunk_number}"

    @property
    def native_value(self) -> int:
        """Return the number of items in this chunk."""
        items = self._get_chunk_items()
        return len(items)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return chunk items and metadata."""
        items = self._get_chunk_items()
        
        start_idx = (self._chunk_number - 1) * CHUNK_SIZE
        end_idx = start_idx + len(items) - 1
        
        return {
            "chunk_number": self._chunk_number,
            "chunk_start": start_idx + 1,
            "chunk_end": end_idx + 1,
            "search_query": self._search_query,
            "search_id": self._search_id,
            ATTR_ITEMS: items,
            "parent_sensor": f"sensor.ebay_{self._account_name.lower().replace(' ', '_')}_search_{self._search_id}",
            ATTR_LAST_UPDATED: dt_util.now().isoformat(),
        }
    
    def _get_chunk_items(self) -> list[dict[str, Any]]:
        """Get the items for this chunk."""
        if not self.coordinator.data:
            return []
        
        start_idx = (self._chunk_number - 1) * CHUNK_SIZE
        end_idx = start_idx + CHUNK_SIZE
        
        return self.coordinator.data[start_idx:end_idx]


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
