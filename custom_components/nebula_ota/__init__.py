"""The Nebula OTA integration.

Serves the LineageOS-style OTA feed + the signed build zips for Nebula Cosmos
UI from the Home Assistant server, so the panels update from your HA instead of
download.lineageos.org. Drop signed zips in `<config>/nebula_ota/builds/<device>/`
(or point `builds_dir` elsewhere); `vendor/nebula/tools/publish-ota.sh` can do
that for you.
"""

from __future__ import annotations

import logging
import os
from datetime import timedelta

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_BASE_URL,
    CONF_BUILDS_DIR,
    CONF_CHANNEL,
    CONF_TOKEN,
    DATA_STORE,
    DATA_UNSUB,
    DEFAULT_BUILDS_DIR,
    DEFAULT_CHANNEL,
    DOMAIN,
    SCAN_INTERVAL,
    SIGNAL_BUILDS_CHANGED,
)
from .http import async_register_http
from .store import BuildStore

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nebula OTA from a config entry."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    cfg = {**entry.data, **entry.options}

    raw_dir = cfg.get(CONF_BUILDS_DIR) or DEFAULT_BUILDS_DIR
    builds_dir = raw_dir if os.path.isabs(raw_dir) else hass.config.path(raw_dir)
    channel = cfg.get(CONF_CHANNEL) or DEFAULT_CHANNEL

    store = BuildStore(hass, builds_dir, channel)
    await store.async_scan()
    _LOGGER.info(
        "Nebula OTA: serving from %s (%d device(s)); feed at /api/nebula_ota/{device}",
        builds_dir, len(store.devices()),
    )

    entry_store = {
        DATA_STORE: store,
        CONF_TOKEN: cfg.get(CONF_TOKEN) or "",
        CONF_BASE_URL: cfg.get(CONF_BASE_URL) or "",
    }
    domain_data[entry.entry_id] = entry_store

    if not domain_data.get("_http_registered"):
        async_register_http(hass)
        _register_services(hass)
        domain_data["_http_registered"] = True

    async def _rescan(_now) -> None:
        if await store.async_scan():
            async_dispatcher_send(hass, SIGNAL_BUILDS_CHANGED)

    entry_store[DATA_UNSUB] = async_track_time_interval(
        hass, _rescan, timedelta(seconds=SCAN_INTERVAL)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    data = hass.data[DOMAIN].pop(entry.entry_id, None)
    if data and (unsub := data.get(DATA_UNSUB)):
        unsub()
    return unload_ok


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _register_services(hass: HomeAssistant) -> None:
    """`nebula_ota.rescan` — force a build-library rescan now."""

    async def _rescan(_call: ServiceCall) -> None:
        changed = False
        for data in hass.data.get(DOMAIN, {}).values():
            if isinstance(data, dict) and (store := data.get(DATA_STORE)):
                changed |= await store.async_scan()
        if changed:
            async_dispatcher_send(hass, SIGNAL_BUILDS_CHANGED)

    hass.services.async_register(DOMAIN, "rescan", _rescan, schema=vol.Schema({}))
