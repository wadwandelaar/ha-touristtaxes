from datetime import datetime
from homeassistant.core import ServiceCall
from homeassistant.helpers.typing import HomeAssistantType
from .const import DOMAIN

async def async_setup(hass: HomeAssistantType, config: dict):
    """Set up the component."""

    async def handle_force_update(call: ServiceCall):
        """Handle force update service call."""
        sensor_entity = hass.data.get(DOMAIN)
        if sensor_entity:
            await sensor_entity._update_daily()
        else:
            hass.logger.warning("TouristTaxes: Sensor entity not found for force update")

    # Registreer de service
    hass.services.async_register(
        DOMAIN,
        "force_update",
        handle_force_update
    )

    return True

async def async_setup_entry(hass: HomeAssistantType, entry):
    """Set up from config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    )
    return True
