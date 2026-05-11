"""Map camera entities for MOVA LiDAX."""

from __future__ import annotations

import asyncio
import collections
import time
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from typing import Any

from aiohttp import web

from homeassistant.components.camera import Camera, CameraEntityDescription, ENTITY_ID_FORMAT
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONTENT_TYPE_MULTIPART, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity import EntityCategory, async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_CALIBRATION, DOMAIN, LOGGER
from .coordinator import MovaLidaxCoordinator
from .dreame.map import DreameMowerMapDataJsonRenderer, DreameMowerMapRenderer
from .entity import MovaLidaxEntity

CONTENT_TYPE_JPEG = "image/jpeg"
CONTENT_TYPE_PNG = "image/png"


@dataclass(frozen=True, kw_only=True)
class MovaLidaxCameraEntityDescription(CameraEntityDescription):
    """Description for a MOVA LiDAX camera entity."""

    map_data_json: bool = False


CAMERAS: tuple[MovaLidaxCameraEntityDescription, ...] = (
    MovaLidaxCameraEntityDescription(key="map", name="Map", icon="mdi:map"),
    MovaLidaxCameraEntityDescription(
        key="map_data",
        name="Map Data",
        icon="mdi:map",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        map_data_json=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MOVA LiDAX camera entities."""
    coordinator: MovaLidaxCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(MovaLidaxMapCamera(coordinator, description) for description in CAMERAS)

    update_map_cameras = partial(async_update_saved_map_cameras, coordinator, {}, async_add_entities)
    coordinator.async_add_listener(update_map_cameras)
    update_map_cameras()


@callback
def async_update_saved_map_cameras(
    coordinator: MovaLidaxCoordinator,
    current: dict[int, list[MovaLidaxMapCamera]],
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add one disabled-by-default camera for every saved map."""
    map_list = coordinator.device.status.map_list or []
    new_indexes = set(range(1, len(map_list) + 1))
    current_indexes = set(current)
    new_entities: list[MovaLidaxMapCamera] = []

    for map_index in current_indexes - new_indexes:
        async_remove_saved_map_camera(map_index, coordinator, current)

    for map_index in new_indexes - current_indexes:
        current[map_index] = [
            MovaLidaxMapCamera(
                coordinator,
                MovaLidaxCameraEntityDescription(
                    key=f"saved_map_{map_index}",
                    name=f"Saved Map {map_index}",
                    icon="mdi:map-search",
                    entity_category=EntityCategory.CONFIG,
                    entity_registry_enabled_default=False,
                ),
                map_index=map_index,
            )
        ]
        new_entities.extend(current[map_index])

    if new_entities:
        async_add_entities(new_entities)


def async_remove_saved_map_camera(
    map_index: int,
    coordinator: MovaLidaxCoordinator,
    current: dict[int, list[MovaLidaxMapCamera]],
) -> None:
    """Remove stale saved-map camera entities."""
    registry = entity_registry.async_get(coordinator.hass)
    for entity in current[map_index]:
        if entity.entity_id in registry.entities:
            registry.async_remove(entity.entity_id)
    del current[map_index]


class MovaLidaxMapCamera(MovaLidaxEntity, Camera):
    """Rendered map camera for MOVA LiDAX."""

    _attr_is_streaming = True
    _attr_should_poll = True
    _supports_native_sync_webrtc = False
    _supports_native_async_webrtc = False
    _webrtc_provider = None
    _legacy_webrtc_provider = None

    def __init__(
        self,
        coordinator: MovaLidaxCoordinator,
        description: MovaLidaxCameraEntityDescription,
        map_index: int = 0,
    ) -> None:
        """Initialize a map camera."""
        super().__init__(coordinator)
        self.entity_description = description
        self.map_index = map_index
        self.content_type = CONTENT_TYPE_PNG if description.map_data_json else CONTENT_TYPE_JPEG
        self.stream = None
        self.access_tokens = collections.deque([], 2)
        self.async_update_token()
        self._last_updated: float | None = None
        self._frame_id: int | None = None
        self._last_map_request = 0.0
        self._calibration_points: Any = None
        self._state: Any = STATE_UNAVAILABLE

        if description.map_data_json:
            self._renderer = DreameMowerMapDataJsonRenderer()
        else:
            self._renderer = DreameMowerMapRenderer()
        self._image = self._renderer.default_map_image
        self._default_map = True

        if map_index:
            self._attr_unique_id = f"{self.device.mac}_saved_map_{map_index}"
            self._attr_name = self._saved_map_name()
            entity_slug = f"{self.device.name.lower()}_saved_map_{map_index}"
        else:
            self._attr_unique_id = f"{self.device.mac}_{description.key}"
            self._attr_name = description.name
            entity_slug = f"{self.device.name.lower()}_{description.key}"

        self.entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, entity_slug, hass=self.coordinator.hass)
        self.update()

    def _saved_map_name(self) -> str:
        """Return a user-facing saved-map camera name."""
        map_data = self._map_data
        if map_data and map_data.custom_name:
            return f"Saved Map {map_data.custom_name.replace('_', ' ').replace('-', ' ').title()}"
        if map_data and map_data.map_name:
            return f"Saved Map {map_data.map_name}"
        return f"Saved Map {self.map_index}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle device updates."""
        if self.map_index:
            new_name = self._saved_map_name()
            if self._attr_name != new_name:
                self._attr_name = new_name

        map_data = self._map_data
        if self._can_render(map_data) and self.available and (self.map_index > 0 or self.device.status.located):
            if self._default_map or self._frame_id != map_data.frame_id:
                self._frame_id = map_data.frame_id
                if not self.device.status.active:
                    self.update()
        else:
            self.update()

        self.async_write_ha_state()

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        """Return the latest rendered map image."""
        now = time.time()
        if now - self._last_map_request >= self.frame_interval:
            self._last_map_request = now
            if self.map_index == 0:
                await self.hass.async_add_executor_job(self.device.update_map)
            self.update()
        return self._image

    async def handle_async_still_stream(self, request: web.Request, interval: float) -> web.StreamResponse:
        """Generate an MJPEG stream from the map camera."""
        response = web.StreamResponse()
        response.content_type = CONTENT_TYPE_MULTIPART.format("--frameboundary")
        await response.prepare(request)

        last_image = None
        while True:
            img_bytes = await self.async_camera_image()
            if not img_bytes:
                img_bytes = self._default_map_image

            if img_bytes != last_image:
                for _ in range(2):
                    await response.write(
                        bytes(
                            "--frameboundary\r\n"
                            f"Content-Type: {self.content_type}\r\n"
                            f"Content-Length: {len(img_bytes)}\r\n\r\n",
                            "utf-8",
                        )
                        + img_bytes
                        + b"\r\n"
                    )
                last_image = img_bytes
            await asyncio.sleep(interval)
        return response

    def update(self) -> None:
        """Refresh rendered image when map data changed."""
        map_data = self._map_data
        if self._can_render(map_data) and self.available and (self.map_index > 0 or self.device.status.located):
            if (
                self.map_index == 0
                and not self.entity_description.map_data_json
                and map_data.last_updated != self._last_updated
                and not self._renderer.render_complete
            ):
                LOGGER.debug("Waiting for MOVA map render to complete")

            if self._renderer.render_complete and map_data.last_updated != self._last_updated:
                self._last_updated = map_data.last_updated
                self._frame_id = map_data.frame_id
                self._default_map = False
                if map_data.timestamp_ms and not map_data.saved_map:
                    self._state = datetime.fromtimestamp(int(map_data.timestamp_ms / 1000))
                elif map_data.last_updated:
                    self._state = datetime.fromtimestamp(int(map_data.last_updated))

                render_data = self.device.get_map_for_render(map_data)
                self._image = self._renderer.render_map(render_data, self.device.status.robot_status)
                if (
                    not self.entity_description.map_data_json
                    and self._calibration_points != self._renderer.calibration_points
                ):
                    self._calibration_points = self._renderer.calibration_points
                    self.coordinator.async_set_updated_data(self.device)
        elif not self._default_map:
            self._image = self._default_map_image
            self._default_map = True
            self._frame_id = None
            self._last_updated = None
            self._state = STATE_UNAVAILABLE

    @property
    def _map_data(self) -> Any:
        return self.device.get_map(self.map_index)

    @staticmethod
    def _can_render(map_data: Any) -> bool:
        """Return true when map data has enough geometry for the renderer."""
        dimensions = getattr(map_data, "dimensions", None)
        return bool(
            map_data
            and not getattr(map_data, "empty_map", False)
            and dimensions is not None
            and getattr(dimensions, "grid_size", None) is not None
            and getattr(dimensions, "width", 0)
            and getattr(dimensions, "height", 0)
        )

    @property
    def _default_map_image(self) -> bytes:
        if self._image and (not self.device.device_connected or not self.device.cloud_connected):
            return self._renderer.disconnected_map_image
        return self._renderer.default_map_image

    @property
    def frame_interval(self) -> float:
        return 0.5

    @property
    def state(self) -> Any:
        return self._state

    @property
    def available(self) -> bool:
        return self.device is not None and self.device.cloud_connected

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.map_data_json:
            return None

        map_data = self._map_data
        if self._can_render(map_data) and (self.map_index > 0 or self.device.status.located):
            attributes = map_data.as_dict()
            if attributes is not None:
                attributes[ATTR_CALIBRATION] = self._calibration_points or self._renderer.calibration_points
            return attributes
        if self.available:
            return {ATTR_CALIBRATION: self._renderer.default_calibration_points}
        return None
