# Zonnedimmer Home Assistant Integration

Een native Home Assistant integratie voor **[Zonnedimmer](https://zonnedimmer.nl)**.
Geen `rest_command`, `script` of helpers meer handmatig configureren — de integratie
maakt zelf de entiteiten aan.

## Functies

- Setup via **Config Flow** (Instellingen → Apparaten & Diensten → Integratie toevoegen)
- Vier **knoppen**: zet uit voor 1, 2, 4 of 8 uur
- **Sensoren**: laatste actie, resterende cooldown, inlogstatus
- **Binaire sensor**: herinloggen vereist
- **Service** `zonnedimmer.turn_off` met `duration` (1/2/4/8) voor automatiseringen
- Werkt volledig via HTTP (geen Chromium/Playwright), licht en snel

## Installatie

### Optie A — HACS

1. Voeg deze repository toe in HACS als **Integration** (Custom repositories).
2. Installeer **Zonnedimmer**.
3. Herstart Home Assistant.

### Optie B — Handmatig

1. Kopieer de map `custom_components/zonnedimmer/` naar je
   `custom_components/zonnedimmer/` op je Home Assistant installatie.
2. Herstart Home Assistant.

## Configuratie

1. Ga naar **Instellingen → Apparaten & Diensten → Integratie toevoegen**.
2. Zoek **Zonnedimmer**.
3. Vul in:
   - URL (standaard `https://app.zonnedimmer.nl`)
   - E-mailadres
   - Wachtwoord
   - Cooldown in seconden (standaard 300)
4. De integratie test de inloggegevens en maakt het apparaaat met entiteiten aan.

## Entiteiten

Na installatie verschijnt er één apparaat **Zonnedimmer** met:

| Entiteit | Type | Beschrijving |
|----------|------|--------------|
| `button.zonnedimmer_uitzetten_voor_1_uur` | Knop | Zet uit voor 1 uur |
| `button.zonnedimmer_uitzetten_voor_2_uur` | Knop | Zet uit voor 2 uur |
| `button.zonnedimmer_uitzetten_voor_4_uur` | Knop | Zet uit voor 4 uur |
| `button.zonnedimmer_uitzetten_voor_8_uur` | Knop | Zet uit voor 8 uur |
| `sensor.zonnedimmer_laatste_actie` | Sensor | Tijdstip van laatste dim-actie |
| `sensor.zonnedimmer_cooldown_resterend` | Sensor | Resterende cooldown (s) |
| `sensor.zonnedimmer_inlogstatus` | Sensor | ingelogd / uitgelogd |
| `binary_sensor.zonnedimmer_herinloggen_vereist` | Binaire sensor | Aan als sessie verlopen is |

## Automatisering (voorbeeld)

```yaml
- alias: "Zonnedimmer automatisch uitzetten"
  trigger:
    - platform: numeric_state
      entity_id: sensor.home_battery_level
      below: 10
  action:
    - action: zonnedimmer.turn_off
      data:
        duration: 2
```

Of roep direct een knop aan:

```yaml
- action: button.press
  target:
    entity_id: button.zonnedimmer_uitzetten_voor_4_uur
```

## Add-on (verouderd)

De eerdere Home Assistant add-on (`zonnedimmer/`) gebruikt Playwright/Chromium en
vereist handmatige `rest_command`-configuratie. De integratie in deze map vervangt
die voor nieuwe installaties.

## Licentie

MIT
