from datetime import datetime
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.event import async_track_time_change

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([TouristTaxSensor(hass, entry)])

class TouristTaxSensor(SensorEntity):
    _attr_name = "Tourist Taxes"
    _attr_icon = "mdi:cash-euro"

    def __init__(self, hass, config_entry):
        self.hass = hass
        self._config = config_entry.data
        self._attr_native_value = 0
        self._guests = 0
        self._days = {}
        
        # Start dagelijkse update om 23:00
        async_track_time_change(
            hass, 
            self._update_daily, 
            hour=23, 
            minute=0
        )

    @property
    def extra_state_attributes(self):
        return {
            'days': self._days,
            'guests': self._guests,
            'price': self._config['price_per_person']
        }

    async def _update_daily(self, now):
        """Dagelijkse update"""
        persons = [
            e for e in self.hass.states.async_entity_ids("person") 
            if self.hass.states.get(e).state == self._config['home_zone']
        ]
        
        self._days[now.strftime("%A %d %b")] = len(persons) + self._guests
        self._attr_native_value = round(sum(self._days.values()) * self._config['price_per_person'], 2)
        self.async_write_ha_state()

    async def _schedule_daily_update(self):
        """Lees tijd uit input_datetime"""
        time_str = self.hass.states.get("input_datetime.tourist_tax_update_time").state
        hour, minute, _ = map(int, time_str.split(":"))
        
        self._unsub_time = async_track_time_change(
            self.hass,
            self._update_daily,
            hour=hour,
            minute=minute
        )
        
        # Update attributen
        self._attr_extra_state_attributes["update_time"] = f"{hour:02d}:{minute:02d}"