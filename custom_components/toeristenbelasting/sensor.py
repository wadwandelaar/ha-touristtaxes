import json
import os
import logging
from datetime import datetime
from collections import defaultdict
from functools import partial

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_change
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
DATA_FILE = "/config/touristtaxes_data.json"

class TouristTaxSensor(Entity):
    def __init__(self, hass, config_entry):
        self.hass = hass
        self._config = config_entry.data
        self._state = 0.0
        self._days = {}
        self._unsub_time = None
        self._data_file = DATA_FILE
        self._setup_complete = False

    async def async_added_to_hass(self):
        """Run when entity is added to HA."""
        await self.async_load_data()
        await self.async_schedule_update()
        self._setup_complete = True

    async def async_load_data(self):
        """Thread-safe data loading."""
        def _read_data():
            if os.path.exists(self._data_file):
                with open(self._data_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            return {"days": {}, "total": 0.0}

        try:
            data = await self.hass.async_add_executor_job(_read_data)
            self._days = data.get("days", {})
            self._state = data.get("total", 0.0)
            _LOGGER.info(f"Loaded {len(self._days)} days, total €{self._state}")
        except Exception as e:
            _LOGGER.error(f"Error loading data: {e}")

    async def async_schedule_update(self, *args):
        """Schedule or reschedule the daily update."""
        if self._unsub_time:
            self._unsub_time()
            self._unsub_time = None

        time_state = self.hass.states.get("input_datetime.tourist_tax_update_time")
        if not time_state:
            _LOGGER.warning("Time input not found, retrying in 30s")
            self.hass.loop.call_later(30, self._reschedule)
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
            _LOGGER.error(f"Scheduling error: {e}")
            self.hass.loop.call_later(30, self._reschedule)

    def _reschedule(self):
        """Helper to reschedule update."""
        self.hass.async_create_task(self.async_schedule_update())

    async def _update_daily(self, now=None):
        """Execute the daily update."""
        try:
            now = now or datetime.now()
            if not (3 <= now.month <= 11):
                _LOGGER.debug("Outside tourist season")
                return

            zone = self._config.get("home_zone", "zone.home").split(".")[-1]
            persons = [e for e in self.hass.states.async_entity_ids("person") 
                      if self.hass.states.get(e).state.lower() == zone]
            
            guests_state = self.hass.states.get("input_number.tourist_guests")
            guests = int(float(guests_state.state)) if guests_state else 0

            day_data = {
                "date": now.strftime("%A %d %B %Y"),
                "persons_in_zone": len(persons),
                "guests": guests,
                "total_persons": len(persons) + guests,
                "amount": round((len(persons) + guests) * self._config["price_per_person"], 2)
            }

            self._days[now.strftime("%Y-%m-%d")] = day_data
            self._state = round(sum(d["amount"] for d in self._days.values()), 2)
            
            self.async_write_ha_state()
            await self.async_save_data()
            _LOGGER.info(f"Updated: {day_data}")
        except Exception as e:
            _LOGGER.error(f"Update failed: {e}")

    async def async_save_data(self, event=None):
        """Thread-safe data saving."""
        def _write():
            temp_file = f"{self._data_file}.tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump({
                    "days": self._days,
                    "total": self._state,
                    "last_updated": datetime.now().isoformat()
                }, f, indent=2)
            os.replace(temp_file, self._data_file)

        try:
            await self.hass.async_add_executor_job(_write)
        except Exception as e:
            _LOGGER.error(f"Save failed: {e}")

    @property
    def name(self):
        return "Tourist Taxes"

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        monthly = defaultdict(lambda: {"days": 0, "persons": 0, "amount": 0.0})
        for date_str, data in self._days.items():
            try:
                month = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m")
                monthly[month]["days"] += 1
                monthly[month]["persons"] += data["total_persons"]
                monthly[month]["amount"] += data["amount"]
            except (ValueError, KeyError):
                continue

        return {
            "price_per_person": self._config["price_per_person"],
            "monthly": dict(sorted(monthly.items(), reverse=True)),
            "next_update": self._unsub_time is not None
        }

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensor."""
    sensor = TouristTaxSensor(hass, config_entry)
    async_add_entities([sensor])
    hass.data[DOMAIN] = sensor

    async def handle_reload(call):
        await sensor.async_load_data()
        sensor.async_write_ha_state()
        _LOGGER.info("Manual reload completed")

    hass.services.async_register(DOMAIN, "reload_data", handle_reload)
    hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, sensor.async_save_data)
    
    # Listen for time changes
    async def time_updated(event):
        if event.data.get("entity_id") == "input_datetime.tourist_tax_update_time":
            await sensor.async_schedule_update()

    hass.bus.async_listen("state_changed", time_updated)
    
    return True