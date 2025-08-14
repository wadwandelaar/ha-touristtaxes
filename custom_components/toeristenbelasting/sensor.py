from datetime import datetime
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_change

async def async_setup_entry(hass, config_entry, async_add_entities):
    async_add_entities([TouristTaxSensor(hass, config_entry)])

class TouristTaxSensor(Entity):
    def __init__(self, hass, config_entry):
        self.hass = hass
        self._config = config_entry.data
        self._state = 0
        self._guests = 0
        self._days = {}
        
        # Start daily updates at 23:00
        async_track_time_change(
            hass, 
            self._update_daily, 
            hour=23, 
            minute=0
        )

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
            'guests': self._guests,
            'price_per_person': self._config['price_per_person']
        }

    async def _update_daily(self, now):
        """Update counts daily at 23:00"""
        persons = [
            e for e in self.hass.states.async_entity_ids("person") 
            if self.hass.states.get(e).state == self._config['home_zone']
        ]
        
        day_name = now.strftime("%A %d %b")
        self._days[day_name] = len(persons) + self._guests
        self._state = sum(self._days.values()) * self._config['price_per_person']
        self.async_write_ha_state()

    async def update_guests(self, guests):
        """Public method to update guests"""
        self._guests = guests
        await self._update_daily(datetime.now())