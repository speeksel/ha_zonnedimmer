"""Config flow for Zonnedimmer."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
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

_LOGGER = logging.getLogger(__name__)


def _credential_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_BASE_URL, default=defaults.get(CONF_BASE_URL, DEFAULT_BASE_URL)
            ): str,
            vol.Required(
                CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")
            ): str,
            vol.Required(
                CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")
            ): str,
            vol.Optional(
                CONF_COOLDOWN, default=defaults.get(CONF_COOLDOWN, DEFAULT_COOLDOWN)
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=7200)),
        }
    )


async def _try_login(base_url: str, username: str, password: str) -> None:
    """Probeer in te loggen; genereert excepties bij fouten."""
    session = aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=30),
        headers={"User-Agent": USER_AGENT},
    )
    try:
        api = ZonnedimmerAPI(session, base_url, username, password)
        await api.async_login()
    finally:
        await session.close()


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
            _LOGGER.warning(
                "Zonnedimmer config flow: probeer login voor %s @ %s",
                username, user_input.get(CONF_BASE_URL),
            )
            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()

            try:
                await _try_login(
                    user_input[CONF_BASE_URL], username, user_input[CONF_PASSWORD]
                )
            except ZonnedimmerAuthError:
                errors["base"] = "invalid_auth"
            except ZonnedimmerError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"

            if not errors:
                return self.async_create_entry(title="Zonnedimmer", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_credential_schema(),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> "ZonnedimmerOptionsFlow":
        return ZonnedimmerOptionsFlow()


class ZonnedimmerOptionsFlow(config_entries.OptionsFlow):
    """Opties-flow om inloggegevens te wijzigen via de Configureer-knop.

    `config_entry` wordt automatisch ingesteld door de OptionsFlow-baseclass
    (read-only property); geen __init__ override nodig.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await _try_login(
                    user_input[CONF_BASE_URL],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except ZonnedimmerAuthError:
                errors["base"] = "invalid_auth"
            except ZonnedimmerError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"

            if not errors:
                # Schrijf de nieuwe inloggegevens terug naar entry.data en herlaad.
                new_data = {**self.config_entry.data, **user_input}
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return self.async_create_entry(title="", data={})

            return self.async_show_form(
                step_id="init",
                data_schema=_credential_schema(user_input),
                errors=errors,
            )

        return self.async_show_form(
            step_id="init",
            data_schema=_credential_schema(dict(self.config_entry.data)),
            errors=errors,
        )
