from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN

async def async_setup(hass: HomeAssistant, config: dict):
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    # Werkt voor zowel oude als nieuwe HA versies
    if hasattr(hass.config_entries, 'async_forward_entry_setups'):
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
        )
    else:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "sensor")
        )
    return True