"""晾衣架 cover 实体。

机械结构 (用户提供, 一号实测验证):
  三个固定档位, 机器运行停止后反馈:
    "0" 上升停止位 - 上升指令的常规停止点
    "1" 隐藏位     - 最高, 完全收起; 上升停止位再上升才到位
    "2" 下降停止位 - 最低, 完全放下
  两个运动状态:
    "3" 上升中 (正在关闭)   "4" 下降中 (正在打开)
  转移规则: 0+上升->1, 1+下降->2, 0+下降->2, 2+上升->0

HA 语义 (不使用百分比, 档位以设备反馈码标注):
  is_closed  = 反馈 "1" (隐藏位, 完全收起)
  is_closing = 反馈 "3" (上升中)
  is_opening = 反馈 "4" (下降中)
  其余 (含 "0" 上升停止位) 显示为打开
  实际档位通过属性 position_code / position_name 标注
控制指令: 打开=putDown(下降), 关闭=raiseUp(上升), 停止=stop
注意: 从下降停止位按一次"关闭"只到上升停止位("0"), 需再按一次才到隐藏位("1")
"""

from __future__ import annotations

import logging

from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CMD_PUT_DOWN,
    CMD_RAISE_UP,
    CMD_STOP,
    DOMAIN,
    MANUFACTURER,
    POSITION_NAMES,
    POS_ASCENDING,
    POS_DESCENDING,
    POS_HIDDEN,
    SUPPORTED_MODEL,
)
from .coordinator import GfDataCoordinator
from .gf_client import GfClientError

_LOGGER = logging.getLogger(__name__)


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
    """格峰晾衣架 (三档位, 以设备反馈码标注状态)。"""

    _attr_has_entity_name = True
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )
    _attr_name = None  # 设备级实体, 名称即设备名

    def __init__(self, coordinator: GfDataCoordinator, device: dict) -> None:
        super().__init__(coordinator)
        self._device_id = device["_id"]
        self._attr_unique_id = self._device_id
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
    def is_closed(self) -> bool:
        """仅隐藏位 ("1") 算完全收起。"""
        return self._position == POS_HIDDEN

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

    @property
    def extra_state_attributes(self) -> dict:
        """暴露设备原始反馈码与档位名称 (不使用百分比)。"""
        code = self._position
        if code is None:
            return {}
        try:
            code_value: int | str = int(code)
        except (TypeError, ValueError):
            code_value = code
        return {
            "position_code": code_value,
            "position_name": POSITION_NAMES.get(code, code),
        }

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
        """打开 = 下降 (putDown), 直达下降停止位。"""
        await self._send(CMD_PUT_DOWN)

    async def async_close_cover(self, **kwargs) -> None:
        """关闭 = 上升 (raiseUp)。

        从下降停止位出发只到上升停止位 ("0"), 需再调用一次才到隐藏位 ("1")。
        """
        await self._send(CMD_RAISE_UP)

    async def async_stop_cover(self, **kwargs) -> None:
        await self._send(CMD_STOP)
