"""HTTP surface for Nebula OTA.

* GET /api/nebula_ota/v1/{device}/{build_type}/{incr}   (no auth) - update feed
* GET /api/nebula_ota/{device}                          (no auth) - update feed (alias)
* GET /api/nebula_ota/download/{device}/{filename}      (no auth) - the zip

All unauthenticated because the LineageOS Updater sends no HA credentials;
gated by the optional shared `?token=` secret from the config entry.
"""

from __future__ import annotations

import hmac
import logging
from http import HTTPStatus

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers import network

from .const import (
    CONF_BASE_URL,
    CONF_TOKEN,
    DATA_STORE,
    DEFAULT_CHANNEL,
    DOMAIN,
    DOWNLOAD_URL,
    FEED_URL,
    FEED_URL_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


def _entry_data(hass: HomeAssistant) -> dict:
    for value in hass.data.get(DOMAIN, {}).values():
        if isinstance(value, dict) and DATA_STORE in value:
            return value
    return {}


def _check_token(hass: HomeAssistant, request: web.Request) -> bool:
    want = _entry_data(hass).get(CONF_TOKEN) or ""
    if not want:
        return True
    got = request.query.get("token", "")
    return hmac.compare_digest(got, want)


def _base_url(hass: HomeAssistant) -> str:
    configured = (_entry_data(hass).get(CONF_BASE_URL) or "").rstrip("/")
    if configured:
        return configured
    try:
        return network.get_url(hass, allow_internal=True, allow_external=True).rstrip("/")
    except network.NoURLAvailableError:
        return ""


def async_register_http(hass: HomeAssistant) -> None:
    hass.http.register_view(NebulaOtaFeedView())
    hass.http.register_view(NebulaOtaDownloadView())


class NebulaOtaFeedView(HomeAssistantView):
    url = FEED_URL
    extra_urls = list(FEED_URL_EXTRA)
    name = "api:nebula_ota:feed"
    requires_auth = False

    async def get(
        self,
        request: web.Request,
        device: str,
        build_type: str = DEFAULT_CHANNEL,
        incr: str = "",
    ) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        data = _entry_data(hass)
        store = data.get(DATA_STORE)
        if store is None:
            return self.json_message("Nebula OTA not set up", HTTPStatus.SERVICE_UNAVAILABLE)
        if not _check_token(hass, request):
            return self.json_message("Forbidden", HTTPStatus.FORBIDDEN)

        builds = store.builds_for(device, build_type)
        token = data.get(CONF_TOKEN) or None
        base = _base_url(hass)
        return self.json(
            {"response": [b.as_feed_entry(base, token) for b in builds]},
            headers={"Cache-Control": "no-store"},
        )


class NebulaOtaDownloadView(HomeAssistantView):
    url = DOWNLOAD_URL
    name = "api:nebula_ota:download"
    requires_auth = False

    async def get(self, request: web.Request, device: str, filename: str) -> web.StreamResponse:
        hass: HomeAssistant = request.app["hass"]
        store = _entry_data(hass).get(DATA_STORE)
        if store is None:
            return self.json_message("Nebula OTA not set up", HTTPStatus.SERVICE_UNAVAILABLE)
        if not _check_token(hass, request):
            return self.json_message("Forbidden", HTTPStatus.FORBIDDEN)

        build = store.get(device, filename)
        if build is None:
            return self.json_message("Unknown build", HTTPStatus.NOT_FOUND)

        # FileResponse handles Range / resume, which the Updater uses.
        return web.FileResponse(
            build.path,
            headers={
                "Content-Disposition": f'attachment; filename="{build.filename}"',
                "Cache-Control": "public, max-age=31536000, immutable",
            },
        )
