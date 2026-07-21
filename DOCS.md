# Zonnedimmer Add-on - Documentatie

## Inhoudsopgave

1. [Installatie](#installatie)
2. [Configuratie](#configuratie)
3. [Eerste login](#eerste-login)
4. [Home Assistant integratie](#home-assistant-integratie)
   - [rest_command](#rest_command)
   - [Script](#script)
   - [Dashboardknop](#dashboardknop)
   - [Automatisering](#automatisering)
   - [Sensor voor laatste actie](#sensor-voor-laatste-actie)
   - [Melding bij herinloggen](#melding-bij-herinloggen)
5. [Interne add-on hostname](#interne-add-on-hostname)
6. [Foutoplossing](#foutoplossing)

---

## Installatie

1. Plaats de add-on repository op GitHub (of een andere git-host).
2. In Home Assistant: **Instellingen → Add-ons → Add-on Store → ⋮ → Repositories**.
3. Voeg de repository URL toe.
4. Installeer de **Zonnedimmer** add-on.
5. Configureer en start.

## Configuratie

Zie [README.md](README.md) voor het overzicht van configuratieopties.

## Eerste login

### Optie A: Automatische login via configuratie

Vul `username` en `password` in de add-on configuratie. De add-on logt automatisch in wanneer de sessie verlopen is.

### Optie B: Handmatige login via Ingress

1. Start de add-on.
2. Open de Ingress-pagina (klik op "Openen in webinterface" in de add-on pagina).
3. Klik op de knop **Inloggen**.
4. De add-on opent een browser, navigeert naar Zonnedimmer en logt in met de opgegeven referenties.
5. De sessie wordt persistent opgeslagen.

---

## Home Assistant integratie

### rest_command

Voeg toe aan `configuration.yaml`:

```yaml
rest_command:
  zonnedimmer_uit:
    url: "http://zonnedimmer:8099/turn-off"
    method: POST
    content_type: "application/json"
    payload: '{"duration": {{ duration | default(2) }}}'
    timeout: 60
```

Roep aan met een `duration` van `1`, `2`, `4` of `8`:

```yaml
service: rest_command.zonnedimmer_uit
data:
  duration: 2
```

> **Belangrijk:** Vervang `zonnedimmer` door de daadwerkelijke add-on slug indien anders. Zie [Interne add-on hostname](#interne-add-on-hostname).
>
> Het verouderde endpoint `POST /turn-off-for-two-hours` blijft werken als alias voor `duration=2`.

### Script

Voeg toe aan `configuration.yaml` of `scripts.yaml`:

```yaml
script:
  zonnedimmer_uitschakelen:
    alias: "Zonnedimmer uitzetten"
    icon: mdi:power-plug-off
    fields:
      duration:
        description: "Aantal uren uitzetten (1, 2, 4 of 8)"
        example: 2
        default: 2
        selector:
          number:
            min: 1
            max: 8
            step: 1
            mode: box
    sequence:
      - service: rest_command.zonnedimmer_uit
        data:
          duration: "{{ duration | default(2) }}"
      - service: input_text.set_value
        data:
          entity_id: input_text.zonnedimmer_last_action
          value: "{{ now().strftime('%Y-%m-%d %H:%M:%S') }}"
      - service: input_datetime.set_datetime
        data:
          entity_id: input_datetime.zonnedimmer_last_action_time
          datetime: "{{ now().strftime('%Y-%m-%d %H:%M:%S') }}"
      - choose:
          - conditions:
              - condition: template
                value_template: "{{ rest_command_response_success | default(false) }}"
            sequence:
              - service: notify.notify
                data:
                  message: "Zonnedimmer uitgeschakeld voor {{ duration | default(2) }} uur."
```

### Dashboardknop

Voeg toe aan je Lovelace dashboard (YAML mode):

```yaml
type: button
name: Zonnedimmer 2 uur uit
icon: mdi:power-plug-off
tap_action:
  action: call-service
  service: script.zonnedimmer_uitschakelen
  data:
    duration: 2
  confirmation:
    text: "Zonnedimmer 2 uur uitzetten?"
hold_action:
  action: more-info
```

Of via de UI editor: voeg een **Button** kaart toe, selecteer het script `zonnedimmer_uitschakelen` en vul `duration` in (1, 2, 4 of 8).

### Automatisering

Voeg toe aan `automations.yaml`:

```yaml
- alias: "Zonnedimmer automatisch uitschakelen bij lage batterij"
  description: "Schakel Zonnedimmer uit bij lage thuisbatterij"
  trigger:
    - platform: numeric_state
      entity_id: sensor.home_battery_level
      below: 10
  condition:
    - condition: time
      after: "06:00:00"
      before: "23:00:00"
  action:
    - service: script.zonnedimmer_uitschakelen
      data:
        duration: 2
  mode: single
```

Voorbeeld met zon-energie overschot:

```yaml
- alias: "Zonnedimmer uitschakelen bij zonnepiek"
  trigger:
    - platform: numeric_state
      entity_id: sensor.zonne_energie_productie
      above: 5000
      for:
        minutes: 15
  action:
    - service: script.zonnedimmer_uitschakelen
      data:
        duration: 2
  mode: single
```

### Sensor voor laatste actie

Maak helpers aan via **Instellingen → Apparaten & Diensten → Helpers**:

1. **input_text** `zonnedimmer_last_action` - tekstveld voor laatste actie tijdstip.
2. **input_datetime** `zonnedimmer_last_action_time` - datum/tijd van laatste actie.

Of in `configuration.yaml`:

```yaml
input_text:
  zonnedimmer_last_action:
    name: Zonnedimmer Laatste Actie
    initial: ""

input_datetime:
  zonnedimmer_last_action_time:
    name: Zonnedimmer Laatste Actie Tijd
    has_date: true
    has_time: true

template:
  - sensor:
      - name: "Zonnedimmer Status"
        state: >
          {% if states('input_text.zonnedimmer_last_action') not in ['', 'unknown', 'none'] %}
            active
          {% else %}
            idle
          {% endif %}
        icon: mdi:solar-power
        attributes:
          last_action: "{{ states('input_text.zonnedimmer_last_action') }}"
          last_action_time: "{{ states('input_datetime.zonnedimmer_last_action_time') }}"
```

### Melding bij herinloggen

Deze automatisering controleert het `/status` endpoint van de add-on en stuurt een notificatie wanneer herinloggen nodig is:

```yaml
rest_command:
  zonnedimmer_check_status:
    url: "http://zonnedimmer:8099/status"
    method: GET
    timeout: 10

template:
  - sensor:
      - name: "Zonnedimmer Login Vereist"
        state: >
          {{ states('sensor.zonnedimmer_login_required') | default('unknown') }}
        icon: mdi:account-alert

- alias: "Zonnedimmer - Herinloggen nodig melding"
  trigger:
    - platform: time_pattern
      minutes: "/30"
  condition:
    - condition: template
      value_template: >
        {{ states('sensor.zonnedimmer_login_required') == 'True' }}
  action:
    - service: notify.notify
      data:
        title: "Zonnedimmer - Actie vereist"
        message: "De Zonnedimmer sessie is verlopen. Log opnieuw in via de add-on Ingress-pagina."
        data:
          tag: zonnedimmer_relogin
  mode: single
```

**Alternatief met een sensor die het status endpoint pollt:**

```yaml
sensor:
  - platform: rest
    name: Zonnedimmer Add-on Status
    resource: http://zonnedimmer:8099/status
    method: GET
    scan_interval: 300
    json_attributes:
      - loginRequired
      - lastActionResult
      - cooldownRemainingSeconds
      - busy
    value_template: "{{ value_json.status }}"
```

Dan in je automatisering:

```yaml
- alias: "Zonnedimmer - Sessie verlopen notificatie"
  trigger:
    - platform: state
      entity_id: sensor.zonnedimmer_add_on_status
      attribute: loginRequired
      to: true
  action:
    - service: notify.notify
      data:
        title: "Zonnedimmer Login Verlopen"
        message: "Log opnieuw in via de add-on Ingress-pagina of vul referenties in de add-on configuratie."
```

---

## Interne add-on hostname

Binnen Home Assistant OS communiceren add-ons met elkaar via de add-on slug als hostname:

```
http://<addon-slug>:<poort>/<endpoint>
```

Voor deze add-on met slug `zonnedimmer` en poort `8099`:

```
http://zonnedimmer:8099/turn-off
```

> `localhost` vanuit Home Assistant verwijst naar de Home Assistant container zelf, **niet** naar de add-on. Gebruik altijd de add-on slug als hostname.
>
> Als je de add-on een andere slug hebt gegeven, pas de URL dienovereenkomstig aan.

### Hoe de URL opgebouwd wordt

1. De add-on slug staat in `config.yaml` als `slug: zonnedimmer`.
2. Home Assistant maakt een intern DNS record aan: `<slug>.hassio`.
3. De poort is gedefinieerd in `config.yaml` onder `ports: 8099/tcp`.
4. De volledige URL: `http://zonnedimmer:8099/turn-off`.

---

## Foutoplossing

### De add-on start niet

- Controleer of de architectuur ondersteund wordt (`amd64` of `aarch64`).
- Bekijk de add-on logs: **Instellingen → Add-ons → Zonnedimmer → Logs**.

### Knop niet gevonden

- De Zonnedimmer website kan gewijzigd zijn. Pas de knopteksten aan in `app/index.js` (functie `performTurnOff`, constante `ALLOWED_DURATIONS`).
- Zet `headless: false` en `log_level: debug` voor meer diagnostiek.

### Login werkt niet

- Controleer gebruikersnaam en wachtwoord in de add-on configuratie.
- Als Zonnedimmer 2FA gebruikt, log dan handmatig in via de Ingress-pagina.
- Controleer of de profielmap `/data/browser-profile` schrijfbaar is.

### Cooldown te lang

- Pas `cooldown_minutes` aan in de add-on configuratie (minimum 1 minuut).

### Meerdere aanvragen tegelijk

- De add-on gebruikt een mutex om gelijktijdige browserprocessen te voorkomen.
- Bij een bezette add-on wordt HTTP 409 (Conflict) geretourneerd.
