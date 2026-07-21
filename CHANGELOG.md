# Changelog

## 1.1.0 (2026-07-21)

### Toegevoegd

- Nieuw REST-endpoint `POST /turn-off` met kiesbare duur (`1`, `2`, `4` of `8` uur) via JSON body of query string.
- Duration-validatie met `invalid_duration`-respons en lijst van toegestane waarden.
- Browser navigeert nu naar de instellingenpagina (`/dashboard/settings`) waar de dimknoppen staan.
- Accepteert de JavaScript `confirm()`-dialoog automatisch en controleert de HTTP-status van de form submission (`/dashboard/manual-power-control`).
- Ingress-pagina toont knoppen voor 1, 2, 4 en 8 uur.

### Gewijzigd

- Succes-respons bevat nu een `durationHours`-veld.
- `POST /turn-off-for-two-hours` is een backward-compatible alias voor `duration=2`.
- `rest_command`, script- en automatiseringsvoorbeelden in `DOCS.md` gebruiken het nieuwe parameterized endpoint.

## 1.0.0 (2026-07-14)

### Toegevoegd

- Eerste release van de Zonnedimmer Home Assistant add-on.
- Express webservice met REST-endpoint `POST /turn-off-for-two-hours`.
- Playwright (Chromium) browserautomatisering met persistent profiel in `/data/browser-profile`.
- Mutex/lock ter voorkoming van gelijktijdige browserprocessen.
- Cooldown van minimaal 5 minuten (configureerbaar).
- Ingress-pagina voor status en handmatige login.
- Periodieke login-controle met statusmelding.
- Ondersteuning voor `amd64` en `aarch64`.
- Configuratie via Home Assistant add-on schema met veilige wachtwoordafhandeling.
- Volledige Home Assistant integratie voorbeelden: `rest_command`, scripts, dashboardknoppen, automatiseringen, sensoren en notificaties.
