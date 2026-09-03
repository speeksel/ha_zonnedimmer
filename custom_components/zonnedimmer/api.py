"""Zonnedimmer HTTP API client.

De Zonnedimmer webapp is een Laravel-applicatie met sessie-authenticatie.
De flow is:
  1. GET /login  -> haal CSRF-token uit <meta name="csrf-token"> + sessiecookie
  2. POST /login (form: _token, email, password) -> sessie wordt geauthenticeerd
  3. GET /dashboard/settings -> verse CSRF-token + controle user-authenticated
  4. POST /dashboard/manual-power-control (form: _token, duration) -> dimmen

Laravel's CSRF-middleware vereist een Referer/Origin-header bij POST-verzoeken.
Geen browser/Playwright nodig: volledig HTTP met aiohttp.
"""
from __future__ import annotations

import logging
import re
from http import HTTPStatus
from typing import Any

from aiohttp import ClientResponse, ClientSession, ClientTimeout

from .const import (
    PATH_LOGIN,
    PATH_MANUAL_POWER,
    PATH_SETTINGS,
    ALLOWED_DURATIONS,
)

_LOGGER = logging.getLogger(__name__)

# Een realistische browser User-Agent voorkomt dat Cloudflare/bot-detectie de
# simpele HTTP-requests blokkeert.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_META_CSRF = re.compile(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', re.IGNORECASE)
_META_AUTH = re.compile(
    r'<meta\s+name="user-authenticated"\s+content="([^"]+)"', re.IGNORECASE
)


class ZonnedimmerError(Exception):
    """Algemene fout bij communicatie met Zonnedimmer."""


class ZonnedimmerAuthError(ZonnedimmerError):
    """Inloggen of sessie is verlopen."""


class ZonnedimmerAPI:
    """Lightweight HTTP-client voor de Zonnedimmer webapp."""

    def __init__(
        self,
        session: ClientSession,
        base_url: str,
        username: str,
        password: str,
    ) -> None:
        self._session = session
        self._base = base_url.rstrip("/")
        self._username = username
        self._password = password

    # ── Helpers ──────────────────────────────────────────────
    @staticmethod
    def _extract_csrf(html: str) -> str | None:
        match = _META_CSRF.search(html)
        return match.group(1) if match else None

    @staticmethod
    def _extract_authenticated(html: str) -> bool:
        match = _META_AUTH.search(html)
        return bool(match and match.group(1) == "1")

    def _url(self, path: str) -> str:
        return f"{self._base}{path}"

    @staticmethod
    def _on_login_page(final_url: str) -> bool:
        return "/login" in final_url

    def _headers(self, referer_path: str | None = None) -> dict[str, str]:
        """Bouw request-headers met Referer/Origin voor Laravel-CSRF."""
        headers: dict[str, str] = {}
        if referer_path:
            headers["Referer"] = self._url(referer_path)
            headers["Origin"] = self._base
        return headers

    # ── Authenticatie ─────────────────────────────────────────
    async def async_login(self) -> bool:
        """Log in met e-mail/wachtwoord en authenticeer de sessie."""
        _LOGGER.info("Inloggen bij Zonnedimmer als %s", self._username)
        try:
            async with self._session.get(self._url(PATH_LOGIN)) as resp:
                if resp.status != HTTPStatus.OK:
                    raise ZonnedimmerError(f"Loginpagina gaf HTTP {resp.status}")
                html = await resp.text()
        except ZonnedimmerError:
            raise
        except Exception as err:
            raise ZonnedimmerError(f"Kon loginpagina niet ophalen: {err}") from err

        token = self._extract_csrf(html)
        if not token:
            raise ZonnedimmerError("CSRF-token niet gevonden op loginpagina")
        _LOGGER.debug("Login CSRF-token gevonden")

        payload = {
            "_token": token,
            "email": self._username,
            "password": self._password,
        }
        try:
            async with self._session.post(
                self._url(PATH_LOGIN),
                data=payload,
                headers=self._headers(PATH_LOGIN),
                allow_redirects=True,
            ) as resp:
                final_url = str(resp.url)
                status = resp.status
                # Lees de body altijd; bij redirect naar login staat er een foutmelding.
                body = await resp.text()
        except Exception as err:
            raise ZonnedimmerError(f"Login-verzoek mislukt: {err}") from err

        _LOGGER.warning(
            "Zonnedimmer login: POST /login -> status=%s final_url=%s body_len=%d",
            status, final_url, len(body),
        )

        # Laravel stuurt bij ongeldige credentials terug naar /login (302->200)
        # en bij validatiefouten een 422 met JSON, of 419 bij CSRF-mismatch.
        if status == HTTPStatus.UNPROCESSABLE_ENTITY:
            raise ZonnedimmerError(
                f"Login afgewezen door validatie (HTTP 422): {body[:300]}"
            )
        if status == HTTPStatus.TOO_MANY_REQUESTS:
            raise ZonnedimmerError("Te veel login-pogingen - even wachten")
        if status == HTTPStatus.FORBIDDEN or status == 419:
            raise ZonnedimmerError(
                f"Login geblokkeerd (HTTP {status}) - mogelijke CSRF/Cloudflare-blokkade: {body[:200]}"
            )

        # Verifieer succes definitief via de authenticated-meta-tag op de settingspagina.
        settings = await self.async_fetch_settings()
        if settings is None or not settings.get("authenticated"):
            if self._on_login_page(final_url):
                _LOGGER.warning(
                    "Zonnedimmer login faalde: geredirect naar /login "
                    "(waarschijnlijk ongeldige credentials)"
                )
                raise ZonnedimmerAuthError(
                    "Inloggen mislukt - ongeldig e-mailadres of wachtwoord"
                )
            _LOGGER.warning(
                "Zonnedimmer login niet bevestigd via settings-pagina "
                "(POST status=%s, url=%s, authenticated=%s)",
                status, final_url,
                settings.get("authenticated") if settings else None,
            )
            raise ZonnedimmerAuthError(
                "Inloggen leek te slagen maar sessie niet bevestigd"
            )

        _LOGGER.warning("Zonnedimmer login succesvol voor %s", self._username)
        return True

    async def async_fetch_settings(self) -> dict[str, Any] | None:
        """Haal de instellingenpagina op.

        Geeft None terug als de sessie is verlopen (redirect naar login).
        """
        try:
            async with self._session.get(
                self._url(PATH_SETTINGS),
                headers=self._headers(PATH_SETTINGS),
                allow_redirects=True,
            ) as resp:
                html = await resp.text()
                final_url = str(resp.url)
                status = resp.status
        except Exception as err:
            raise ZonnedimmerError(f"Kon instellingenpagina niet ophalen: {err}") from err

        _LOGGER.warning(
            "Zonnedimmer: GET /dashboard/settings -> status=%s url=%s authenticated=%s",
            status, final_url, self._extract_authenticated(html),
        )

        if self._on_login_page(final_url):
            return None

        return {
            "html": html,
            "authenticated": self._extract_authenticated(html),
            "url": final_url,
        }

    async def async_check_auth(self) -> bool:
        """Controleer of we nog ingelogd zijn."""
        data = await self.async_fetch_settings()
        return bool(data and data["authenticated"])

    async def _ensure_auth(self) -> None:
        if not await self.async_check_auth():
            await self.async_login()

    async def _fresh_csrf(self) -> str:
        """Haal een verse CSRF-token; logt in als de sessie verlopen is."""
        data = await self.async_fetch_settings()
        if data is None:
            await self.async_login()
            data = await self.async_fetch_settings()
        token = self._extract_csrf(data["html"]) if data else None
        if not token:
            # Soms is de meta-tag pas na een re-login aanwezig
            await self.async_login()
            data = await self.async_fetch_settings()
            token = self._extract_csrf(data["html"]) if data else None
        if not token:
            raise ZonnedimmerError("CSRF-token niet gevonden op instellingenpagina")
        return token

    # ── Acties ────────────────────────────────────────────────
    async def async_turn_off(self, duration: int) -> bool:
        """Dim de zonnepanelen voor het opgegeven aantal uren (1, 2, 4 of 8)."""
        if duration not in ALLOWED_DURATIONS:
            raise ZonnedimmerError(
                f"Ongeldige duur {duration}. Toegestaan: {ALLOWED_DURATIONS}"
            )

        await self._ensure_auth()
        token = await self._fresh_csrf()

        payload = {"_token": token, "duration": str(duration)}
        try:
            async with self._session.post(
                self._url(PATH_MANUAL_POWER),
                data=payload,
                headers=self._headers(PATH_SETTINGS),
                allow_redirects=True,
            ) as resp:
                final_url = str(resp.url)
                status = resp.status
        except Exception as err:
            raise ZonnedimmerError(f"Dim-verzoek mislukt: {err}") from err

        _LOGGER.debug("Turn-off POST -> status=%s url=%s", status, final_url)

        if self._on_login_page(final_url):
            raise ZonnedimmerAuthError("Sessie verlopen tijdens dimmen")
        if status >= HTTPStatus.BAD_REQUEST:
            raise ZonnedimmerError(f"Dimmen mislukt (HTTP {status})")

        _LOGGER.info("Zonnedimmer gedimd voor %d uur", duration)
        return True
