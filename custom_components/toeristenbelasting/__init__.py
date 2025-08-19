"""The Tourist Taxes integration."""
from datetime import datetime
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Tourist Taxes component."""
    # Forward the setup to the config_flow entry
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Tourist Taxes from a config entry."""
    # Set up the sensor platform
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    # Unload the sensor platform
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    return True