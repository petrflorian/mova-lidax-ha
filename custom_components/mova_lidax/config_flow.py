"""Config flow for MOVA LiDAX."""

from __future__ import annotations

from typing import Any
import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .dreame.protocol import DreameMowerDreameHomeCloudProtocol

from .const import CONF_ACCOUNT_TYPE, CONF_COUNTRY, CONF_DID, CONF_MAC, CONF_MODEL, DEFAULT_ACCOUNT_TYPE, DEFAULT_COUNTRY, DOMAIN

_LOGGER = logging.getLogger(__name__)


class MovaLidaxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle MOVA LiDAX config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._user_input: dict[str, Any] = {}
        self._devices: dict[str, dict[str, Any]] = {}

    @callback
    def _device_label(self, device: dict[str, Any]) -> str:
        name = device.get("customName") or device.get("name") or str(device["did"])
        model = device.get("model", "unknown")
        return f"{name} ({model})"

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Collect cloud credentials."""
        if user_input is not None:
            self._user_input = user_input
            protocol = DreameMowerDreameHomeCloudProtocol(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                user_input[CONF_COUNTRY],
                account_type=user_input[CONF_ACCOUNT_TYPE],
            )
            try:
                logged_in = await self.hass.async_add_executor_job(protocol.login)
                devices = await self.hass.async_add_executor_job(protocol.get_devices) if logged_in else None
            except Exception:
                _LOGGER.exception("MOVA LiDAX login/device discovery failed")
                devices = None

            if not devices:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._user_schema(user_input),
                    errors={"base": "cannot_connect"},
                )

            found = {}
            device_list: list[dict[str, Any]] = []
            if isinstance(devices, list):
                device_list = devices
            elif isinstance(devices, dict):
                if isinstance(devices.get("device"), list):
                    device_list = devices["device"]
                elif isinstance(devices.get("result"), dict) and isinstance(devices["result"].get("device"), list):
                    device_list = devices["result"]["device"]
                elif isinstance(devices.get("devices"), list):
                    device_list = devices["devices"]
                elif isinstance(devices.get("page"), dict) and isinstance(devices["page"].get("records"), list):
                    device_list = devices["page"]["records"]
                elif isinstance(devices.get("devices"), dict) and isinstance(devices["devices"].get("page"), dict):
                    records = devices["devices"]["page"].get("records")
                    if isinstance(records, list):
                        device_list = records

            for device in device_list:
                model = device.get("model", "")
                if model.startswith("mova.mower.") and not device.get("parent_id"):
                    found[str(device["did"])] = device

            if not found:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._user_schema(user_input),
                    errors={"base": "no_devices"},
                )

            self._devices = found
            if len(found) == 1:
                did = next(iter(found))
                return self._create_entry(did)
            return await self.async_step_device()

        return self.async_show_form(step_id="user", data_schema=self._user_schema())

    async def async_step_device(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Select a discovered LiDAX mower."""
        if user_input is not None:
            return self._create_entry(user_input[CONF_DID])

        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DID): vol.In(
                        {did: self._device_label(device) for did, device in self._devices.items()}
                    )
                }
            ),
        )

    def _create_entry(self, did: str) -> FlowResult:
        device = self._devices[did]
        name = device.get("customName") or device.get("name") or "LiDAX Ultra"
        self._async_abort_entries_match({CONF_DID: did})
        return self.async_create_entry(
            title=name,
            data={
                CONF_NAME: name,
                CONF_USERNAME: self._user_input[CONF_USERNAME],
                CONF_PASSWORD: self._user_input[CONF_PASSWORD],
                CONF_COUNTRY: self._user_input[CONF_COUNTRY],
                CONF_ACCOUNT_TYPE: self._user_input[CONF_ACCOUNT_TYPE],
                CONF_DID: did,
                CONF_MAC: device.get("mac"),
                CONF_MODEL: device.get("model"),
            },
        )

    def _user_schema(self, defaults: dict[str, Any] | None = None) -> vol.Schema:
        defaults = defaults or {}
        return vol.Schema(
            {
                vol.Required(CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")): str,
                vol.Required(CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")): str,
                vol.Required(CONF_COUNTRY, default=defaults.get(CONF_COUNTRY, DEFAULT_COUNTRY)): str,
                vol.Required(
                    CONF_ACCOUNT_TYPE,
                    default=defaults.get(CONF_ACCOUNT_TYPE, DEFAULT_ACCOUNT_TYPE),
                ): vol.In(["mova", "dreame"]),
            }
        )
