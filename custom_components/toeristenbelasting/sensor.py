from datetime import datetime
import logging
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_change

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensor."""
    sensor = TouristTaxSensor(hass, config_entry)
    async_add_entities([sensor])
    await sensor.async_schedule_update()  # Nieuwe methode aanroepen
    return True

class TouristTaxSensor(Entity):
    def __init__(self, hass, config_entry):
        self.hass = hass
        self._config = config_entry.data
        self._state = 0.0
        self._days = {}
        self._unsub_time = None

    async def async_schedule_update(self):
        """Schedule the daily update."""
        if self._unsub_time:
            self._unsub_time()

        time_state = self.hass.states.get("input_datetime.tourist_tax_update_time")
        if time_state:
            hour = int(time_state.attributes['hour'])
            minute = int(time_state.attributes['minute'])
            
            self._unsub_time = async_track_time_change(
                self.hass,
                self._update_daily,
                hour=hour,
                minute=minute
            )
            _LOGGER.debug(f"Scheduled update for {hour}:{minute}")

    async def _update_daily(self, now):
        """Perform the daily update."""
        try:
            zone = self._config['home_zone']
            persons = [
                e for e in self.hass.states.async_entity_ids("person") 
                if self.hass.states.get(e).state == zone
            ]
            
            day_name = now.strftime("%A %d %b")
            self._days[day_name] = len(persons)
            self._state = round(sum(self._days.values()) * self._config['price_per_person'], 2)
            self.async_write_ha_state()
            
            _LOGGER.debug(f"Updated: {len(persons)} persons = €{self._state}")
            
        except Exception as e:
            _LOGGER.error(f"Update failed: {e}")

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
            'next_update': self._unsub_time is not None
        }