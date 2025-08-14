from homeassistant import config_entries
import voluptuous as vol
from .const import DOMAIN, DEFAULT_PRICE

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="Tourist Taxes", data=user_input)
            
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("price_per_person", default=DEFAULT_PRICE): float,
                vol.Required("home_zone", default="zone.home"): str
            })
        )