"""Config flow for Nebula OTA (single instance)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_BASE_URL,
    CONF_BUILDS_DIR,
    CONF_CHANNEL,
    CONF_TOKEN,
    DEFAULT_BUILDS_DIR,
    DEFAULT_CHANNEL,
    DOMAIN,
)


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(
                CONF_BUILDS_DIR, default=defaults.get(CONF_BUILDS_DIR, DEFAULT_BUILDS_DIR)
            ): str,
            vol.Optional(CONF_BASE_URL, default=defaults.get(CONF_BASE_URL, "")): str,
            vol.Optional(CONF_TOKEN, default=defaults.get(CONF_TOKEN, "")): str,
            vol.Optional(
                CONF_CHANNEL, default=defaults.get(CONF_CHANNEL, DEFAULT_CHANNEL)
            ): str,
        }
    )


class NebulaOtaConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="Nebula OTA", data=user_input)

        return self.async_show_form(step_id="user", data_schema=_schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return NebulaOtaOptionsFlow(config_entry)


class NebulaOtaOptionsFlow(OptionsFlow):
    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=_schema(current))
