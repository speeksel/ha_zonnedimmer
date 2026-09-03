"""Zonnedimmer binaire sensor: herinloggen vereist."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ZonnedimmerCoordinator
from .entity import ZonnedimmerEntity

LOGIN_REQUIRED = BinarySensorEntityDescription(
    key="login_required",
    name="Herinloggen vereist",
    icon="mdi:account-alert",
    device_class=BinarySensorDeviceClass.PROBLEM,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zonnedimmer binary sensor."""
    coordinator: ZonnedimmerCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([ZonnedimmerLoginRequiredSensor(coordinator, entry)])


class ZonnedimmerLoginRequiredSensor(ZonnedimmerEntity, BinarySensorEntity):
    """Aan wanneer de sessie is verlopen."""

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, LOGIN_REQUIRED)

    @property
    def is_on(self) -> bool:
        data = self.coordinator.data or {}
        return not data.get("authenticated", False)
