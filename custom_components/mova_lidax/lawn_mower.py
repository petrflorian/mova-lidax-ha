"""Lawn mower entity for MOVA LiDAX."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components.lawn_mower import LawnMowerActivity, LawnMowerEntity, LawnMowerEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.dreame_mower.dreame import DreameMowerState

from .const import (
    ATTR_MAP_ID,
    DOMAIN,
    SERVICE_RAW_ACTION,
    SERVICE_SCHEDULE_CONFIG,
    SERVICE_SWITCH_MAP,
    SERVICE_UPDATE_SCHEDULE,
)
from .coordinator import MovaLidaxCoordinator
from .entity import MovaLidaxEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: MovaLidaxCoordinator = hass.data[DOMAIN][entry.entry_id]
    platform = entity_platform.current_platform.get()
    platform.async_register_entity_service(
        SERVICE_SWITCH_MAP,
        {
            vol.Optional(ATTR_MAP_ID): cv.positive_int,
        },
        "async_switch_map",
    )
    platform.async_register_entity_service(
        SERVICE_SCHEDULE_CONFIG,
        {
            vol.Required("data"): [object],
        },
        "async_schedule_config",
    )
    platform.async_register_entity_service(
        SERVICE_UPDATE_SCHEDULE,
        {
            vol.Required("schedule_id"): cv.positive_int,
            vol.Optional(ATTR_MAP_ID): cv.positive_int,
            vol.Optional("enabled"): cv.boolean,
            vol.Optional("mode"): cv.positive_int,
            vol.Optional("time_minutes"): cv.positive_int,
            vol.Optional("weekdays"): [cv.positive_int],
            vol.Optional("zones"): [cv.positive_int],
        },
        "async_update_schedule",
    )
    platform.async_register_entity_service(
        SERVICE_RAW_ACTION,
        {
            vol.Required("payload"): [object],
        },
        "async_raw_action",
    )
    async_add_entities([MovaLidaxMowerEntity(coordinator)])


class MovaLidaxMowerEntity(MovaLidaxEntity, LawnMowerEntity):
    """Main mower entity."""

    _attr_supported_features = (
        LawnMowerEntityFeature.START_MOWING
        | LawnMowerEntityFeature.PAUSE
        | LawnMowerEntityFeature.DOCK
    )

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_mower"

    @property
    def activity(self):
        state = self.device.status.state
        if state == DreameMowerState.MOWING:
            return LawnMowerActivity.MOWING
        if state == DreameMowerState.PAUSED:
            return LawnMowerActivity.PAUSED
        if state == DreameMowerState.RETURNING:
            return LawnMowerActivity.RETURNING
        if state in (
            DreameMowerState.CHARGING,
            DreameMowerState.CHARGING_COMPLETED,
            DreameMowerState.SMART_CHARGING,
            DreameMowerState.IDLE,
        ):
            return LawnMowerActivity.DOCKED
        if self.device.status.has_error:
            return LawnMowerActivity.ERROR
        return LawnMowerActivity.DOCKED

    async def async_start_mowing(self) -> None:
        await self._exec(self.device.start)

    async def async_pause(self) -> None:
        await self._exec(self.device.pause)

    async def async_dock(self) -> None:
        await self._exec(self.device.dock)

    async def async_switch_map(self, map_id: int | None = None) -> None:
        if map_id is None and self.device.status.selected_map:
            map_id = self.device.status.selected_map.map_id
        await self._exec(self.device.set_selected_map, map_id)

    async def async_schedule_config(self, data: list) -> None:
        payload = [{"t": "SCHDC", "d": data, "m": "s"}]
        await self._exec(self.device._protocol.action, 2, 50, payload)

    async def async_update_schedule(
        self,
        schedule_id: int,
        map_id: int | None = None,
        enabled: bool | None = None,
        mode: int | None = None,
        time_minutes: int | None = None,
        weekdays: list[int] | None = None,
        zones: list[int] | None = None,
    ) -> None:
        if map_id is None and self.device.status.selected_map:
            map_id = self.device.status.selected_map.map_id
        if map_id is None:
            raise ValueError("map_id is required when no selected map is available")
        await self._exec(
            self.coordinator.update_schedule_entry,
            map_id,
            schedule_id,
            enabled=enabled,
            mode=mode,
            time_minutes=time_minutes,
            weekdays=weekdays,
            zones=zones,
        )

    async def async_raw_action(self, payload: list) -> None:
        await self._exec(self.device._protocol.action, 2, 50, payload)
