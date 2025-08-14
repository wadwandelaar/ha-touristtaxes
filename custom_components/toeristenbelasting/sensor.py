from datetime import datetime
import logging
from functools import partial
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_change
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensor."""
    sensor = TouristTaxSensor(hass, config_entry)
    async_add_entities([sensor])
    await sensor.async_schedule_update()

    # Save for service use
    hass.data[DOMAIN] = sensor

    return True

class TouristTaxSensor(Entity):
    def __init__(self, hass, config_entry):
        self.hass = hass
        self._config = config_entry.data
        self._state = 0.0
        self._days = {}
        self._unsub_time = None

    async def async_schedule_update(self):
        """Schedule the daily update based on input_datetime."""
        if self._unsub_time:
            self._unsub_time()

        time_state = self.hass.states.get("input_datetime.tourist_tax_update_time")
        if time_state:
            hour = int(time_state.attributes.get("hour", 23))
            minute = int(time_state.attributes.get("minute", 0))

            self._unsub_time = async_track_time_change(
                self.hass,
                partial(self._update_daily),
                hour=hour,
                minute=minute,
                second=0
            )
            _LOGGER.debug(f"TouristTaxes: Scheduled update for {hour:02}:{minute:02}")
        else:
            _LOGGER.warning("TouristTaxes: input_datetime.tourist_tax_update_time not found")

    async def _update_daily(self, now=None):
        """Perform the daily update."""
        try:
            now = now or datetime.now()

            # Haal de zone op via entity_id
            zone_entity_id = self._config['home_zone']
            zone = self.hass.states.get(zone_entity_id)
            if not zone:
                _LOGGER.error(f"TouristTaxes: Zone {zone_entity_id} not found")
                return

            # Haal 'home' uit 'zone.home'
            zone_id = zone_entity_id.split(".")[-1].lower()

            person_entities = self.hass.states.async_entity_ids("person")
            persons_in_zone = [
                e for e in person_entities
                if self.hass.states.get(e).state.lower() == zone_id
            ]

            # Logging wie er wordt meegeteld
            _LOGGER.debug(f"TouristTaxes: Zone ID = '{zone_id}'")
            _LOGGER.debug(f"TouristTaxes: Personen in zone '{zone_id}': {[e for e in persons_in_zone]}")

            day_name = now.strftime("%A %d %b")
            self._days[day_name] = len(persons_in_zone)

            self._state = round(
                sum(self._days.values()) * self._config['price_per_person'],
                2
            )

            self.async_write_ha_state()
            _LOGGER.info(f"TouristTaxes: Updated {day_name} - {len(persons_in_zone)} persons -> €{self._state}")

        except Exception as e:
            _LOGGER.error(f"TouristTaxes: Update failed: {e}")

    @property
    def name(self):
        return "Tourist Taxes"

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return {
            'days': self._days,
            'price_per_person': self._config['price_per_person'],
            'next_update_scheduled': self._unsub_time is not None
        }
