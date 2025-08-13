import logging
from datetime import datetime, timedelta
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.const import STATE_HOME

from .const import DOMAIN, RESIDENTS, GUEST_INPUT_ENTITY, PRICE_PER_PERSON, STORAGE_KEY

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry):
    store = Store(hass, 1, STORAGE_KEY)

    data = await store.async_load() or {
        "total_nights": 0,
        "total_amount": 0.0
    }

    async def check_tourist_tax(now):
        guests = hass.states.get(GUEST_INPUT_ENTITY)
        guest_count = int(guests.state) if guests else 0

        resident_count = sum(
            1 for person in RESIDENTS
            if hass.states.get(person) and hass.states.get(person).state == STATE_HOME
        )

        total_people = resident_count + guest_count
        amount = round(total_people * PRICE_PER_PERSON, 2)

        data["total_nights"] += 1
        data["total_amount"] = round(data["total_amount"] + amount, 2)

        await store.async_save(data)

        hass.data[DOMAIN] = {
            "today_people": total_people,
            "today_amount": amount,
            "total_nights": data["total_nights"],
            "total_amount": data["total_amount"]
        }

        for entity in hass.data.get(f"{DOMAIN}_entities", []):
            await entity.async_update_ha_state(True)

        _LOGGER.info("Toeristenbelasting: %s pers, €%s", total_people, amount)

    # TESTMODUS — nu + 2 minuten
    now = datetime.now()
    test_time = (now + timedelta(minutes=2)).time()
    _LOGGER.warning("TESTMODUS: Berekening om %02d:%02d", test_time.hour, test_time.minute)
    async_track_time_change(hass, check_tourist_tax, hour=test_time.hour, minute=test_time.minute)

    # PRODUCTIE — elke dag om 23:00
    # async_track_time_change(hass, check_tourist_tax, hour=23, minute=0)

    hass.helpers.discovery.load_platform("sensor", DOMAIN, {}, entry.data)
    return True
