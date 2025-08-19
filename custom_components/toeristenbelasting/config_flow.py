"""Config flow for Tourist Taxes."""
from homeassistant import config_entries
import voluptuous as vol
from .const import DOMAIN, DEFAULT_PRICE

class TouristTaxesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tourist Taxes."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Validate input
            if user_input["price_per_person"] <= 0:
                errors["price_per_person"] = "price_must_be_positive"
            
            if not errors:
                return self.async_create_entry(title="Tourist Taxes", data=user_input)
            
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("price_per_person", default=DEFAULT_PRICE): vol.Coerce(float),
                vol.Required("home_zone", default="zone.home"): str
            }),
            errors=errors
        )