"""晾衣架 cover 实体。

实测 props.position 语义 (hanger_ypr):
  "0" 收起 (最高位) -> HA closed (0%)
  "1" 中位          -> 50%
  "2" 放下 (最低位) -> HA open (100%)
  "3" 上升中        -> closing
  "4" 下降中        -> opening
控制指令: 打开=putDown(下降), 关闭=raiseUp(上升), 停止=stop
"""

from __future__ import annotations

import logging

from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CMD_PUT_DOWN,
    CMD_RAISE_UP,
    CMD_STOP,
    DOMAIN,
    MANUFACTURER,
    POS_ASCENDING,
    POS_BOTTOM,
    POS_DESCENDING,
    POS_MID,
    POS_TOP,
    SUPPORTED_MODEL,
)
from .coordinator import GfDataCoordinator
from .gf_client import GfClientError

_LOGGER = logging.getLogger(__name__)

# position -> HA cover 位置百分比
POSITION_MAP = {
    POS_TOP: 0,
    POS_MID: 50,
    POS_BOTTOM: 100,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    coordinator: GfDataCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities = [
        GfCover(coordinator, device)
        for device in coordinator.device_list
        if device.get("e_model") == SUPPORTED_MODEL
    ]
    async_add_entities(entities)


class GfCover(CoordinatorEntity[GfDataCoordinator], CoverEntity):
    """格峰晾衣架。"""

    _attr_has_entity_name = True
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )
    _attr_name = None  # 设备级实体, 名称即设备名

    def __init__(self, coordinator: GfDataCoordinator, device: dict) -> None:
        super().__init__(coordinator)
        self._device_id = device["_id"]
        self._attr_unique_id = self._device_id
        self._last_position: int | None = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=device.get("e_name") or "晾衣架",
            manufacturer=MANUFACTURER,
            model=device.get("e_model"),
            sw_version=device.get("wifiVersion"),
        )

    # ------------------------------------------------------------------ 状态

    @property
    def _device(self) -> dict:
        return self.coordinator.get_device(self._device_id) or {}

    @property
    def _props(self) -> dict:
        return self._device.get("props") or {}

    @property
    def _position(self) -> str | None:
        return self._props.get("position")

    @property
    def current_cover_position(self) -> int | None:
        position = self._position
        if position in POSITION_MAP:
            self._last_position = POSITION_MAP[position]
        return self._last_position

    @property
    def is_closed(self) -> bool:
        return self._position == POS_TOP

    @property
    def is_opening(self) -> bool:
        return self._position == POS_DESCENDING

    @property
    def is_closing(self) -> bool:
        return self._position == POS_ASCENDING

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.client.connected
            and self._device.get("isOnline", True)
        )

    # ------------------------------------------------------------------ 控制

    async def _send(self, name: str) -> None:
        client = self.coordinator.client
        try:
            resp = await client.remote_control(self._device_id, name)
            if resp.get("code") != 200:
                _LOGGER.warning(
                    "%s: 指令 %s 被云端拒绝 (code=%s %s)",
                    self.name,
                    name,
                    resp.get("code"),
                    resp.get("codetxt", ""),
                )
        except GfClientError as err:
            _LOGGER.error("%s: 发送指令 %s 失败: %s", self.name, name, err)
            raise

    async def async_open_cover(self, **kwargs) -> None:
        """打开 = 下降 (putDown)。"""
        await self._send(CMD_PUT_DOWN)

    async def async_close_cover(self, **kwargs) -> None:
        """关闭 = 上升 (raiseUp)。"""
        await self._send(CMD_RAISE_UP)

    async def async_stop_cover(self, **kwargs) -> None:
        await self._send(CMD_STOP)
