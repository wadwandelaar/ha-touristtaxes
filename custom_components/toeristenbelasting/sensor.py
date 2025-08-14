import json
import os
from datetime import datetime
import logging
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from datetime import timedelta
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_FILE = "touristtaxes_data.json"

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensor from a config entry."""
    sensor = TouristTaxSensor(hass, config_entry)
    async_add_entities([sensor])

    hass.data[DOMAIN] = sensor

    await sensor.async_schedule_update()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, sensor.save_data)

    return True

class TouristTaxSensor(Entity):
    def __init__(self, hass, config_entry):
        self.hass = hass
        self._config = config_entry.data
        self._state = 0.0
        self._days = {}
        self._unsub_interval = None
        self._data_file = os.path.join(hass.config.path(), DATA_FILE)
        self._last_update = None

        self.load_data()

    def load_data(self):
        try:
            if os.path.exists(self._data_file):
                with open(self._data_file, "r") as f:
                    data = json.load(f)
                self._days = data.get("days", {})
                self._state = data.get("total", 0.0)
                _LOGGER.debug(f"TouristTaxes: Loaded data from {self._data_file}")
        except Exception as e:
            _LOGGER.error(f"TouristTaxes: Failed to load data: {e}")

    def save_data(self, event=None):
        try:
            data = {
                "days": self._days,
                "total": self._state,
            }
            with open(self._data_file, "w") as f:
                json.dump(data, f)
            _LOGGER.debug(f"TouristTaxes: Saved data to {self._data_file}")
        except Exception as e:
            _LOGGER.error(f"TouristTaxes: Failed to save data: {e}")

    async def async_schedule_update(self):
        """Schedule a periodic check every minute."""
        if self._unsub_interval:
            self._unsub_interval()

        self._unsub_interval = async_track_time_interval(
            self.hass, self._check_and_update, timedelta(minutes=1)
        )
        _LOGGER.debug("TouristTaxes: Scheduled minute-based update check")

    async def _check_and_update(self, now):
        """Check if it's the correct time to update and do it once per day."""
        try:
            time_state = self.hass.states.get("input_datetime.tourist_tax_update_time")
            if not time_state:
                _LOGGER.warning("TouristTaxes: input_datetime.tourist_tax_update_time not found")
                return

            target_hour = int(time_state.attributes.get("hour", 23))
            target_minute = int(time_state.attributes.get("minute", 0))

            if now.hour == target_hour and now.minute == target_minute:
                today = now.strftime("%Y-%m-%d")
                if self._last_update != today:
                    _LOGGER.debug("TouristTaxes: Triggered scheduled daily update")
                    await self._update_daily(now)
                    self._last_update = today
        except Exception as e:
            _LOGGER.error(f"TouristTaxes: Error in scheduled update check: {e}")

    async def _update_daily(self, now=None):
        try:
            now = now or datetime.now()
            zone_entity_id = self._config.get('home_zone', 'zone.home')
            zone = self.hass.states.get(zone_entity_id)
            if not zone:
                _LOGGER.error(f"TouristTaxes: Zone {zone_entity_id} not found")
                return

            zone_id = zone_entity_id.split(".")[-1].lower()

            person_entities = self.hass.states.async_entity_ids("person")
            persons_in_zone = [
                e for e in person_entities
                if self.hass.states.get(e).state.lower() == zone_id
            ]

            guests_state = self.hass.states.get("input_number.tourist_guests")
            guests = 0
            if guests_state and guests_state.state not in ("unknown", "unavailable"):
                try:
                    guests = int(float(guests_state.state))
                except ValueError:
                    _LOGGER.warning("TouristTaxes: Invalid value in input_number.tourist_guests")

            total_persons = len(persons_in_zone) + guests

            day_name = now.strftime("%A %d %b")
            self._days[day_name] = total_persons

            self._state = round(
                sum(self._days.values()) * self._config['price_per_person'],
                2
            )

            self.async_write_ha_state()

            _LOGGER.info(f"TouristTaxes: Updated {day_name} - {total_persons} persons (incl. {guests} guests) -> €{self._state}")

            self.save_data()

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
            'next_update_scheduled': self._unsub_interval is not None
        }

    async def reset_data(self):
        self._days = {}
        self._state = 0.0
        self._last_update = None
        self.async_write_ha_state()
        self.save_data()
        _LOGGER.info("TouristTaxes: Data has been reset to 0.")
