from homeassistant import config_entries
import voluptuous as vol
from .const import DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="Tourist Taxes", data=user_input)

        zones = self.hass.states.async_entity_ids("zone")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("price_per_person", default=2.40): float,
                vol.Required("home_zone", default="zone.home"): vol.In(zones),
                vol.Optional("update_hour", default=23): vol.All(int, vol.Range(min=0, max=23)),
                vol.Optional("update_minute", default=0): vol.All(int, vol.Range(min=0, max=59))
            })
        )