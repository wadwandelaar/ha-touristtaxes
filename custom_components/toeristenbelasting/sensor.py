import json
import os
import logging
from datetime import datetime
from collections import defaultdict

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
        self._load_attempted = False

    async def async_added_to_hass(self):
        await self._load_with_retry()
        await self.async_schedule_update()

    async def _load_with_retry(self, retries=3):
        for attempt in range(retries):
            try:
                await self.async_load_data()
                self._load_attempted = True
                _LOGGER.info(f"Data loaded successfully (attempt {attempt + 1})")
                self.async_write_ha_state()
                return
            except Exception as e:
                _LOGGER.warning(f"Load attempt {attempt + 1} failed: {str(e)}")
                if attempt == retries - 1:
                    _LOGGER.error("All data load attempts failed, initializing empty dataset")
                    self._days = {}
                    self._state = 0.0
                    self.async_write_ha_state()

    async def async_load_data(self):
        def _read_and_validate():
            if not os.path.exists(self._data_file):
                return {"days": {}, "total": 0.0}
            with open(self._data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Invalid data format")
            if "days" not in data or "total" not in data:
                raise ValueError("Missing required fields in JSON")
            return data

        data = await self.hass.async_add_executor_job(_read_and_validate)
        self._days = data.get("days", {})
        self._state = round(sum(
            day.get("amount", 0) for day in self._days.values()
        ), 2)
        _LOGGER.debug(f"Loaded {len(self._days)} days, recalculated total: €{self._state}")

    async def async_schedule_update(self, *args):
        if self._unsub_time:
            self._unsub_time()
            self._unsub_time = None

        time_state = self.hass.states.get("input_datetime.tourist_tax_update_time")
        if not time_state:
            _LOGGER.warning("Time input entity not found")
            self.hass.loop.call_later(30, lambda: self.hass.async_create_task(self.async_schedule_update()))
            return

        try:
            hour = int(time_state.attributes.get("hour", 23))
            minute = int(time_state.attributes.get("minute", 0))
            self._unsub_time = async_track_time_change(
                self.hass,
                self._perform_daily_update,
                hour=hour,
                minute=minute,
                second=0
            )
            _LOGGER.info(f"Scheduled daily update at {hour:02d}:{minute:02d}")
        except Exception as e:
            _LOGGER.error(f"Scheduling failed: {str(e)}")
            self.hass.loop.call_later(30, lambda: self.hass.async_create_task(self.async_schedule_update()))

    async def _perform_daily_update(self, now=None):
        try:
            now = now or datetime.now()
            day_key = now.strftime("%Y-%m-%d")
            _LOGGER.debug(f"Running tourist tax update for {day_key}")

            # Alleen bijhouden van maart t/m november
            if not (3 <= now.month <= 11):
                _LOGGER.debug("Outside tourist season, skipping update")
                return

            target_zone = "zone.camping"
            persons_in_zone = [
                e for e in self.hass.states.async_entity_ids("person")
                if self.hass.states.get(e) is not None and self.hass.states.get(e).state.lower() == target_zone.lower()
            ]
            _LOGGER.debug(f"Persons in zone '{target_zone}': {persons_in_zone}")

            guests_state = self.hass.states.get("input_number.tourist_guests")
            guests = int(float(guests_state.state)) if guests_state and guests_state.state not in ("unknown", "unavailable") else 0
            _LOGGER.debug(f"Number of guests: {guests}")

            persons_count = len(persons_in_zone)
            total = persons_count + guests

            if total == 0:
                _LOGGER.debug(f"No persons or guests present for {day_key}, skipping data write")
                if day_key in self._days:
                    del self._days[day_key]
                    await self.async_save_data()
                return

            amount = round(total * self._config["price_per_person"], 2)

            day_data = {
                "date": now.strftime("%A %d %B %Y"),
                "persons_in_zone": persons_count,
                "guests": guests,
                "total_persons": total,
                "amount": amount
            }

            self._days[day_key] = day_data
            self._state = round(sum(d["amount"] for d in self._days.values()), 2)

            await self.async_save_data()
            _LOGGER.info(f"Tourist tax recorded for {day_key}: {day_data}")

        except Exception as e:
            _LOGGER.error(f"Daily update failed: {str(e)}", exc_info=True)

    async def async_save_data(self, event=None):
        if not self._days:
            _LOGGER.debug("No data to save: days dictionary is empty")
            if os.path.exists(self._data_file):
                try:
                    os.remove(self._data_file)
                    _LOGGER.info(f"Removed data file {self._data_file} because data is empty")
                except Exception as e:
                    _LOGGER.error(f"Failed to remove empty data file: {str(e)}")
            return

        has_valid_data = any(day_data.get("total_persons", 0) > 0 for day_data in self._days.values())
        if not has_valid_data:
            _LOGGER.debug("No valid data to save: all days have zero persons")
            if os.path.exists(self._data_file):
                try:
                    os.remove(self._data_file)
                    _LOGGER.info(f"Removed data file {self._data_file} because all entries zero")
                except Exception as e:
                    _LOGGER.error(f"Failed to remove empty data file: {str(e)}")
            return

        def _write_data():
            temp_file = f"{self._data_file}.tmp"
            try:
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump({
                        "days": self._days,
                        "total": self._state,
                        "last_updated": datetime.now().isoformat()
                    }, f, indent=2, ensure_ascii=False)
                os.replace(temp_file, self._data_file)
            except Exception as e:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                raise

        try:
            await self.hass.async_add_executor_job(_write_data)
            _LOGGER.debug(f"Data saved to {self._data_file}")
        except Exception as e:
            _LOGGER.error(f"Failed to save data: {str(e)}")

    @property
    def name(self):
        return "Tourist Taxes"

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        monthly = defaultdict(lambda: {"days": 0, "persons": 0, "amount": 0.0})
        season_total = 0

        for day_key, day_data in self._days.items():
            try:
                date_obj = datetime.strptime(day_key, "%Y-%m-%d")
                month_key = date_obj.strftime("%Y-%m")
                monthly[month_key]["days"] += 1
                monthly[month_key]["persons"] += day_data["total_persons"]
                monthly[month_key]["amount"] += day_data["amount"]
                if self._is_in_season(date_obj):
                    season_total += day_data["amount"]
            except Exception as e:
                _LOGGER.warning(f"Error processing day {day_key}: {str(e)}")

        return {
            "price_per_person": self._config["price_per_person"],
            "season": "March-November",
            "days_count": len(self._days),
            "monthly_summary": dict(sorted(monthly.items(), reverse=True)),
            "season_total": round(season_total, 2),
            "data_file": self._data_file,
            "last_day": next(iter(self._days.items())) if self._days else None,
            "days": self._days
        }

    def _is_in_season(self, date_obj):
        return 3 <= date_obj.month <= 11
