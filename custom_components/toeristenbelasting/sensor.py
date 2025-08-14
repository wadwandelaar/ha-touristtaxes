from datetime import datetime
import logging
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_change

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensor."""
    _LOGGER.debug("Setting up tourist taxes sensor")  # Debug toegevoegd
    sensor = TouristTaxSensor(hass, config_entry)
    async_add_entities([sensor], True)
    _LOGGER.debug(f"Sensor created: {sensor.entity_id}")  # Debug toegevoegd

class TouristTaxSensor(Entity):
    def __init__(self, hass, config_entry):
        self.hass = hass
        self._config = config_entry.data
        self._state = 0.0
        self._days = {}
        self._unsub_time = None
        self._schedule_daily_update()
        _LOGGER.debug(f"Initialized with config: {self._config}")  # Debug toegevoegd

    # ... (andere properties blijven hetzelfde)

    async def _update_daily(self, now):
        """Execute daily update with debug logging."""
        _LOGGER.debug("Starting daily update")  # Debug toegevoegd
        
        try:
            zone = self._config['home_zone']
            persons = [
                e for e in self.hass.states.async_entity_ids("person") 
                if self.hass.states.get(e).state == zone
            ]
            _LOGGER.debug(f"Found {len(persons)} persons in zone {zone}")  # Debug toegevoegd
            
            day_name = now.strftime("%A %d %b")
            self._days[day_name] = len(persons)
            self._state = round(sum(self._days.values()) * self._config['price_per_person'], 2)
            
            _LOGGER.debug(f"New state: {self._state}, Days: {self._days}")  # Debug toegevoegd
            self.async_write_ha_state()
            
        except Exception as e:
            _LOGGER.error(f"Update error: {str(e)}")  # Foutlogging toegevoegd