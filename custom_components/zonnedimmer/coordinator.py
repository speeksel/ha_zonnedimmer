"""DataUpdateCoordinator voor de Zonnedimmer integration."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import ZonnedimmerAPI, ZonnedimmerAuthError, ZonnedimmerError
from .const import DOMAIN, UPDATE_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)


class ZonnedimmerCoordinator(DataUpdateCoordinator):
    """Coördineert statuspolls en houdt lokaal laatste-actie/cooldown bij."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: ZonnedimmerAPI,
        cooldown_seconds: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.api = api
        self.cooldown_seconds = cooldown_seconds
        self.last_action_at: datetime | None = None

    async def _async_update_data(self) -> dict:
        """Controleer sessie; log opnieuw in wanneer nodig."""
        try:
            authenticated = await self.api.async_check_auth()
        except ZonnedimmerAuthError:
            authenticated = False
        except ZonnedimmerError as err:
            raise UpdateFailed(str(err)) from err

        if not authenticated:
            _LOGGER.warning("Zonnedimmer sessie niet actief, probeer in te loggen")
            try:
                await self.api.async_login()
                authenticated = True
            except ZonnedimmerAuthError as err:
                raise UpdateFailed(f"Inloggen mislukt (ongeldige credentials): {err}") from err
            except ZonnedimmerError as err:
                raise UpdateFailed(f"Herinloggen mislukt: {err}") from err

        return {"authenticated": authenticated}

    def record_action(self) -> None:
        """Registreer dat er zojuist een dim-actie is uitgevoerd."""
        self.last_action_at = datetime.utcnow()

    def cooldown_remaining(self) -> int:
        """Resterende cooldown in seconden (0 als geen cooldown actief)."""
        if self.last_action_at is None:
            return 0
        elapsed = (datetime.utcnow() - self.last_action_at).total_seconds()
        return max(0, int(self.cooldown_seconds - elapsed))
