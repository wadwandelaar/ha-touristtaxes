"""Tourist Taxes integration for Home Assistant."""
from datetime import datetime, timedelta
import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.event import async_track_time_change

from .const import DOMAIN, PRICE_PER_PERSON, RESIDENTS

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the integration."""
    store = hass.helpers.storage.Store(1, f"{DOMAIN}.json")
    hass.data[DOMAIN] = {"store": store}

    coordinator = TouristTaxesCoordinator(hass, store)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN]["coordinator"] = coordinator

    # Normale modus: elke avond 23:00
    async_track_time_change(hass, lambda *_: check_tourist_tax(hass), hour=23, minute=0)

    # TESTMODUS: +2 minuten
    now = datetime.now()
    test_time = (now + timedelta(minutes=2)).time()
    async_track_time_change(hass, lambda *_: check_tourist_tax(hass, test=True),
                            hour=test_time.hour, minute=test_time.minute)

    return True

async def check_tourist_tax(hass: HomeAssistant, test=False):
    """Tel het aantal aanwezige bewoners + gasten en sla op."""
    coordinator: TouristTaxesCoordinator = hass.data[DOMAIN]["coordinator"]
    guests = hass.states.get(f"input_number.{DOMAIN}_guests")
    guest_count = int(float(guests.state)) if guests else 0

    present = 0
    for person in RESIDENTS:
        state = hass.states.get(f"person.{person}")
        if state and state.state == "home":
            present += 1

    total_people = present + guest_count
    today = datetime.now().strftime("%Y-%m-%d")
    amount = total_people * PRICE_PER_PERSON

    # Opslaan in coordinator.data
    coordinator.data[today] = amount
    await coordinator.store.async_save(coordinator.data)

    if test:
        _LOGGER.info(f"TESTMODUS: Berekening om {datetime.now().strftime('%H:%M')}: {total_people} personen, €{amount:.2f}")
    else:
        _LOGGER.info(f"Toeristenbelasting berekend voor {today}: {total_people} personen, €{amount:.2f}")

class TouristTaxesCoordinator(DataUpdateCoordinator):
    """Coordinator voor toeristenbelasting."""

    def __init__(self, hass, store):
        super().__init__(
            hass,
            _LOGGER,
            name="Tourist Taxes Coordinator",
            update_interval=timedelta(minutes=5),
        )
        self.store = store
        self.data = {}

    async def _async_update_data(self):
        loaded = await self.store.async_load() or {}
        self.data = loaded
        return self.data
