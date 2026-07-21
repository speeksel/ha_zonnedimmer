"""Gemeenschappelijke entity-class voor Zonnedimmer."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZonnedimmerCoordinator


class ZonnedimmerEntity(CoordinatorEntity):
    """Base entity voor alle Zonnedimmer entiteiten."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ZonnedimmerCoordinator,
        entry: ConfigEntry,
        description: EntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Zonnedimmer",
            manufacturer="Zonnedimmer",
            model="Webapp",
        )
