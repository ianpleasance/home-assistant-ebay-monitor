"""Config flow for eBay integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_ACCOUNT_NAME,
    CONF_CATEGORY_ID,
    CONF_LISTING_TYPE,
    CONF_MAX_PRICE,
    CONF_MIN_PRICE,
    CONF_SEARCH_QUERY,
    CONF_SITE,
    CONF_UPDATE_INTERVAL,
    DEFAULT_SITE,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    EBAY_SITES,
    LISTING_TYPES,
)

_LOGGER = logging.getLogger(__name__)


class EbayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for eBay."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._account_name: str | None = None
        self._app_id: str | None = None
        self._dev_id: str | None = None
        self._cert_id: str | None = None
        self._token: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            self._account_name = user_input[CONF_ACCOUNT_NAME]

            # Check if account already exists
            await self.async_set_unique_id(self._account_name)
            self._abort_if_unique_id_configured()

            return await self.async_step_credentials()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_ACCOUNT_NAME): cv.string,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle eBay API credentials."""
        errors = {}

        if user_input is not None:
            self._app_id = user_input["app_id"]
            self._dev_id = user_input["dev_id"]
            self._cert_id = user_input["cert_id"]
            self._token = user_input["token"]

            # Basic validation - just check they're not empty
            # Actual API validation will happen when the integration loads
            if not all([self._app_id, self._dev_id, self._cert_id, self._token]):
                errors["base"] = "invalid_auth"
            else:
                return self.async_create_entry(
                    title=f"eBay - {self._account_name}",
                    data={
                        CONF_ACCOUNT_NAME: self._account_name,
                        "app_id": self._app_id,
                        "dev_id": self._dev_id,
                        "cert_id": self._cert_id,
                        "token": self._token,
                        "site_id": DEFAULT_SITE,
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required("app_id"): cv.string,
                vol.Required("dev_id"): cv.string,
                vol.Required("cert_id"): cv.string,
                vol.Required("token"): cv.string,
            }
        )

        return self.async_show_form(
            step_id="credentials",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "account_name": self._account_name,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> EbayOptionsFlowHandler:
        """Get the options flow for this handler."""
        return EbayOptionsFlowHandler(config_entry)


class EbayOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle eBay options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._searches: dict[str, dict[str, Any]] = {}
        self._current_search_id: str | None = None
        self._search_action: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return await self.async_step_search_list()

    async def async_step_search_list(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show list of searches with add/edit/delete options."""
        # Load current searches
        store = self.hass.data[DOMAIN][self._config_entry.entry_id]["store"]
        self._searches = await store.async_load() or {}

        if user_input is not None:
            action = user_input.get("action")

            if action == "add":
                self._search_action = "add"
                return await self.async_step_search_config()
            elif action and action.startswith("edit_"):
                self._current_search_id = action.replace("edit_", "")
                self._search_action = "edit"
                return await self.async_step_search_config()
            elif action and action.startswith("delete_"):
                self._current_search_id = action.replace("delete_", "")
                return await self.async_step_confirm_delete()

        # Build options for the form
        search_options = {"add": "Add New Search"}

        for search_id, search_config in self._searches.items():
            query = search_config[CONF_SEARCH_QUERY]
            search_options[f"edit_{search_id}"] = f"Edit: {query}"
            search_options[f"delete_{search_id}"] = f"Delete: {query}"

        data_schema = vol.Schema(
            {
                vol.Required("action"): vol.In(search_options),
            }
        )

        return self.async_show_form(
            step_id="search_list",
            data_schema=data_schema,
            description_placeholders={
                "account_name": self._config_entry.data[CONF_ACCOUNT_NAME],
                "search_count": len(self._searches),
            },
        )

    async def async_step_search_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure a search."""
        errors = {}

        # Get existing search config if editing
        existing_config = {}
        if self._search_action == "edit" and self._current_search_id:
            existing_config = self._searches.get(self._current_search_id, {})

        if user_input is not None:
            # Validate inputs
            if not user_input[CONF_SEARCH_QUERY].strip():
                errors["base"] = "invalid_query"
            else:
                # Create or update the search
                search_config = {
                    CONF_SEARCH_QUERY: user_input[CONF_SEARCH_QUERY],
                    CONF_SITE: user_input[CONF_SITE],
                    CONF_CATEGORY_ID: user_input.get(CONF_CATEGORY_ID) or None,
                    CONF_MIN_PRICE: user_input.get(CONF_MIN_PRICE) or None,
                    CONF_MAX_PRICE: user_input.get(CONF_MAX_PRICE) or None,
                    CONF_LISTING_TYPE: user_input[CONF_LISTING_TYPE],
                    CONF_UPDATE_INTERVAL: user_input[CONF_UPDATE_INTERVAL],
                }

                if self._search_action == "add":
                    # Generate new search ID
                    import uuid
                    search_id = str(uuid.uuid4())
                else:
                    search_id = self._current_search_id

                # Save to storage
                self._searches[search_id] = search_config
                store = self.hass.data[DOMAIN][self._config_entry.entry_id]["store"]
                await store.async_save(self._searches)

                # Reload the integration to create/update coordinators
                await self.hass.config_entries.async_reload(self._config_entry.entry_id)

                return self.async_create_entry(title="", data={})

        # Build form schema with defaults
        site_options = {code: name for code, name in EBAY_SITES.items()}
        listing_type_options = {code: name for code, name in LISTING_TYPES.items()}

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_SEARCH_QUERY,
                    default=existing_config.get(CONF_SEARCH_QUERY, ""),
                ): cv.string,
                vol.Required(
                    CONF_SITE,
                    default=existing_config.get(CONF_SITE, "uk"),
                ): vol.In(site_options),
                vol.Optional(
                    CONF_CATEGORY_ID,
                    default=existing_config.get(CONF_CATEGORY_ID, ""),
                ): cv.string,
                vol.Optional(
                    CONF_MIN_PRICE,
                    default=existing_config.get(CONF_MIN_PRICE),
                ): vol.Any(None, vol.Coerce(float)),
                vol.Optional(
                    CONF_MAX_PRICE,
                    default=existing_config.get(CONF_MAX_PRICE),
                ): vol.Any(None, vol.Coerce(float)),
                vol.Required(
                    CONF_LISTING_TYPE,
                    default=existing_config.get(CONF_LISTING_TYPE, "both"),
                ): vol.In(listing_type_options),
                vol.Required(
                    CONF_UPDATE_INTERVAL,
                    default=existing_config.get(
                        CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=1440)),
            }
        )

        return self.async_show_form(
            step_id="search_config",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "action": "Add" if self._search_action == "add" else "Edit",
            },
        )

    async def async_step_confirm_delete(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm deletion of a search."""
        search_id = self._current_search_id
        
        if user_input is not None:
            if user_input.get("confirm"):
                # Delete the search
                self._searches.pop(search_id, None)

                # Save to storage
                store = self.hass.data[DOMAIN][self._config_entry.entry_id]["store"]
                await store.async_save(self._searches)

                # Reload integration to remove coordinator
                await self.hass.config_entries.async_reload(self._config_entry.entry_id)

            return self.async_create_entry(title="", data={})

        search_query = self._searches.get(search_id, {}).get(CONF_SEARCH_QUERY, "Unknown")

        return self.async_show_form(
            step_id="confirm_delete",
            data_schema=vol.Schema(
                {
                    vol.Required("confirm", default=False): cv.boolean,
                }
            ),
            description_placeholders={
                "search_query": search_query,
            },
        )
