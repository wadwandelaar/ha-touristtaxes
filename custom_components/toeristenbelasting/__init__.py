from datetime import datetime
from homeassistant.core import HomeAssistant, ServiceCall
from .const import DOMAIN

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the component and register services."""

    async def handle_force_update(call: ServiceCall):
        """Handle force update service call."""
        sensor_entity = hass.data.get(DOMAIN)
        if sensor_entity:
            await sensor_entity._update_daily(datetime.now())

    async def handle_reset_data(call: ServiceCall):
        """Handle reset data service call."""
        sensor_entity = hass.data.get(DOMAIN)
        if sensor_entity:
            await sensor_entity.reset_data()

    hass.services.async_register(DOMAIN, "force_update", handle_force_update)
    hass.services.async_register(DOMAIN, "reset_data", handle_reset_data)

    return True

async def async_setup_entry(hass: HomeAssistant, entry):
    """Set up from config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    )
    return True
