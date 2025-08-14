from homeassistant.core import ServiceCall
from homeassistant.helpers.typing import HomeAssistantType
from .const import DOMAIN

async def async_setup(hass: HomeAssistantType, config: dict):
    """Set up the component and register services."""

    async def handle_force_update(call: ServiceCall):
        sensor_entity = hass.data.get(DOMAIN)
        if sensor_entity:
            await sensor_entity._update_daily()

    async def handle_reset(call: ServiceCall):
        sensor_entity = hass.data.get(DOMAIN)
        if sensor_entity:
            sensor_entity.reset_data()

    hass.services.async_register(DOMAIN, "force_update", handle_force_update)
    hass.services.async_register(DOMAIN, "reset", handle_reset)

    return True

async def async_setup_entry(hass: HomeAssistantType, entry):
    """Set up from config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    )
    return True
