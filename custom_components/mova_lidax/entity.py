"""Base entity for MOVA LiDAX."""

from __future__ import annotations

from functools import partial
from typing import Any

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MovaLidaxCoordinator


class MovaLidaxEntity(CoordinatorEntity[MovaLidaxCoordinator]):
    """Base entity."""

    def __init__(self, coordinator: MovaLidaxCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_has_entity_name = True

    @property
    def device(self):
        return self.coordinator.device

    @property
    def available(self) -> bool:
        # LiDAX data often continue to flow through device callbacks even when the
        # coordinator's last polling refresh was not marked successful.
        return self.device is not None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self.device.mac)},
            identifiers={(DOMAIN, self.device.mac)},
            name=self.device.name,
            manufacturer=self.device.info.manufacturer if self.device.info else "MOVA",
            model=self.device.info.model if self.device.info else "LiDAX",
            sw_version=self.device.info.firmware_version if self.device.info else None,
            hw_version=self.device.info.hardware_version if self.device.info else None,
        )

    async def _exec(self, func, *args, **kwargs) -> Any:
        try:
            result = await self.hass.async_add_executor_job(partial(func, *args, **kwargs))
            self.coordinator.async_set_updated_data(self.device)
            return result
        except Exception as exc:
            raise HomeAssistantError(str(exc)) from exc
