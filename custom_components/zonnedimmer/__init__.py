"""The Zonnedimmer integration."""
from __future__ import annotations

import logging

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError

from .api import USER_AGENT, ZonnedimmerAPI, ZonnedimmerError
from .const import (
    ALLOWED_DURATIONS,
    CONF_BASE_URL,
    CONF_COOLDOWN,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEFAULT_COOLDOWN,
    DOMAIN,
    SERVICE_TURN_OFF,
    ATTR_DURATION,
)
from .coordinator import ZonnedimmerCooldownActive, ZonnedimmerCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["button", "sensor", "binary_sensor"]

_LOGGER.warning("Zonnedimmer integration module geladen")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Zonnedimmer from a config entry."""
    _LOGGER.warning("Zonnedimmer integration wordt geladen (setup_entry)")
    base_url = entry.data[CONF_BASE_URL]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    cooldown = entry.data.get(CONF_COOLDOWN, DEFAULT_COOLDOWN)

    session = aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=30),
        headers={"User-Agent": USER_AGENT},
    )
    api = ZonnedimmerAPI(session, base_url, username, password)
    coordinator = ZonnedimmerCoordinator(hass, api, cooldown)

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as err:
        await session.close()
        raise ConfigEntryNotReady(f"Kan geen verbinding maken met Zonnedimmer: {err}") from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "session": session,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if data:
            await data["session"].close()

    return unload_ok


def _register_services(hass: HomeAssistant) -> None:
    """Registreer de zonnedimmer.turn_off service."""

    async def handle_turn_off(call: ServiceCall) -> None:
        duration = call.data.get(ATTR_DURATION, 2)
        try:
            duration = int(duration)
        except (TypeError, ValueError):
            raise ServiceValidationError(f"Ongeldige duur: {duration}")
        if duration not in ALLOWED_DURATIONS:
            raise ServiceValidationError(
                f"Ongeldige duur {duration}. Toegestaan: {ALLOWED_DURATIONS}"
            )

        entries = hass.data.get(DOMAIN, {})
        if not entries:
            raise ServiceValidationError("Zonnedimmer is niet geconfigureerd")
        for data in entries.values():
            api: ZonnedimmerAPI = data["api"]
            coordinator: ZonnedimmerCoordinator = data["coordinator"]
            try:
                coordinator.ensure_not_cooling_down()
                await api.async_turn_off(duration)
                coordinator.record_action()
                await coordinator.async_request_refresh()
            except ZonnedimmerCooldownActive as err:
                raise ServiceValidationError(
                    f"Cooldown actief. Probeer opnieuw over {err.remaining_seconds} seconden."
                ) from err
            except ZonnedimmerError as err:
                raise ServiceValidationError(str(err)) from err

    if not hass.services.has_service(DOMAIN, SERVICE_TURN_OFF):
        hass.services.async_register(DOMAIN, SERVICE_TURN_OFF, handle_turn_off)
