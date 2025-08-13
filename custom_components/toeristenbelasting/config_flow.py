import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN, CONF_MODE, MODE_TEST, MODE_PROD

class TouristTaxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title="Toeristenbelasting",
                data={CONF_MODE: user_input[CONF_MODE]}
            )

        schema = vol.Schema({
            vol.Required(CONF_MODE, default=MODE_PROD): vol.In({
                MODE_PROD: "Productie (23:00)",
                MODE_TEST: "Testmodus (nu + 2 minuten)"
            })
        })
        return self.async_show_form(step_id="user", data_schema=schema)
