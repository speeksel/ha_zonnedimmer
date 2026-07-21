#!/usr/bin/env bash
# Zonnedimmer login diagnostic - repliceert wat de HA-integration doet.
#
# Gebruik:
#   export ZONNEDIMMER_EMAIL="jouw@email.nl"
#   export ZONNEDIMMER_PASSWORD="jouwWachtwoord"
#   bash zonnedimmer-login-test.sh
#
# Optioneel: export BASE_URL="https://app.zonnedimmer.nl" (standaard)

set -euo pipefail

BASE_URL="${BASE_URL:-https://app.zonnedimmer.nl}"
JAR="$(mktemp -t znd_cookies.XXXXXX)"
trap 'rm -f "$JAR"' EXIT

EMAIL="${ZONNEDIMMER_EMAIL:?Set ZONNEDIMMER_EMAIL env var}"
PASSWORD="${ZONNEDIMMER_PASSWORD:?Set ZONNEDIMMER_PASSWORD env var}"

UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

echo "=== 1. GET /login (haal CSRF + sessiecookie) ==="
LOGIN_HTML="$(curl -sS -X GET "${BASE_URL}/login" \
  -A "$UA" \
  -c "$JAR" \
  -w "\n---HTTP_STATUS:%{http_code}---\n")"

LOGIN_STATUS="$(printf '%s' "$LOGIN_HTML" | grep -oE 'HTTP_STATUS:[0-9]+' | cut -d: -f2)"
echo "HTTP status: $LOGIN_STATUS"

CSRF="$(printf '%s' "$LOGIN_HTML" | grep -oE 'csrf-token" content="[^"]+"' | sed -E 's/.*content="([^"]+)"/\1/')"
if [ -z "$CSRF" ]; then
  echo "FAIL: geen CSRF-token gevonden op loginpagina"
  exit 1
fi
echo "CSRF token: ${CSRF:0:12}... (lengte ${#CSRF})"

echo ""
echo "=== 2. POST /login (credentials + Referer/Origin) ==="
LOGIN_RESP="$(curl -sS -X POST "${BASE_URL}/login" \
  -A "$UA" \
  -b "$JAR" -c "$JAR" \
  -H "Referer: ${BASE_URL}/login" \
  -H "Origin: ${BASE_URL}" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "_token=${CSRF}" \
  --data-urlencode "email=${EMAIL}" \
  --data-urlencode "password=${PASSWORD}" \
  -L \
  -o /tmp/znd_login_body.html \
  -w "HTTP_STATUS:%{http_code}\nFINAL_URL:%{url_effective}\nREDIRECTS:%{num_redirects}\n")"

echo "$LOGIN_RESP"
echo "Body opgeslagen in /tmp/znd_login_body.html ($(wc -c < /tmp/znd_login_body.html) bytes)"

# Detecteer of we terug op /login staan (geldige indicator van failed auth bij Laravel)
if grep -q "Inloggen" /tmp/znd_login_body.html 2>/dev/null && grep -qi 'csrf-token' /tmp/znd_login_body.html 2>/dev/null; then
  echo ">> Resultaat: terug op /login = INGELIJD WAARSCHIJNLIJK ONGELDIG"
fi

echo ""
echo "=== 3. GET /dashboard/settings (verifieer sessie) ==="
SETTINGS_RESP="$(curl -sS -X GET "${BASE_URL}/dashboard/settings" \
  -A "$UA" \
  -b "$JAR" -c "$JAR" \
  -H "Referer: ${BASE_URL}/dashboard" \
  -L \
  -o /tmp/znd_settings.html \
  -w "HTTP_STATUS:%{http_code}\nFINAL_URL:%{url_effective}\n")"

echo "$SETTINGS_RESP"
echo "Body opgeslagen in /tmp/znd_settings.html ($(wc -c < /tmp/znd_settings.html) bytes)"

AUTH="$(grep -oE 'user-authenticated" content="[^"]+"' /tmp/znd_settings.html | sed -E 's/.*content="([^"]+)"/\1/' || echo "niet-gevonden")"
echo "user-authenticated meta: $AUTH"

echo ""
echo "=== Conclusie ==="
if [ "$AUTH" = "1" ]; then
  echo "SUCCES - sessie is geauthenticeerd. Login flow werkt."
  exit 0
else
  echo "FAIL - niet ingelogd."
  echo ""
  echo "Cookie jar bevat:"
  grep -v '^#' "$JAR" | grep -v '^$' || echo "(leeg)"
  echo ""
  echo "Tip: inspecteer /tmp/znd_login_body.html en /tmp/znd_settings.html"
  exit 1
fi
