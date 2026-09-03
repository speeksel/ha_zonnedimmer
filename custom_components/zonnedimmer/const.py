"""Constants for the Zonnedimmer integration."""

DOMAIN = "zonnedimmer"

# Config entry keys
CONF_BASE_URL = "base_url"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_COOLDOWN = "cooldown"

DEFAULT_BASE_URL = "https://app.zonnedimmer.nl"
DEFAULT_COOLDOWN = 300  # seconden

# Dim-duren die overeenkomen met de knoppen op de instellingenpagina
ALLOWED_DURATIONS = [1, 2, 4, 8]

# Poll-interval voor status (login + instellingen)
UPDATE_INTERVAL_SECONDS = 900

# Service
SERVICE_TURN_OFF = "turn_off"
ATTR_DURATION = "duration"

# Paden op de Zonnedimmer webapp
PATH_LOGIN = "/login"
PATH_SETTINGS = "/dashboard/settings"
PATH_MANUAL_POWER = "/dashboard/manual-power-control"
PATH_LOGOUT = "/logout"
