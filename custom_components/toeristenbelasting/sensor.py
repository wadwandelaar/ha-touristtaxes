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
DATA_FILE = "/config/touristtaxes_data.json"  # Expliciet pad voor HassOS

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Setup met integratie herlaadondersteuning."""
    sensor = TouristTaxSensor(hass, config_entry)
    await sensor.async_load_data()
    async_add_entities([sensor])
    hass.data[DOMAIN] = sensor

    # Herlaad-logica
    async def handle_reload(call):
        await sensor.async_load_data()
        _LOGGER.info("Handmatige herlading voltooid")

    hass.services.async_register(DOMAIN, "reload_data", handle_reload)
    await sensor.async_schedule_update()
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
        """Laad data met veilige merge voor handmatige historie."""
        def _read_data():
            if os.path.exists(self._data_file):
                with open(self._data_file, "r") as f:
                    return json.load(f)
            return {"days": {}, "total": 0.0}

        try:
            data = await self.hass.async_add_executor_job(_read_data)
            
            # Behoud handmatige dagen tijdens merges
            existing_days = self._days.copy()
            self._days = {**data.get("days", {}), **existing_days}
            
            # Herbereken totaal
            self._state = round(sum(
                day["amount"] for day in self._days.values()
                if self._is_date_in_season(day.get("date", ""))
            ), 2)
            
            _LOGGER.debug(f"Data geladen, {len(self._days)} dagen beschikbaar")
        except Exception as e:
            _LOGGER.error(f"Fout bij laden data: {e}")

    async def async_save_data(self, event=None):
        """Veilig opslaan zonder handmatige data te overschrijven."""
        try:
            data = {
                "days": {k: v for k, v in self._days.items() 
                        if self._is_date_in_season(v.get("date", ""))},
                "total": self._state,
                "last_updated": datetime.now().isoformat()
            }
            await self.hass.async_add_executor_job(self._write_data_sync, data)
        except Exception as e:
            _LOGGER.error(f"Opslaan mislukt: {e}")

    def _write_data_sync(self, data):
        """Thread-safe schrijfbewerking."""
        temp_file = f"{self._data_file}.tmp"
        with open(temp_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(temp_file, self._data_file)

    # ... [Behoud alle bestaande methodes zoals _update_daily, etc] ...

    @property
    def extra_state_attributes(self):
        """Voeg versie-info toe voor debuggen."""
        return {
            "version": "2024.08.1",
            "data_file": self._data_file,
            **super().extra_state_attributes
        }