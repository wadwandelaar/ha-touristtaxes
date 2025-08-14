from homeassistant import config_entries
from .const import *
import voluptuous as vol


class TouristTaxesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="Tourist Taxes", data=user_input)

        zones = self.hass.states.async_entity_ids("zone")
        persons = self.hass.states.async_entity_ids("person")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_PRICE_PER_PERSON, default=DEFAULT_PRICE_PER_PERSON): vol.Coerce(float),
                vol.Required(CONF_HOME_ZONE, default="zone.home"): vol.In(zones)
            })
        )