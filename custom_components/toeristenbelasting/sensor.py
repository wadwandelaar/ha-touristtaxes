import json
import os
import logging
from datetime import datetime
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_change
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

    async def async_added_to_hass(self):
        await self._load_data()
        await self._schedule_daily_update()

    async def _load_data(self):
        def read_file():
            if not os.path.exists(self._data_file):
                return {"days": {}, "total": 0.0}
            with open(self._data_file, "r", encoding="utf-8") as f:
                return json.load(f)

        try:
            data = await self.hass.async_add_executor_job(read_file)
            self._days = data.get("days", {})
            self._state = round(sum(d.get("amount", 0) for d in self._days.values()), 2)
            _LOGGER.info("Loaded data with %d days, total: %.2f", len(self._days), self._state)
        except Exception as e:
            _LOGGER.warning("Failed to load data, starting fresh: %s", e)
            self._days = {}
            self._state = 0.0

    async def _schedule_daily_update(self):
        if self._unsub_time:
            self._unsub_time()
            self._unsub_time = None

        time_state = self.hass.states.get("input_datetime.tourist_tax_update_time")
        if not time_state:
            _LOGGER.warning("Update time entity input_datetime.tourist_tax_update_time not found")
            # Probeer opnieuw over 30 seconden
            self.hass.loop.call_later(30, lambda: self.hass.async_create_task(self._schedule_daily_update()))
            return

        hour = int(time_state.attributes.get("hour", 23))
        minute = int(time_state.attributes.get("minute", 0))

        self._unsub_time = async_track_time_change(
            self.hass,
            self._daily_update,
            hour=hour,
            minute=minute,
            second=0
        )
        _LOGGER.info("Scheduled daily update at %02d:%02d", hour, minute)

    async def _daily_update(self, now=None):
        now = now or datetime.now()
        day_key = now.strftime("%Y-%m-%d")

        # Alleen in seizoen maart t/m november
        if not (3 <= now.month <= 11):
            _LOGGER.debug("Outside season, skipping update")
            return

        target_zone = "zone.camping"
        persons_in_zone = [
            entity_id for entity_id in self.hass.states.async_entity_ids("person")
            if (state := self.hass.states.get(entity_id)) and state.state.lower() == target_zone.lower()
        ]

        if not persons_in_zone:
            _LOGGER.debug("No persons in zone %s on %s, skipping write", target_zone, day_key)
            return

        guests_state = self.hass.states.get("input_number.tourist_guests")
        guests = int(float(guests_state.state)) if guests_state and guests_state.state not in ("unknown", "unavailable") else 0

        total_persons = len(persons_in_zone) + guests
        if total_persons == 0:
            _LOGGER.debug("No guests or persons to record for %s", day_key)
            return

        amount = round(total_persons * self._config.get("price_per_person", 2.40), 2)

        day_data = {
            "date": now.strftime("%A %d %B %Y"),
            "persons_in_zone": len(persons_in_zone),
            "guests": guests,
            "total_persons": total_persons,
            "amount": amount
        }

        self._days[day_key] = day_data
        self._state = round(sum(d["amount"] for d in self._days.values()), 2)

        await self._save_data()
        _LOGGER.info("Recorded tourist tax for %s: %s", day_key, day_data)
        self.async_write_ha_state()

    async def _save_data(self):
        # Als er geen dagen zijn of alle dagen 0 personen, niets opslaan
        if not self._days or all(d.get("total_persons", 0) == 0 for d in self._days.values()):
            _LOGGER.debug("No valid data to save, skipping JSON write")
            return

        def write_file():
            temp_file = f"{self._data_file}.tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump({
                    "days": self._days,
                    "total": self._state,
                    "last_updated": datetime.now().isoformat()
                }, f, indent=2, ensure_ascii=False)
            os.replace(temp_file, self._data_file)

        try:
            await self.hass.async_add_executor_job(write_file)
            _LOGGER.debug("Data saved to %s", self._data_file)
        except Exception as e:
            _LOGGER.error("Failed to save data: %s", e)

    @property
    def name(self):
        return "Tourist Taxes"

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return {
            "price_per_person": self._config.get("price_per_person", 2.40),
            "days_count": len(self._days),
            "days": self._days,
        }
