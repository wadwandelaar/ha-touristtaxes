import json
import os
import logging
from datetime import datetime, timedelta
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
        self._last_save = None

    async def async_added_to_hass(self):
        await self._load_with_retry()
        await self.async_schedule_update()

    async def _load_with_retry(self, retries=3):
        for attempt in range(retries):
            try:
                await self.async_load_data()
                self._load_attempted = True
                _LOGGER.info(f"Data loaded successfully (attempt {attempt + 1})")
                if self._days:
                    await self.async_write_ha_state()
                return
            except Exception as e:
                _LOGGER.warning(f"Load attempt {attempt + 1} failed: {str(e)}")
                if attempt == retries - 1:
                    _LOGGER.error("All data load attempts failed, keeping empty dataset")
                    self._days = {}
                    self._state = 0.0

    async def async_load_data(self):
        def _read_and_validate():
            if not os.path.exists(self._data_file):
                raise FileNotFoundError("Data file not found")
            with open(self._data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Invalid data format: not a dictionary")
            if "days" not in data or "total" not in data:
                raise ValueError("Missing required fields in JSON")
            return data

        try:
            data = await self.hass.async_add_executor_job(_read_and_validate)
            self._days = data.get("days", {})
            self._state = round(sum(
                day.get("amount", 0) 
                for day in self._days.values()
            ), 2)
            _LOGGER.debug(f"Loaded {len(self._days)} days, recalculated total: €{self._state}")
        except FileNotFoundError:
            _LOGGER.info("No data file found, keeping empty dataset")
            self._days = {}
            self._state = 0.0
        except Exception as e:
            _LOGGER.error(f"Failed to load data: {str(e)}")
            raise

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
            _LOGGER.debug("=== DAILY UPDATE STARTED ===")

            if not (3 <= now.month <= 11):
                _LOGGER.debug("Skipping update outside tourist season")
                return

            zone = self._config.get("home_zone", "zone.home").split(".")[-1].lower()
            if zone != "camping":
                _LOGGER.debug(f"Skipping update, not in camping zone (current zone: {zone})")
                return

            persons = [
                e for e in self.hass.states.async_entity_ids("person")
                if self.hass.states.get(e).state.lower() == zone
            ]

            guests_state = self.hass.states.get("input_number.tourist_guests")
            guests_raw = guests_state.state if guests_state else None
            _LOGGER.debug(f"Guest sensor state: {guests_raw} (type: {type(guests_raw)})")

            if not guests_raw or guests_raw in ("unknown", "unavailable", "0", "0.0"):
                guests = 0
            else:
                try:
                    guests = int(float(guests_raw))
                except ValueError:
                    _LOGGER.warning(f"Unexpected guest value: {guests_raw}")
                    guests = 0

            day_key = now.strftime("%Y-%m-%d")
            total_present = len(persons) + guests

            if total_present == 0:
                if day_key in self._days:
                    del self._days[day_key]
                    self._state = round(sum(d["amount"] for d in self._days.values()), 2)
                    await self.async_write_ha_state()
                    _LOGGER.info(f"Removed empty day: {day_key}")
                else:
                    _LOGGER.info("Skipping registration: no persons and no guests (hard check)")
                return

            day_data = {
                "date": now.strftime("%A %d %B %Y"),
                "persons_in_zone": len(persons),
                "guests": guests,
                "total_persons": total_present,
                "amount": round(total_present * self._config["price_per_person"], 2)
            }

            self._days[day_key] = day_data
            self._state = round(sum(d["amount"] for d in self._days.values()), 2)

            await self.async_write_ha_state()
            _LOGGER.info(
                f"Updated {day_key}: Residents: {len(persons)}, Guests: {guests}, "
                f"Amount: €{day_data['amount']}"
            )
        except Exception as e:
            _LOGGER.error(f"Daily update failed: {str(e)}")
            import traceback
            _LOGGER.error(f"Traceback: {traceback.format_exc()}")

    async def async_save_data(self, event=None):
        now = datetime.now()
        if self._last_save and (now - self._last_save).total_seconds() < 30:
            _LOGGER.debug("Skipping save - too frequent")
            return
        self._last_save = now

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

    async def async_write_ha_state(self):
        total_people = sum(day.get("persons_in_zone", 0) + day.get("guests", 0) 
                          for day in self._days.values())
        if total_people > 0 or len(self._days) > 0:
            await super().async_write_ha_state()
            await self.async_save_data()
            _LOGGER.debug(f"State updated: {len(self._days)} days, €{self._state}")
        else:
            _LOGGER.debug("No people and no existing data, skipping state update and save")

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
            except (ValueError, KeyError) as e:
                _LOGGER.warning(f"Error processing day {day_key}: {str(e)}")
                continue

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

async def async_setup_entry(hass, config_entry, async_add_entities):
    sensor = TouristTaxSensor(hass, config_entry)
    async_add_entities([sensor])
    hass.data[DOMAIN] = sensor

    async def handle_reload(call):
        await sensor._load_with_retry()
        _LOGGER.info("Manual reload completed")

    hass.services.async_register(DOMAIN, "reload_data", handle_reload)

    async def handle_time_change(event):
        if event.data.get("entity_id") == "input_datetime.tourist_tax_update_time":
            _LOGGER.debug("Detected time change, rescheduling")
            await sensor.async_schedule_update()

    hass.bus.async_listen("state_changed", handle_time_change)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, sensor.async_save_data)

    return True
