"""Zonnedimmer sensoren: laatste actie en cooldown."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ZonnedimmerCoordinator
from .entity import ZonnedimmerEntity

SENSORS = (
    SensorEntityDescription(
        key="last_action",
        name="Laatste actie",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-outline",
    ),
    SensorEntityDescription(
        key="cooldown",
        name="Cooldown resterend",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:timer-sand",
    ),
    SensorEntityDescription(
        key="login_status",
        name="Inlogstatus",
        icon="mdi:account-check",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Zonnedimmer sensors from a config entry."""
    coordinator: ZonnedimmerCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([ZonnedimmerSensor(coordinator, entry, desc) for desc in SENSORS])


class ZonnedimmerSensor(ZonnedimmerEntity, SensorEntity):
    """Sensor gebaseerd op coordinator-data."""

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        if self.entity_description.key == "last_action":
            if self.coordinator.last_action_at is None:
                return None
            return self.coordinator.last_action_at.replace(tzinfo=None).isoformat()
        if self.entity_description.key == "cooldown":
            return self.coordinator.cooldown_remaining()
        if self.entity_description.key == "login_status":
            return "ingelogd" if data.get("authenticated") else "uitgelogd"
        return None

    @property
    def icon(self):
        if self.entity_description.key == "login_status":
            data = self.coordinator.data or {}
            return "mdi:account-check" if data.get("authenticated") else "mdi:account-alert"
        return self.entity_description.icon
