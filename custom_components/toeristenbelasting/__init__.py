"""Tourist Taxes integration for Home Assistant"""
from datetime import datetime, timedelta, time
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store

from .const import DOMAIN, RESIDENTS, GUEST_INPUT_ENTITY, PRICE_PER_PERSON, STORAGE_KEY

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the integration (legacy setup)."""
    _LOGGER.info("Tourist Taxes: async_setup called")
    return True

async def async_setup_entry(hass: HomeAssistant, entry):
    """Set up the integration from a config entry."""
    _LOGGER.info("Tourist Taxes: async_setup_entry called")

    hass.data.setdefault(DOMAIN, {})
    store = Store(hass, 1, STORAGE_KEY)
    hass.data[DOMAIN]['store'] = store

    async def check_tourist_tax(now_time=None):
        """Check who is home and calculate tourist tax."""
        guests = hass.states.get(GUEST_INPUT_ENTITY)
        guests_count = int(guests.state) if guests else 0

        residents_home = [r for r in RESIDENTS if hass.states.is_state(r, "home")]
        total_people = len(residents_home) + guests_count

        amount = total_people * PRICE_PER_PERSON
        _LOGGER.info(
            "TOURIST TAX CALCULATION: %d residents + %d guests = %d total, amount €%.2f",
            len(residents_home),
            guests_count,
            total_people,
            amount,
        )

        # Sla het op in storage
        data = await store.async_load() or {}
        today = datetime.now().strftime("%Y-%m-%d")
        data[today] = {"people": total_people, "amount": amount}
        await store.async_save(data)

    # Kies modus: test of productie
    mode = entry.data.get("mode", "prod")
    now = datetime.now()
    if mode == "test":
        test_time = (now + timedelta(minutes=2)).time()
        _LOGGER.info("TESTMODUS: Berekening om %s", test_time.strftime("%H:%M"))
        async_track_time_change(hass, check_tourist_tax, hour=test_time.hour, minute=test_time.minute)
    else:
        async_track_time_change(hass, check_tourist_tax, hour=23, minute=0)

    # Sensor platform laden
    await discovery.async_load_platform(hass, "sensor", DOMAIN, {}, entry.data)

    return True
