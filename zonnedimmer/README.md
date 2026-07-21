# Zonnedimmer Home Assistant Add-on

Automatiseer **Zonnedimmer** binnen Home Assistant met behulp van Playwright (Chromium) browserautomatisering.

## Functies

- Volledig installeerbaar als Home Assistant add-on (lokale repository)
- Werkt op `amd64` en `aarch64`
- Playwright met Chromium voor betrouwbare browserautomatisering
- Persistente opslag van cookies en sessies in `/data/browser-profile`
- Automatisch starten na herstart van Home Assistant (`boot: auto`, `startup: application`)
- REST-endpoint voor integratie met `rest_command`
- Mutex/lock ter voorkoming van gelijktijdige browserprocessen
- Cooldown van minimaal 5 minuten tussen acties
- Ingress-pagina voor status en handmatige login
- Veilige afhandeling van referenties via add-on configuratie (password type)
- Periodieke login-controle met melding wanneer herinloggen nodig is

## Installatie

1. Plaats de bestanden in een git-repository (bijv. GitHub).
2. Ga in Home Assistant naar **Instellingen → Add-ons → Add-on Store → ⋮ → Repositories**.
3. Voeg de URL van je repository toe en klik **Toevoegen**.
4. De add-on **Zonnedimmer** verschijnt in de add-on store. Klik **Installeren**.
5. Configureer de add-on (zie hieronder).
6. Start de add-on.

## Configuratie

Open de add-on configuratie in Home Assistant:

| Optie | Standaard | Beschrijving |
|-------|-----------|--------------|
| `zonnedimmer_url` | `https://app.zonnedimmer.nl` | URL van de Zonnedimmer webapp |
| `headless` | `true` | Browser headless uitvoeren (`false` voor debugging) |
| `cooldown_minutes` | `5` | Minimum tijd tussen twee acties |
| `browser_timeout_ms` | `60000` | Time-out voor browseracties in milliseconden |
| `log_level` | `info` | Logniveau: `debug`, `info`, `warning`, `error` |
| `login_check_interval_minutes` | `60` | Interval voor periodieke login-controle |
| `username` | _(leeg)_ | Optioneel: gebruikersnaam voor automatische login |
| `password` | _(leeg)_ | Optioneel: wachtwoord voor automatische login (wordt veilig opgeslagen) |

### Eerste login

1. Vul `username` en `password` in de add-on configuratie, **of**
2. Open de **Ingress**-pagina van de add-on en klik op **Inloggen**.
3. Na succesvolle login wordt de sessie persistent opgeslagen in `/data/browser-profile`.
4. Daaropvolgende acties worden headless uitgevoerd.

## REST API

### `POST /turn-off`

Schakelt Zonnedimmer uit voor het opgegeven aantal uren. Toegestane waarden: `1`, `2`, `4` of `8` uur.

**Verzoek (JSON body):**
```json
{ "duration": 2 }
```

Of via query string: `POST /turn-off?duration=2`.

**Respons (succes):**
```json
{
  "success": true,
  "status": "completed",
  "durationHours": 2,
  "message": "Zonnedimmer uitgeschakeld voor 2 uur (knop: \"2 uur uitzetten\").",
  "timestamp": "2026-01-15T12:00:00.000Z"
}
```

**Respons (ongeldige duur):**
```json
{
  "success": false,
  "status": "invalid_duration",
  "error": "Ongeldige duur. Toegestaan: 1, 2, 4, 8 uur.",
  "allowedDurations": [1, 2, 4, 8],
  "timestamp": "2026-01-15T12:00:00.000Z"
}
```

**Respons (cooldown):**
```json
{
  "success": false,
  "status": "cooldown",
  "error": "Cooldown actief. Probeer opnieuw over 283 seconden.",
  "cooldownRemainingSeconds": 283,
  "timestamp": "2026-01-15T12:00:00.000Z"
}
```

**Respons (login vereist):**
```json
{
  "success": false,
  "status": "login_required",
  "error": "Sessie verlopen en geen referenties opgegeven. Log handmatig in via de Ingress-pagina.",
  "timestamp": "2026-01-15T12:00:00.000Z"
}
```

### `POST /turn-off-for-two-hours` (verouderd)

Bestaande alias die equivalent is aan `POST /turn-off` met `duration=2`. Blijft werken voor eerdere `rest_command`-configuraties.

### `GET /status`

Geeft de huidige status van de add-on.

### `GET /health`
Health check endpoint.

### `POST /login`

Handmatige login (gebruikt door Ingress-pagina).

## Home Assistant integratie

Zie `DOCS.md` voor volledige voorbeelden van `rest_command`, scripts, automatiseringen, dashboardknoppen, sensoren en meldingen.

## Architektuur

```
Home Assistant
  └─ rest_command → POST http://<addon-slug>:8099/turn-off
       └─ Express webservice (Node.js)
            └─ Playwright (Chromium)
                 └─ Persistent profile: /data/browser-profile
```

## Ondersteunde architecturen

- `amd64`
- `aarch64`

## Licentie

MIT
