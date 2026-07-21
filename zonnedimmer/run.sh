#!/usr/bin/with-contenv bashio
set -e

export ZONNEDIMMER_URL=$(bashio::config 'zonnedimmer_url')
export ZONNEDIMMER_HEADLESS=$(bashio::config 'headless')
export ZONNEDIMMER_COOLDOWN_MINUTES=$(bashio::config 'cooldown_minutes')
export ZONNEDIMMER_TIMEOUT_MS=$(bashio::config 'browser_timeout_ms')
export ZONNEDIMMER_LOG_LEVEL=$(bashio::config 'log_level')
export ZONNEDIMMER_LOGIN_CHECK_MINUTES=$(bashio::config 'login_check_interval_minutes')
export ZONNEDIMMER_USERNAME=$(bashio::config 'username')
export ZONNEDIMMER_PASSWORD=$(bashio::config 'password')

# Zorg dat de persistente profielmap bestaat
mkdir -p /data/browser-profile
chmod 700 /data/browser-profile

# Start de Node.js webservice
exec node /app/index.js
