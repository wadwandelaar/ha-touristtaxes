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
DATA_FILE = "/config/touristtaxes_data.json"  # Pas aan indien nodig

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Setup sensor en registreer reload + automatische herplanning."""
    sensor = TouristTaxSensor(hass, config_entry)
    await sensor.async_load_data()
    async_add_entities([sensor])
    hass.data[DOMAIN] = sensor

    # Service om handmatig data te herladen
    async def handle_reload(call):
        await sensor.async_load_data()
        sensor.async_write_ha_state()
        _LOGGER.info("Handmatige herlading van touristtaxes data voltooid")

    hass.services.async_register(DOMAIN, "reload_data", handle_reload)

    # Eerste planning op basis van input_datetime
    await sensor.async_schedule_update()

    # Herplan automatisch bij wijziging van input_datetime
    hass.bus.async_listen("state_changed", lambda event: hass.async_create_task(sensor.async_schedule_update()))

    # Opslaan bij afsluiten
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, sensor.async_save_data)
    return True

class TouristTaxSensor(Entity):
    def __init__(self, hass, config_entry):
        self.hass = hass
        self._config = config_entry.data
        self._state = 0.0
        self._days = {}
        self._unsub_time = None
        self._data_file = DATA_FILE

    async def async_load_data(self):
        """Laad JSON-data en merge handmatige invoer."""
        def _read_data():
            if os.path.exists(self._data_file):
                with open(self._data_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            return {"days": {}, "total": 0.0}

        try:
            data = await self.hass.async_add_executor_job(_read_data)
            merged_days = {**data.get("days", {}), **self._days}
            self._days = merged_days

            self._state = round(sum(
                day.get("amount", 0) for day in self._days.values()
                if self._is_date_in_season(day.get("date", ""))
            ), 2)

            _LOGGER.debug(f"Data geladen: {len(self._days)} dagen, totaal €{self._state}")
        except Exception as e:
            _LOGGER.error(f"Fout bij laden van data: {e}")

    async def async_save_data(self, event=None):
        """Sla JSON-data veilig op."""
        try:
            data = {
                "days": {k: v for k, v in self._days.items()
                         if self._is_date_in_season(v.get("date", ""))},
                "total": self._state,
                "last_updated": datetime.now().isoformat()
            }
            await self.hass.async_add_executor_job(self._write_data_sync, data)
            _LOGGER.debug(f"Data opgeslagen naar {self._data_file}")
        except Exception as e:
            _LOGGER.error(f"Opslaan mislukt: {e}")

    def _write_data_sync(self, data):
        temp_file = f"{self._data_file}.tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(temp_file, self._data_file)

    async def async_schedule_update(self):
        """Plan dagelijkse update op tijd uit input_datetime."""
        if self._unsub_time:
            self._unsub_time()
            self._unsub_time = None

        time_state = self.hass.states.get("input_datetime.tourist_tax_update_time")
        if not time_state:
            _LOGGER.warning("Geen input_datetime.tourist_tax_update_time gevonden. Herprobeer over 30 sec.")
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
            _LOGGER.info(f"Dagelijkse update gepland om {hour:02d}:{minute:02d}")
        except Exception as e:
            _LOGGER.error(f"Fout bij plannen van update: {e}")

    async def _update_daily(self, now=None):
        """Voer dagelijkse update uit op geplande tijd."""
        try:
            now = now or datetime.now()
            if now.month < 3 or now.month > 11:
                _LOGGER.info("Buiten het toeristenseizoen (maart-november). Geen update uitgevoerd.")
                return

            zone_id = self._config.get("home_zone", "zone.home").split(".", 1)[-1].lower()
            persons = [
                e for e in self.hass.states.async_entity_ids("person")
                if self.hass.states.get(e).state.lower() == zone_id
            ]

            guests_state = self.hass.states.get("input_number.tourist_guests")
            guests = int(float(guests_state.state)) if (guests_state and guests_state.state not in ("unknown", "unavailable")) else 0

            total_persons = len(persons) + guests
            day_key = now.strftime("%Y-%m-%d")
            date_display = now.strftime("%A %d %B %Y")

            self._days[day_key] = {
                "date": date_display,
                "persons_in_zone": len(persons),
                "guests": guests,
                "total_persons": total_persons,
                "amount": round(total_persons * self._config["price_per_person"], 2)
            }

            self._state = round(sum(
                day["amount"] for day in self._days.values()
                if self._is_date_in_season(day["date"])
            ), 2)

            self.async_write_ha_state()
            await self.async_save_data()

            _LOGGER.info(
                f"Update voor {date_display}: {len(persons)} personen + {guests} gasten = "
                f"{total_persons} × €{self._config['price_per_person']} = €{self._days[day_key]['amount']}"
            )
        except Exception as e:
            _LOGGER.error(f"Dagelijkse update mislukt: {e}")

    def _is_date_in_season(self, date_str):
        """Controleer of datum in seizoen (maart-november) valt."""
        try:
            date = datetime.strptime(date_str, "%A %d %B %Y")
            return 3 <= date.month <= 11
        except ValueError:
            return True

    @property
    def name(self):
        return "Tourist Taxes"

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        monthly_data = defaultdict(lambda: {"days": 0, "persons": 0, "amount": 0.0})

        for day_key, day_data in self._days.items():
            try:
                date_obj = datetime.strptime(day_key, "%Y-%m-%d")
                month_key = date_obj.strftime("%Y-%m")
                monthly_data[month_key]["days"] += 1
                monthly_data[month_key]["persons"] += day_data["total_persons"]
                monthly_data[month_key]["amount"] += day_data["amount"]
            except (ValueError, KeyError):
                continue

        return {
            "price_per_person": self._config["price_per_person"],
            "season": "March-November",
            "days": dict(sorted(self._days.items(), reverse=True)),
            "monthly": dict(sorted(monthly_data.items(), reverse=True)),
            "total_days": len(self._days),
            "next_update_scheduled": self._unsub_time is not None,
            "version": "2024.08.1",
            "data_file": self._data_file,
        }

    async def reset_data(self):
        """Reset alle data."""
        self._days = {}
        self._state = 0.0
        self.async_write_ha_state()
        await self.async_save_data()
        _LOGGER.warning("Alle tourist tax data is gereset!")
