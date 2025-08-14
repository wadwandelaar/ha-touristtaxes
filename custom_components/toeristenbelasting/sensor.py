from datetime import datetime
import logging
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_change

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensor."""
    async_add_entities([TouristTaxSensor(hass, config_entry)])

class TouristTaxSensor(Entity):
    def __init__(self, hass, config_entry):
        self.hass = hass
        self._config = config_entry.data
        self._state = 0
        self._days = {}
        self._unsub_time = None
        self._schedule_daily_update()

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
            'update_time': self.hass.states.get("input_datetime.tourist_tax_update_time").state
        }

    def _schedule_daily_update(self):
        """Schedule daily update using input_datetime."""
        if self._unsub_time:
            self._unsub_time()

        time_state = self.hass.states.get("input_datetime.tourist_tax_update_time")
        if not time_state:
            _LOGGER.error("Input datetime not found!")
            return

        hour = int(time_state.attributes['hour'])
        minute = int(time_state.attributes['minute'])

        self._unsub_time = async_track_time_change(
            self.hass,
            self._update_daily,
            hour=hour,
            minute=minute
        )
        _LOGGER.debug(f"Scheduled daily update at {hour}:{minute}")

    async def _update_daily(self, now):
        """Execute daily update."""
        _LOGGER.debug("Running daily update")
        zone = self._config.get('home_zone', 'zone.home')
        persons = [
            e for e in self.hass.states.async_entity_ids("person") 
            if self.hass.states.get(e).state == zone
        ]
        
        day_name = now.strftime("%A %d %b")
        self._days[day_name] = len(persons)
        self._state = sum(self._days.values()) * self._config.get('price_per_person', 2.40)
        self.async_write_ha_state()