from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN

async def async_setup(hass: HomeAssistant, config: dict):
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    # Moderne aanroep voor nieuwere HA versies
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True