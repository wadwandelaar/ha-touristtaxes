from homeassistant import config_entries
import voluptuous as vol
from .const import DOMAIN, DEFAULT_PRICE, DEFAULT_ZONE

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        if user_input is not None:
            # Voeg de vaste zone toe aan de configuratie
            user_input["zone"] = DEFAULT_ZONE  # "camping"
            return self.async_create_entry(title="Tourist Taxes", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("price_per_person", default=DEFAULT_PRICE): float
            })
        )