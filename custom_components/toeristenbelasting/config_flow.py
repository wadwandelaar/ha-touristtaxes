from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from .const import DOMAIN

class TouristTaxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="Toeristenbelasting", data={})
        return self.async_show_form(step_id="user", data_schema=None)
