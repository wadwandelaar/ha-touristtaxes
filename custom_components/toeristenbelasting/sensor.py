from homeassistant.helpers.entity import Entity
from .const import DOMAIN, PRICE_PER_PERSON

async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    if discovery_info is None:
        return

    sensors = [
        TouristTaxTodaySensor(hass),
        TouristTaxTotalSensor(hass)
    ]
    hass.data[f"{DOMAIN}_entities"] = sensors
    add_entities(sensors)

class TouristTaxTodaySensor(Entity):
    def __init__(self, hass):
        self.hass = hass
        self._attr_name = "Toeristenbelasting Vandaag"
        self._attr_unique_id = "toeristenbelasting_vandaag"

    @property
    def state(self):
        return self.hass.data.get(DOMAIN, {}).get("today_amount", 0.0)

    @property
    def extra_state_attributes(self):
        d = self.hass.data.get(DOMAIN, {})
        return {
            "personen": d.get("today_people", 0),
            "prijs_per_persoon": PRICE_PER_PERSON
        }

class TouristTaxTotalSensor(Entity):
    def __init__(self, hass):
        self.hass = hass
        self._attr_name = "Toeristenbelasting Totaal"
        self._attr_unique_id = "toeristenbelasting_totaal"

    @property
    def state(self):
        return self.hass.data.get(DOMAIN, {}).get("total_amount", 0.0)

    @property
    def extra_state_attributes(self):
        d = self.hass.data.get(DOMAIN, {})
        return {
            "totaal_nachten": d.get("total_nights", 0),
            "prijs_per_persoon": PRICE_PER_PERSON
        }
