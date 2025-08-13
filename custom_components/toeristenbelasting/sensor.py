"""Sensor platform for Tourist Taxes integration."""
from homeassistant.components.sensor import SensorEntity
import logging

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the tourist taxes sensors."""
    coordinator = hass.data[DOMAIN]["coordinator"]

    async_add_entities([
        TouristTaxesSensor(coordinator, "Daily Tax"),
        TouristTaxesSensor(coordinator, "Total Tax"),
    ], True)

class TouristTaxesSensor(SensorEntity):
    """Sensor voor dagelijkse en totale toeristenbelasting."""

    def __init__(self, coordinator, name):
        self.coordinator = coordinator
        self._name = name

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        if not self.coordinator.data:
            return 0
        if self._name == "Daily Tax":
            last_day = sorted(self.coordinator.data.keys())[-1]
            return self.coordinator.data.get(last_day, 0)
        elif self._name == "Total Tax":
            return sum(self.coordinator.data.values())
        return 0

    @property
    def unit_of_measurement(self):
        return "€"

    async def async_update(self):
        await self.coordinator.async_request_refresh()
