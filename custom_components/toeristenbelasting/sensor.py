"""Sensor platform for Tourist Taxes integration."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from datetime import timedelta
import logging

from .const import DOMAIN, STORAGE_KEY, PRICE_PER_PERSON

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the tourist taxes sensor platform."""
    store = hass.data[DOMAIN]['store']

    coordinator = TouristTaxesCoordinator(hass, store)
    await coordinator.async_config_entry_first_refresh()

    async_add_entities([
        TouristTaxesSensor(coordinator, "Daily Tax"),
        TouristTaxesSensor(coordinator, "Total Tax"),
    ], True)

class TouristTaxesCoordinator(DataUpdateCoordinator):
    """Class to fetch and update tourist taxes from storage."""

    def __init__(self, hass, store):
        super().__init__(
            hass,
            _LOGGER,
            name="Tourist Taxes Coordinator",
            update_interval=timedelta(minutes=5),
        )
        self.store = store
        self.data = {}

    async def _async_update_data(self):
        """Fetch data from storage."""
        data = await self.store.async_load() or {}
        self.data = data
        return data

class TouristTaxesSensor(SensorEntity):
    """Representation of a tourist tax sensor."""

    def __init__(self, coordinator, name):
        self.coordinator = coordinator
        self._name = name
        self._state = None

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        if self._name == "Daily Tax":
            today = list(self.coordinator.data.keys())[-1] if self.coordinator.data else None
            return self.coordinator.data.get(today, {}).get("amount") if today else 0
        elif self._name == "Total Tax":
            total = sum(entry.get("amount", 0) for entry in self.coordinator.data.values())
            return total
        return 0

    @property
    def unit_of_measurement(self):
        return "€"

    async def async_update(self):
        """Update the sensor."""
        await self.coordinator.async_request_refresh()
