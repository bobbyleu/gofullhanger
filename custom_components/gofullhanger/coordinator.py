"""数据协调器: 维护设备状态, 由 gf_client 的推送驱动更新。"""

from __future__ import annotations

import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DEVICE_TYPE_HANGER,
    DOMAIN,
    PUSH_DEVICE_OPERATION,
    PUSH_DEVICE_STATUS,
    PUSH_HOME_INFO,
    SUPPORTED_MODEL,
)
from .gf_client import GfClient

_LOGGER = logging.getLogger(__name__)


def _iter_devices(obj):
    """递归遍历 onHomeInfo 结构, 产出所有设备 dict。"""
    if isinstance(obj, dict):
        if obj.get("e_type") == DEVICE_TYPE_HANGER and obj.get("_id"):
            yield obj
        for value in obj.values():
            yield from _iter_devices(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_devices(item)


class GfDataCoordinator(DataUpdateCoordinator):
    """推送驱动的协调器 (update_interval=None, 不轮询)。"""

    def __init__(self, hass, client: GfClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,  # 纯推送, 长连接
        )
        self.client = client
        self.devices: dict[str, dict] = {}
        self.operation_messages: dict[str, str] = {}

        client.add_push_handler(PUSH_HOME_INFO, self._on_home_info)
        client.add_push_handler(PUSH_DEVICE_STATUS, self._on_device_status)
        client.add_push_handler(PUSH_DEVICE_OPERATION, self._on_device_operation)

    # ------------------------------------------------------------------ 推送处理

    def _on_home_info(self, body: dict) -> None:
        for device in _iter_devices(body or {}):
            if device.get("e_model") != SUPPORTED_MODEL:
                continue
            device_id = device["_id"]
            existing = self.devices.get(device_id)
            if existing is None:
                self.devices[device_id] = device
            else:
                # 保留最新 props, 更新静态信息
                existing.update(device)
        self._publish()

    def _on_device_status(self, body: dict) -> None:
        for device in (body or {}).get("devices", []):
            device_id = device.get("_id")
            if not device_id:
                continue
            if device.get("e_model") != SUPPORTED_MODEL:
                continue
            existing = self.devices.get(device_id)
            if existing is None:
                # 尚未在 onHomeInfo 中出现过, 先记录
                self.devices[device_id] = device
            else:
                existing.update(device)
        self._publish()

    def _on_device_operation(self, body: dict) -> None:
        device_id = (body or {}).get("deviceId")
        msg = (body or {}).get("msg", "")
        if device_id:
            self.operation_messages[device_id] = msg
            if msg and msg != "操作成功":
                _LOGGER.warning("设备 %s 操作结果: %s", device_id, msg)

    def _publish(self) -> None:
        self.async_set_updated_data(dict(self.devices))

    # ------------------------------------------------------------------ 辅助

    def get_device(self, device_id: str) -> dict | None:
        return self.devices.get(device_id)

    @property
    def device_list(self) -> list[dict]:
        return list(self.devices.values())
