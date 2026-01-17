"""The eBay integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
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
    SERVICE_REFRESH_ACCOUNT,
    SERVICE_REFRESH_ALL,
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
    )
    
    watchlist_coordinator = EbayWatchlistCoordinator(
        hass=hass,
        api=api,
        account_name=account_name,
        update_interval=timedelta(minutes=DEFAULT_WATCHLIST_INTERVAL),
    )
    
    purchases_coordinator = EbayPurchasesCoordinator(
        hass=hass,
        api=api,
        account_name=account_name,
        update_interval=timedelta(minutes=DEFAULT_PURCHASES_INTERVAL),
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
        await _create_search_coordinator(hass, entry, search_id, search_config)
    
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
    )
    
    await coordinator.async_config_entry_first_refresh()
    
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
    
    async def create_search(call: ServiceCall) -> None:
        """Create a new search."""
        account = call.data[ATTR_ACCOUNT]
        
        # Find the entry for this account
        for entry_id, data in hass.data[DOMAIN].items():
            if data["account_name"] == account:
                import uuid
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
                
                # Update config with new values
                for key in [
                    CONF_SEARCH_QUERY,
                    CONF_SITE,
                    CONF_CATEGORY_ID,
                    CONF_MIN_PRICE,
                    CONF_MAX_PRICE,
                    CONF_LISTING_TYPE,
                    CONF_UPDATE_INTERVAL,
                ]:
                    if key in call.data:
                        search_config[key] = call.data[key]
                
                # Recreate coordinator with new config
                old_coordinator = search_data["coordinator"]
                
                # Create new coordinator
                entry = hass.config_entries.async_get_entry(entry_id)
                await _create_search_coordinator(hass, entry, search_id, search_config)
                
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
                data["searches"].pop(search_id)
                
                # Save to storage
                searches = await data["store"].async_load() or {}
                searches.pop(search_id, None)
                await data["store"].async_save(searches)
                
                _LOGGER.info(f"Deleted search {search_id}")
                return
    
    # Register all services
    hass.services.async_register(DOMAIN, SERVICE_REFRESH_BIDS, refresh_bids)
    hass.services.async_register(DOMAIN, SERVICE_REFRESH_WATCHLIST, refresh_watchlist)
    hass.services.async_register(DOMAIN, SERVICE_REFRESH_PURCHASES, refresh_purchases)
    hass.services.async_register(DOMAIN, SERVICE_REFRESH_SEARCH, refresh_search)
    hass.services.async_register(DOMAIN, SERVICE_REFRESH_ACCOUNT, refresh_account)
    hass.services.async_register(DOMAIN, SERVICE_REFRESH_ALL, refresh_all)
    hass.services.async_register(DOMAIN, SERVICE_CREATE_SEARCH, create_search)
    hass.services.async_register(DOMAIN, SERVICE_UPDATE_SEARCH, update_search)
    hass.services.async_register(DOMAIN, SERVICE_DELETE_SEARCH, delete_search)
