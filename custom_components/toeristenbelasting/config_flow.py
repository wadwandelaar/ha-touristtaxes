import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN, CONF_GUESTS, CONF_MODE, PRICE_PER_PERSON

class TouristTaxesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            # Simpele validatie: gasten moet een positief getal zijn
            if user_input[CONF_GUESTS] <= 0:
                errors["base"] = "invalid_guests"
            else:
                return self.async_create_entry(
                    title="Tourist Taxes",
                    data={
                        CONF_GUESTS: user_input[CONF_GUESTS],
                        CONF_MODE: user_input[CONF_MODE],
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_GUESTS, default=1): int,
                vol.Required(CONF_MODE, default="standard"): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
