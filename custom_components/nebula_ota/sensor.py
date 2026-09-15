"""`sensor.nebula_ota_<device>_latest` — the newest build on offer per device.

Handy for a notify automation:

    trigger: state of sensor.nebula_ota_checkers_latest changes
    action:  notify.mobile_app_...  "Nebula Cosmos UI {{ states(...) }} is ready"
"""

from __future__ import annotations

from datetime import datetime, timezone

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_STORE, DOMAIN, SIGNAL_BUILDS_CHANGED


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    store = hass.data[DOMAIN][entry.entry_id][DATA_STORE]
    seen: set[str] = set()

    @callback
    def _sync() -> None:
        new = [
            NebulaOtaLatestSensor(entry, store, dev)
            for dev in store.devices()
            if dev not in seen
        ]
        for dev in store.devices():
            seen.add(dev)
        if new:
            async_add_entities(new)

    _sync()
    entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_BUILDS_CHANGED, _sync))


class NebulaOtaLatestSensor(SensorEntity):
    _attr_should_poll = False
    _attr_icon = "mdi:cellphone-arrow-down"
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, store, device: str) -> None:
        self._store = store
        self._device = device
        self._attr_unique_id = f"{entry.entry_id}_{device}_latest"
        self._attr_name = f"{device} latest"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Nebula OTA",
            manufacturer="Nebula",
            model="Cosmos UI update server",
            # Nests this device under "Nebula Panel" (the Nebula Smart Home
            # hub) in the device list — a separate HACS repo/domain, so this
            # is a string-literal cross-integration reference by convention,
            # not an import. Harmless if that device doesn't exist yet (HA
            # just won't show the parent link until it does).
            via_device=("nebula", "panel"),
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_BUILDS_CHANGED, self.async_write_ha_state
            )
        )

    @property
    def native_value(self) -> str:
        b = self._store.latest(self._device)
        return b.version if b else "none"

    @property
    def extra_state_attributes(self) -> dict:
        b = self._store.latest(self._device)
        builds = self._store.builds_for(self._device)
        if not b:
            return {"count": 0}
        return {
            "filename": b.filename,
            "channel": b.romtype,
            "size_mb": round(b.size / 1024 / 1024, 1),
            "sha256": b.sha256,
            "published": datetime.fromtimestamp(b.datetime, timezone.utc).isoformat(),
            "count": len(builds),
        }
