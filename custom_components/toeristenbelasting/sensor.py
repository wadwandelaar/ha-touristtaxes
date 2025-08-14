from datetime import datetime
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_change

class TouristTaxSensor(Entity):
    def __init__(self, hass, config_entry):
        self.hass = hass
        self._config = config_entry.data
        self._state = 0
        self._guests = 0
        self._days = {}

        # Stel dagelijkse update in
        async_track_time_change(
            hass,
            self._update_daily,
            hour=self._config.get('update_hour', 23),
            minute=self._config.get('update_minute', 0)
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
            'price': self._config.get('price_per_person', 2.40)
        }

    async def _update_daily(self, now):
        """Dagelijkse update om ingestelde tijd"""
        zone = self._config.get('home_zone', 'zone.home')
        persons = [e for e in self.hass.states.async_entity_ids('person')
                  if self.hass.states.get(e).state == zone]

        datum = now.strftime("%A %d %b")
        self._days[datum] = len(persons) + self._guests

        # Bereken totaal
        self._state = sum(self._days.values()) * self._config.get('price_per_person', 2.40)
        self.async_write_ha_state()

    async def update_guests(self, guests):
        """Update aantal logés"""
        self._guests = guests
        await self._update_daily(datetime.now())