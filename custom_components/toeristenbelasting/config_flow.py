from homeassistant import config_entries
from datetime import time
import voluptuous as vol
from .const import DOMAIN, DEFAULT_PRICE

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        if user_input is not None:
            # Sla de tijd op als string (bijv. "13:49")
            user_input["update_time"] = f"{user_input['update_hour']}:{user_input['update_minute']}"
            return self.async_create_entry(title="Tourist Taxes", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("price_per_person", default=2.40): float,
                vol.Required("home_zone", default="zone.home"): str,
                vol.Required("update_hour", default=23): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
                vol.Required("update_minute", default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=59))
            })
        )
    
class TouristTaxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
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