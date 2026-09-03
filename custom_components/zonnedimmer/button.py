"""Zonnedimmer knoppen: zet uit voor 1, 2, 4 of 8 uur."""
from __future__ import annotations

import logging

from homeassistant.components.button import (
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import ZonnedimmerError
from .const import ALLOWED_DURATIONS, DOMAIN
from .coordinator import ZonnedimmerCooldownActive, ZonnedimmerCoordinator
from .entity import ZonnedimmerEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Zonnedimmer buttons from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: ZonnedimmerCoordinator = data["coordinator"]
    api = data["api"]

    async_add_entities(
        [ZonnedimmerTurnOffButton(coordinator, api, entry, duration) for duration in ALLOWED_DURATIONS]
    )


class ZonnedimmerTurnOffButton(ZonnedimmerEntity, ButtonEntity):
    """Knop om Zonnedimmer uit te zetten voor een vast aantal uren."""

    def __init__(
        self,
        coordinator: ZonnedimmerCoordinator,
        api,
        entry: ConfigEntry,
        duration: int,
    ) -> None:
        description = ButtonEntityDescription(
            key=f"turn_off_{duration}",
            name=f"Uitzetten voor {duration} uur",
            icon="mdi:power-plug-off",
        )
        super().__init__(coordinator, entry, description)
        self._api = api
        self._duration = duration

    async def async_press(self) -> None:
        """Dim Zonnedimmer voor dit aantal uren."""
        try:
            self.coordinator.ensure_not_cooling_down()
            await self._api.async_turn_off(self._duration)
            self.coordinator.record_action()
            await self.coordinator.async_request_refresh()
        except ZonnedimmerCooldownActive as err:
            _LOGGER.warning(
                "Knop %d uur: %s", self._duration, err
            )
            raise HomeAssistantError(
                f"Cooldown actief. Probeer opnieuw over {err.remaining_seconds} seconden."
            ) from err
        except ZonnedimmerError as err:
            _LOGGER.error("Dimmen voor %d uur mislukt: %s", self._duration, err)
            raise HomeAssistantError(str(err)) from err
