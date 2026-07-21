"""Config flow for Zonnedimmer."""
from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .api import USER_AGENT, ZonnedimmerAPI, ZonnedimmerAuthError, ZonnedimmerError
from .const import (
    CONF_BASE_URL,
    CONF_COOLDOWN,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEFAULT_BASE_URL,
    DEFAULT_COOLDOWN,
    DOMAIN,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_COOLDOWN, default=DEFAULT_COOLDOWN): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=7200)
        ),
    }
)


class ZonnedimmerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Zonnedimmer."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()

            session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"User-Agent": USER_AGENT},
            )
            try:
                api = ZonnedimmerAPI(
                    session,
                    user_input[CONF_BASE_URL],
                    username,
                    user_input[CONF_PASSWORD],
                )
                await api.async_login()
            except ZonnedimmerAuthError:
                errors["base"] = "invalid_auth"
            except ZonnedimmerError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"
            finally:
                await session.close()

            if not errors:
                return self.async_create_entry(title="Zonnedimmer", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "ZonnedimmerOptionsFlow":
        """Options flow is not used; placeholder for future settings."""
        return ZonnedimmerOptionsFlow(config_entry)


class ZonnedimmerOptionsFlow(config_entries.OptionsFlow):
    """Placeholder options flow (geen opties in v1)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(step_id="init", data_schema=vol.Schema({}))
