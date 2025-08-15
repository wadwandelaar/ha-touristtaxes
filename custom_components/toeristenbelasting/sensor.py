import json
import os
import logging
from datetime import datetime
from functools import partial

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_change
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
DATA_FILE = "touristtaxes_data.json"

async def async_setup_entry(hass, config_entry, async_add_entities):
    sensor = TouristTaxSensor(hass, config_entry)
    async_add_entities([sensor])
    hass.data[DOMAIN] = sensor
    await sensor.load_data()
    await sensor.async_schedule_update()
    
    # Add listener for time changes
    async def handle_time_change(event):
        if event.data.get("entity_id") == "input_datetime.tourist_tax_update_time":
            _LOGGER.debug("Detected change in update time, rescheduling...")
            await sensor.async_schedule_update()
    
    hass.bus.async_listen("state_changed", handle_time_change)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, sensor.save_data)
    return True

class TouristTaxSensor(Entity):
    def __init__(self, hass, config_entry):
        self.hass = hass
        self._config = config_entry.data
        self._state = 0.0
        self._days = {}
        self._unsub_time = None
        self._data_file = os.path.join(hass.config.path(), DATA_FILE)

    async def load_data(self):
        def _read_data():
            if os.path.exists(self._data_file):
                with open(self._data_file, "r") as f:
                    return json.load(f)
            return {}

        try:
            data = await self.hass.async_add_executor_job(_read_data)
            self._days = data.get("days", {})
            self._state = data.get("total", 0.0)
            _LOGGER.debug(f"Loaded data from {self._data_file}")
        except Exception as e:
            _LOGGER.error(f"Failed to load data: {e}")

    def _write_data_sync(self, data):
        with open(self._data_file, "w") as f:
            json.dump(data, f, indent=2)

    async def save_data(self, event=None):
        try:
            data = {
                "days": self._days,
                "total": self._state,
            }
            await self.hass.async_add_executor_job(self._write_data_sync, data)
            _LOGGER.debug(f"Saved data to {self._data_file}")
        except Exception as e:
            _LOGGER.error(f"Failed to save data: {e}")

    async def async_schedule_update(self):
        # Cancel existing timer if any
        if self._unsub_time:
            self._unsub_time()
            self._unsub_time = None

        # Get new time
        time_state = self.hass.states.get("input_datetime.tourist_tax_update_time")
        if not time_state:
            _LOGGER.warning("Update time entity not found. Retrying in 30 seconds.")
            self.hass.loop.call_later(
                30, 
                lambda: self.hass.async_create_task(self.async_schedule_update())
            )
            return

        try:
            hour = int(time_state.attributes.get("hour", 23))
            minute = int(time_state.attributes.get("minute", 0))
            
            self._unsub_time = async_track_time_change(
                self.hass,
                self._update_daily,
                hour=hour,
                minute=minute,
                second=0
            )
            _LOGGER.info(f"Scheduled daily update at {hour:02d}:{minute:02d}")
        except Exception as e:
            _LOGGER.error(f"Failed to schedule update: {e}")
            self.hass.loop.call_later(
                30,
                lambda: self.hass.async_create_task(self.async_schedule_update())
            )

    async def _update_daily(self, now=None):
        try:
            now = now or datetime.now()
            zone_id = self._config.get("home_zone", "zone.home").split(".", 1)[-1].lower()

            persons = [
                e for e in self.hass.states.async_entity_ids("person")
                if self.hass.states.get(e).state.lower() == zone_id
            ]

            guests_state = self.hass.states.get("input_number.tourist_guests")
            guests = int(float(guests_state.state)) if (
                guests_state and guests_state.state not in ("unknown", "unavailable")
            ) else 0

            total_persons = len(persons) + guests
            day_key = now.strftime("%A %d %b")

            self._days[day_key] = {
                "persons_in_zone": len(persons),
                "guests": guests,
                "total": total_persons
            }

            self._state = round(
                sum(d["total"] for d in self._days.values()) * self._config["price_per_person"], 2
            )

            self.async_write_ha_state()
            await self.save_data()

            _LOGGER.info(
                f"Updated {day_key} → "
                f"zone: {len(persons)}, guests: {guests}, "
                f"total: {total_persons}, €{self._state}"
            )
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
            "days": self._days,
            "price_per_person": self._config["price_per_person"],
            "next_update_scheduled": self._unsub_time is not None
        }

    async def reset_data(self):
        self._days = {}
        self._state = 0.0
        self.async_write_ha_state()
        await self.save_data()
        _LOGGER.info("Data reset to empty.")