from datetime import datetime
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change
from .const import *


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensor from a config entry."""
    sensor = TouristTaxSensor(hass, config_entry)
    async_add_entities([sensor], True)

    # Register service
    async def handle_update_guests(call):
        """Handle the service call to update guests."""
        await sensor.async_update_guests(call.data.get(ATTR_GUESTS, 0))

    hass.services.async_register(
        DOMAIN, SERVICE_UPDATE_GUESTS, handle_update_guests
    )


class TouristTaxSensor(Entity):
    def __init__(self, hass, config_entry):
        self._hass = hass
        self._config_entry = config_entry
        self._state = None
        self._attributes = {
            ATTR_DAYS: {},
            ATTR_GUESTS: 0
        }
        self._unsub_track = None

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        self._unsub_track = async_track_state_change(
            self.hass, "person", self._async_person_changed
        )
        # Schedule daily update at 23:00
        self.hass.helpers.event.async_track_time_change(
            self._async_daily_update, hour=23, minute=0, second=0
        )

    async def async_will_remove_from_hass(self):
        """Run when entity will be removed."""
        if self._unsub_track:
            self._unsub_track()

    async def _async_person_changed(self, entity_id, old_state, new_state):
        """Handle person state changes."""
        await self.async_update_ha(True)

    async def async_update_guests(self, guests):
        """Update the number of guests."""
        self._attributes[ATTR_GUESTS] = int(guests)
        await self.async_update_ha(True)

    async def _async_daily_update(self, now):
        """Record daily count at 23:00."""
        home_zone = self._config_entry.data[CONF_HOME_ZONE]
        persons = [e for e in self.hass.states.async_entity_ids("person")
                   if self.hass.states.get(e).state == home_zone]
        guests = self._attributes[ATTR_GUESTS]

        day_name = now.strftime("%A %d %b")
        self._attributes[ATTR_DAYS][day_name] = len(persons) + guests
        await self.async_update_ha(True)

    async def async_update(self):
        """Calculate total tax."""
        price = self._config_entry.data[CONF_PRICE_PER_PERSON]
        total_people = sum(self._attributes[ATTR_DAYS].values())
        self._state = round(total_people * price, 2)