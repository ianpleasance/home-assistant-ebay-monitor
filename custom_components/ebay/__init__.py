"""The eBay integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_ACCOUNT,
    ATTR_SEARCH_ID,
    CONF_ACCOUNT_NAME,
    CONF_CATEGORY_ID,
    CONF_LISTING_TYPE,
    CONF_MAX_PRICE,
    CONF_MIN_PRICE,
    CONF_SEARCH_QUERY,
    CONF_SITE,
    CONF_UPDATE_INTERVAL,
    DEFAULT_BIDS_INTERVAL,
    DEFAULT_PURCHASES_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_WATCHLIST_INTERVAL,
    DOMAIN,
    SERVICE_CREATE_SEARCH,
    SERVICE_DELETE_SEARCH,
    SERVICE_GET_RATE_LIMITS,
    SERVICE_REFRESH_ACCOUNT,
    SERVICE_REFRESH_ALL,
    SERVICE_REFRESH_API_USAGE,
    SERVICE_REFRESH_BIDS,
    SERVICE_REFRESH_PURCHASES,
    SERVICE_REFRESH_SEARCH,
    SERVICE_REFRESH_WATCHLIST,
    SERVICE_UPDATE_SEARCH,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .coordinator import (
    EbayBidsCoordinator,
    EbayPurchasesCoordinator,
    EbaySearchCoordinator,
    EbayWatchlistCoordinator,
)
from .ebay_api import EbayAPI

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the eBay component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up eBay from a config entry."""
    account_name = entry.data[CONF_ACCOUNT_NAME]
    
    # Initialize API client
    api = EbayAPI(
        hass=hass,
        app_id=entry.data["app_id"],
        dev_id=entry.data["dev_id"],
        cert_id=entry.data["cert_id"],
        token=entry.data["token"],
        site_id=entry.data.get("site_id", "EBAY-GB"),
    )
    
    # Create storage for searches
    store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry.entry_id}")
    searches_data = await store.async_load() or {}
    
    # Initialize coordinators
    bids_coordinator = EbayBidsCoordinator(
        hass=hass,
        api=api,
        account_name=account_name,
        update_interval=timedelta(minutes=DEFAULT_BIDS_INTERVAL),
        config_entry=entry,
    )
    
    watchlist_coordinator = EbayWatchlistCoordinator(
        hass=hass,
        api=api,
        account_name=account_name,
        update_interval=timedelta(minutes=DEFAULT_WATCHLIST_INTERVAL),
        config_entry=entry,
    )
    
    purchases_coordinator = EbayPurchasesCoordinator(
        hass=hass,
        api=api,
        account_name=account_name,
        update_interval=timedelta(minutes=DEFAULT_PURCHASES_INTERVAL),
        config_entry=entry,
    )
    
    # Store coordinators and data
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "store": store,
        "account_name": account_name,
        "bids_coordinator": bids_coordinator,
        "watchlist_coordinator": watchlist_coordinator,
        "purchases_coordinator": purchases_coordinator,
        "searches": {},
    }
    
    # Load saved searches and create coordinators
    for search_id, search_config in searches_data.items():
        await _create_search_coordinator(hass, entry, search_id, search_config, is_setup=True)
    
    # Initial coordinator refresh
    await bids_coordinator.async_config_entry_first_refresh()
    await watchlist_coordinator.async_config_entry_first_refresh()
    await purchases_coordinator.async_config_entry_first_refresh()
    
    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register services (only once, for first entry)
    if len(hass.data[DOMAIN]) == 1:
        await _async_register_services(hass)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok


async def _create_search_coordinator(
    hass: HomeAssistant,
    entry: ConfigEntry,
    search_id: str,
    search_config: dict,
    is_setup: bool = False,
) -> EbaySearchCoordinator:
    """Create a search coordinator."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    
    coordinator = EbaySearchCoordinator(
        hass=hass,
        api=entry_data["api"],
        account_name=entry_data["account_name"],
        search_id=search_id,
        search_config=search_config,
        update_interval=timedelta(
            minutes=search_config.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        ),
        config_entry=entry,
    )
    
    # Use async_config_entry_first_refresh only during initial setup
    # Otherwise use regular async_refresh
    if is_setup:
        await coordinator.async_config_entry_first_refresh()
    else:
        await coordinator.async_refresh()
    
    entry_data["searches"][search_id] = {
        "config": search_config,
        "coordinator": coordinator,
    }
    
    return coordinator


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register eBay services."""
    
    async def refresh_bids(call: ServiceCall) -> None:
        """Refresh bids for account(s)."""
        account = call.data.get(ATTR_ACCOUNT)
        
        for entry_id, data in hass.data[DOMAIN].items():
            if account and data["account_name"] != account:
                continue
            await data["bids_coordinator"].async_request_refresh()
    
    async def refresh_watchlist(call: ServiceCall) -> None:
        """Refresh watchlist for account(s)."""
        account = call.data.get(ATTR_ACCOUNT)
        
        for entry_id, data in hass.data[DOMAIN].items():
            if account and data["account_name"] != account:
                continue
            await data["watchlist_coordinator"].async_request_refresh()
    
    async def refresh_purchases(call: ServiceCall) -> None:
        """Refresh purchases for account(s)."""
        account = call.data.get(ATTR_ACCOUNT)
        
        for entry_id, data in hass.data[DOMAIN].items():
            if account and data["account_name"] != account:
                continue
            await data["purchases_coordinator"].async_request_refresh()
    
    async def refresh_search(call: ServiceCall) -> None:
        """Refresh a specific search."""
        search_id = call.data[ATTR_SEARCH_ID]
        
        for entry_id, data in hass.data[DOMAIN].items():
            if search_id in data["searches"]:
                await data["searches"][search_id]["coordinator"].async_request_refresh()
                return
    
    async def refresh_account(call: ServiceCall) -> None:
        """Refresh all data for an account."""
        account = call.data[ATTR_ACCOUNT]
        
        for entry_id, data in hass.data[DOMAIN].items():
            if data["account_name"] == account:
                tasks = [
                    data["bids_coordinator"].async_request_refresh(),
                    data["watchlist_coordinator"].async_request_refresh(),
                    data["purchases_coordinator"].async_request_refresh(),
                ]
                
                for search_data in data["searches"].values():
                    tasks.append(search_data["coordinator"].async_request_refresh())
                
                await asyncio.gather(*tasks)
                return
    
    async def refresh_all(call: ServiceCall) -> None:
        """Refresh all data for all accounts."""
        tasks = []
        
        for entry_id, data in hass.data[DOMAIN].items():
            tasks.extend([
                data["bids_coordinator"].async_request_refresh(),
                data["watchlist_coordinator"].async_request_refresh(),
                data["purchases_coordinator"].async_request_refresh(),
            ])
            
            for search_data in data["searches"].values():
                tasks.append(search_data["coordinator"].async_request_refresh())
        
        await asyncio.gather(*tasks)
    
    async def refresh_api_usage(call: ServiceCall) -> None:
        """Refresh API usage sensor(s)."""
        account = call.data.get(ATTR_ACCOUNT)
        
        # Get entity registry to find API usage sensors
        entity_reg = er.async_get(hass)
        
        for entry_id, data in hass.data[DOMAIN].items():
            # Skip if specific account requested and this isn't it
            if account and data["account_name"] != account:
                continue
            
            # Find the API usage sensor for this account
            account_name = data["account_name"]
            sensor_id = f"sensor.ebay_{account_name.lower().replace(' ', '_')}_api_usage"
            
            entity = entity_reg.async_get(sensor_id)
            if entity:
                # Trigger update
                await hass.services.async_call(
                    "homeassistant",
                    "update_entity",
                    {"entity_id": sensor_id},
                    blocking=True
                )
                _LOGGER.info("Refreshed API usage for account: %s", account_name)
    
    async def create_search(call: ServiceCall) -> None:
        """Create a new search."""
        account = call.data[ATTR_ACCOUNT]
        
        # Find the entry for this account
        for entry_id, data in hass.data[DOMAIN].items():
            if data["account_name"] == account:
                import uuid
                from homeassistant.helpers.entity_platform import async_get_platforms
                
                search_id = str(uuid.uuid4())
                
                search_config = {
                    CONF_SEARCH_QUERY: call.data[CONF_SEARCH_QUERY],
                    CONF_SITE: call.data[CONF_SITE],
                    CONF_CATEGORY_ID: call.data.get(CONF_CATEGORY_ID),
                    CONF_MIN_PRICE: call.data.get(CONF_MIN_PRICE),
                    CONF_MAX_PRICE: call.data.get(CONF_MAX_PRICE),
                    CONF_LISTING_TYPE: call.data.get(CONF_LISTING_TYPE, "both"),
                    CONF_UPDATE_INTERVAL: call.data.get(
                        CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                    ),
                }
                
                # Create coordinator
                await _create_search_coordinator(
                    hass, 
                    hass.config_entries.async_get_entry(entry_id),
                    search_id,
                    search_config
                )
                
                # Save to storage
                searches = await data["store"].async_load() or {}
                searches[search_id] = search_config
                await data["store"].async_save(searches)
                
                # Create the entity dynamically
                # Find the sensor platform for this entry
                platforms = async_get_platforms(hass, DOMAIN)
                for platform in platforms:
                    if platform.config_entry.entry_id == entry_id and platform.domain == "sensor":
                        # Import here to avoid circular dependency
                        from .sensor import EbaySearchSensor
                        
                        # Create the new sensor
                        new_sensor = EbaySearchSensor(
                            coordinator=data["searches"][search_id]["coordinator"],
                            account_name=data["account_name"],
                            search_id=search_id,
                            search_query=search_config[CONF_SEARCH_QUERY],
                        )
                        
                        # Add it to the platform
                        await platform.async_add_entities([new_sensor])
                        _LOGGER.info(f"Created search {search_id} and entity for account {account}")
                        return
                
                _LOGGER.info(f"Created search {search_id} for account {account}")
                return
    
    async def update_search(call: ServiceCall) -> None:
        """Update an existing search."""
        search_id = call.data[ATTR_SEARCH_ID]
        
        # Find the entry containing this search
        for entry_id, data in hass.data[DOMAIN].items():
            if search_id in data["searches"]:
                search_data = data["searches"][search_id]
                search_config = search_data["config"]
                coordinator = search_data["coordinator"]
                
                # Track if we need to update the interval
                interval_changed = False
                
                # Update config with new values
                for key in [
                    CONF_SEARCH_QUERY,
                    CONF_SITE,
                    CONF_CATEGORY_ID,
                    CONF_MIN_PRICE,
                    CONF_MAX_PRICE,
                    CONF_LISTING_TYPE,
                ]:
                    if key in call.data:
                        search_config[key] = call.data[key]
                
                # Handle update_interval separately
                if CONF_UPDATE_INTERVAL in call.data:
                    new_interval = call.data[CONF_UPDATE_INTERVAL]
                    if search_config.get(CONF_UPDATE_INTERVAL) != new_interval:
                        search_config[CONF_UPDATE_INTERVAL] = new_interval
                        interval_changed = True
                        # Update the coordinator's update_interval
                        coordinator.update_interval = timedelta(minutes=new_interval)
                        _LOGGER.info(f"Updated search {search_id} interval to {new_interval} minutes")
                
                # Update the coordinator's search_config so next refresh uses new params
                coordinator.search_config = search_config
                
                # Force a refresh with the new configuration
                await coordinator.async_refresh()
                
                # Save to storage
                searches = await data["store"].async_load() or {}
                searches[search_id] = search_config
                await data["store"].async_save(searches)
                
                _LOGGER.info(f"Updated search {search_id}")
                return
    
    async def delete_search(call: ServiceCall) -> None:
        """Delete a search."""
        search_id = call.data[ATTR_SEARCH_ID]
        
        # Find and remove the search
        for entry_id, data in hass.data[DOMAIN].items():
            if search_id in data["searches"]:
                # Build unique_id to find the entity
                account_name = data["account_name"]
                unique_id = f"ebay_{account_name}_search_{search_id}"
                
                # Remove from entity registry using unique_id
                entity_registry = er.async_get(hass)
                entity_id = entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)
                
                if entity_id:
                    entity_registry.async_remove(entity_id)
                    _LOGGER.info(f"Removed entity {entity_id} (unique_id: {unique_id})")
                else:
                    _LOGGER.warning(f"Entity with unique_id {unique_id} not found in registry")
                
                # Remove from runtime data
                data["searches"].pop(search_id)
                
                # Save to storage
                searches = await data["store"].async_load() or {}
                searches.pop(search_id, None)
                await data["store"].async_save(searches)
                
                _LOGGER.info(f"Deleted search {search_id}")
                return
    
    async def get_rate_limits(call: ServiceCall) -> None:
        """Get API call tracking information."""
        account = call.data.get(ATTR_ACCOUNT)
        
        # Find the entry for this account (or use first if no account specified)
        for entry_id, data in hass.data[DOMAIN].items():
            if account and data["account_name"] != account:
                continue
            
            # Get rate limits from local tracking
            rate_info = data["api"].get_rate_limits()
            
            # Log the information
            _LOGGER.info("=" * 80)
            _LOGGER.info("EBAY API CALL TRACKING - Account: %s", data["account_name"])
            _LOGGER.info("=" * 80)
            _LOGGER.info("NOTE: This shows LOCAL tracking data, not actual eBay quotas")
            _LOGGER.info("eBay's Analytics API requires OAuth 2.0 (not available with Auth'n'Auth)")
            _LOGGER.info("")
            _LOGGER.info("Tracking started: %s", rate_info["tracking_start"])
            _LOGGER.info("Current time: %s", rate_info["current_time"])
            _LOGGER.info("Total API calls made: %d", rate_info["total_calls"])
            _LOGGER.info("Estimated daily total: %.0f calls/day", rate_info["estimated_daily_total"])
            _LOGGER.info("")
            
            for api in rate_info["apis"]:
                _LOGGER.info("API: %s", api["api_name"].upper())
                _LOGGER.info("  Calls made: %d", api["calls_made"])
                _LOGGER.info("  Tracking duration: %.2f hours", api["hours_elapsed"])
                _LOGGER.info("  Rate: %.1f calls/hour", api["calls_per_hour"])
                _LOGGER.info("  Estimated daily: %.0f calls/day", api["estimated_daily"])
                _LOGGER.info("")
            
            _LOGGER.info("Standard eBay Production Limits (for reference):")
            _LOGGER.info("  Finding API: 5,000 calls/day")
            _LOGGER.info("  Trading API: varies by call (typically 1,500-5,000/day)")
            _LOGGER.info("  Shopping API: 5,000 calls/day")
            _LOGGER.info("")
            
            if rate_info["estimated_daily_total"] > 4000:
                _LOGGER.warning("⚠️  Estimated usage is HIGH - consider increasing update intervals")
            elif rate_info["estimated_daily_total"] > 2000:
                _LOGGER.info("ℹ️  Estimated usage is MODERATE - within safe limits")
            else:
                _LOGGER.info("✅ Estimated usage is LOW - well within limits")
            
            _LOGGER.info("=" * 80)
            
            # Only check first matching account
            return
    
    # Register all services
    hass.services.async_register(DOMAIN, SERVICE_REFRESH_BIDS, refresh_bids)
    hass.services.async_register(DOMAIN, SERVICE_REFRESH_WATCHLIST, refresh_watchlist)
    hass.services.async_register(DOMAIN, SERVICE_REFRESH_PURCHASES, refresh_purchases)
    hass.services.async_register(DOMAIN, SERVICE_REFRESH_SEARCH, refresh_search)
    hass.services.async_register(DOMAIN, SERVICE_REFRESH_ACCOUNT, refresh_account)
    hass.services.async_register(DOMAIN, SERVICE_REFRESH_ALL, refresh_all)
    hass.services.async_register(DOMAIN, SERVICE_REFRESH_API_USAGE, refresh_api_usage)
    hass.services.async_register(DOMAIN, SERVICE_CREATE_SEARCH, create_search)
    hass.services.async_register(DOMAIN, SERVICE_UPDATE_SEARCH, update_search)
    hass.services.async_register(DOMAIN, SERVICE_DELETE_SEARCH, delete_search)
    hass.services.async_register(DOMAIN, SERVICE_GET_RATE_LIMITS, get_rate_limits)
