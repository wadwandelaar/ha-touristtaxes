"""Sensor platform for Tourist Taxes."""
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

# ONLY these zones will trigger updates
ALLOWED_ZONES = ["zone.camping"]  # Voeg andere zones toe indien nodig

class TouristTaxSensor(Entity):
    def __init__(self, hass, config_entry):
        self.hass = hass
        self._config = config_entry.data
        self._state = 0.0
        self._days = {}
        self._unsub_time = None
        self._data_file = DATA_FILE
        self._load_attempted = False
        self._entry_id = config_entry.entry_id

    @property
    def unique_id(self):
        return f"tourist_taxes_{self._entry_id}"

    async def async_added_to_hass(self):
        await self._load_with_retry()
        await self.async_schedule_update()

        async def handle_force_update(call):
            await self._perform_daily_update(datetime.now())
            _LOGGER.info("Manual update triggered via service")

        async def handle_reset_data(call):
            await self.reset_data()
            _LOGGER.info("Data reset triggered via service")

        async def handle_debug_zones(call):
            zone_entity_id = self._config.get("home_zone", "zone.camping")
            
            _LOGGER.info(f"🔍 Debug Zone Info:")
            _LOGGER.info(f"Target Zone: {zone_entity_id}")
            _LOGGER.info(f"Allowed Zones: {ALLOWED_ZONES}")
            _LOGGER.info(f"Is target zone allowed: {zone_entity_id in ALLOWED_ZONES}")
            
            # Check all persons
            for entity_id in self.hass.states.async_entity_ids("person"):
                person_state = self.hass.states.get(entity_id)
                if not person_state:
                    continue
                
                person_zone = person_state.attributes.get('zone', 'unknown')
                _LOGGER.info(f"Person {entity_id}: state={person_state.state}, zone={person_zone}")

        self.hass.services.async_register(DOMAIN, "force_update", handle_force_update)
        self.hass.services.async_register(DOMAIN, "reset_data", handle_reset_data)
        self.hass.services.async_register(DOMAIN, "debug_zones", handle_debug_zones)

    def _should_update(self, zone_entity_id):
        """Check if we should update based on zone and person states."""
        # Only update if the target zone is in our allowed list
        if zone_entity_id not in ALLOWED_ZONES:
            _LOGGER.info(f"🛑 Zone {zone_entity_id} is not in allowed list: {ALLOWED_ZONES}")
            return False
        
        # Check if any person is in the allowed zone
        for entity_id in self.hass.states.async_entity_ids("person"):
            person_state = self.hass.states.get(entity_id)
            if not person_state:
                continue
                
            person_zone = person_state.attributes.get('zone')
            if person_zone in ALLOWED_ZONES:
                _LOGGER.info(f"✅ Person {entity_id} is in allowed zone: {person_zone}")
                return True
        
        # Check guests
        guests_state = self.hass.states.get("input_number.tourist_guests")
        guests = 0
        if guests_state and guests_state.state not in ("unknown", "unavailable"):
            try:
                guests = int(float(guests_state.state))
                if guests > 0:
                    _LOGGER.info(f"✅ Guests present: {guests}")
                    return True
            except (ValueError, TypeError):
                pass
        
        _LOGGER.info("🛑 No persons in allowed zones and no guests")
        return False

    async def reset_data(self):
        self._days = {}
        self._state = 0.0
        self.async_write_ha_state()
        await self.async_save_data()
        _LOGGER.info("All data has been reset")

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
                raise ValueError("Invalid data format: not a dictionary")
            if "days" not in data or "total" not in data:
                raise ValueError("Missing required fields in JSON")
            return data

        data = await self.hass.async_add_executor_job(_read_and_validate)
        self._days = data.get("days", {})
        self._state = round(sum(
            day.get("amount", 0)
            for day in self._days.values()
        ), 2)
        _LOGGER.debug(f"Loaded {len(self._days)} days, recalculated total: €{self._state}")

    async def async_schedule_update(self, *args):
        if self._unsub_time:
            self._unsub_time()
            self._unsub_time = None

        time_state = self.hass.states.get("input_datetime.tourist_tax_update_time")
        if not time_state:
            _LOGGER.warning("⏰ 'input_datetime.tourist_tax_update_time' not found. Will retry in 30 seconds.")
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
            _LOGGER.info(f"🗓 Update scheduled daily at {hour:02d}:{minute:02d}")
        except Exception as e:
            _LOGGER.error(f"Scheduling failed: {str(e)}")
            self.hass.loop.call_later(30, lambda: self.hass.async_create_task(self.async_schedule_update()))

    async def _perform_daily_update(self, now=None):
        try:
            now = now or datetime.now()

            if not (3 <= now.month <= 11):
                _LOGGER.debug("📆 Skipping update outside tourist season")
                return

            zone_entity_id = self._config.get("home_zone", "zone.camping")
            
            # STRICT CHECK: Only update if conditions are met
            if not self._should_update(zone_entity_id):
                _LOGGER.info(f"🛑 Update conditions not met for {zone_entity_id}")
                return

            # Get guests count
            guests_state = self.hass.states.get("input_number.tourist_guests")
            guests = 0
            if guests_state and guests_state.state not in ("unknown", "unavailable"):
                try:
                    guests = int(float(guests_state.state))
                except (ValueError, TypeError):
                    guests = 0
                    _LOGGER.warning("Ongeldige waarde voor gasten")

            # Count persons in allowed zones
            persons_in_allowed_zones = 0
            for entity_id in self.hass.states.async_entity_ids("person"):
                person_state = self.hass.states.get(entity_id)
                if not person_state:
                    continue
                    
                person_zone = person_state.attributes.get('zone')
                if person_zone in ALLOWED_ZONES:
                    persons_in_allowed_zones += 1

            day_key = now.strftime("%Y-%m-%d")
            day_data = {
                "date": now.strftime("%A %d %B %Y"),
                "persons_in_zone": persons_in_allowed_zones,
                "guests": guests,
                "total_persons": persons_in_allowed_zones + guests,
                "amount": round((persons_in_allowed_zones + guests) * self._config["price_per_person"], 2)
            }

            # Only add entry if there's actually something to record
            if day_data["total_persons"] > 0:
                self._days[day_key] = day_data
                self._state = round(sum(d["amount"] for d in self._days.values()), 2)
                self.async_write_ha_state()
                await self.async_save_data()

                _LOGGER.info(
                    f"✅ Updated {day_key}: Personen in allowed zones: {persons_in_allowed_zones}, "
                    f"Guests: {guests}, Total: {day_data['total_persons']}, Amount: €{day_data['amount']}"
                )
            else:
                _LOGGER.info(f"📝 Geen personen of gasten gevonden ondanks positieve check")

        except Exception as e:
            _LOGGER.error(f"❌ Daily update failed: {str(e)}")

    async def async_save_data(self, event=None):
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
    def unit_of_measurement(self):
        return "€"

    @property
    def icon(self):
        return "mdi:cash"

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
            "allowed_zones": ALLOWED_ZONES
        }

    def _is_in_season(self, date_obj):
        return 3 <= date_obj.month <= 11

async def async_setup_entry(hass, config_entry, async_add_entities):
    sensor = TouristTaxSensor(hass, config_entry)
    async_add_entities([sensor])

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = sensor

    async def handle_reload(call):
        await sensor._load_with_retry()
        _LOGGER.info("Manual reload completed")

    hass.services.async_register(DOMAIN, "reload_data", handle_reload)

    async def handle_time_change(event):
        entity = event.data.get("entity_id")
        if isinstance(entity, str) and entity == "input_datetime.tourist_tax_update_time":
            _LOGGER.warning("🕒 Time change detected, rescheduling daily update")
            await sensor.async_schedule_update()

    hass.bus.async_listen("state_changed", handle_time_change)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, sensor.async_save_data)

    return True