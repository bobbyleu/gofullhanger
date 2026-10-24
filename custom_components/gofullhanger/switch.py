"""晾衣架功能开关 (消毒/风干/烘干)。

协议为翻转语义: 每次发送 {"name": <func>, "method": "set", "value": null}
设备在开/关之间切换, 结果通过 onDeviceStatusData 的 props 反映。
部分机型 (如仅升降型号) 不支持这些功能, 设备会返回"操作失败"。
"""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MANUFACTURER,
    SUPPORTED_MODEL,
    SWITCH_FUNCTIONS,
)
from .coordinator import GfDataCoordinator
from .gf_client import GfClientError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    coordinator: GfDataCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities = []
    for device in coordinator.device_list:
        if device.get("e_model") != SUPPORTED_MODEL:
            continue
        for prop_key, label, icon in SWITCH_FUNCTIONS:
            entities.append(
                GfFunctionSwitch(coordinator, device["_id"], prop_key, label, icon)
            )
    async_add_entities(entities)


class GfFunctionSwitch(CoordinatorEntity[GfDataCoordinator], SwitchEntity):
    """晾衣架功能开关。"""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GfDataCoordinator,
        device_id: str,
        prop_key: str,
        label: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._prop_key = prop_key
        self._attr_unique_id = f"{device_id}_{prop_key}"
        self._attr_name = label
        self._attr_icon = icon
        self._optimistic: bool | None = None
        device = coordinator.get_device(device_id) or {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device.get("e_name") or "晾衣架",
            manufacturer=MANUFACTURER,
            model=device.get("e_model"),
            sw_version=device.get("wifiVersion"),
        )

    # ------------------------------------------------------------------ 状态

    @property
    def _props(self) -> dict:
        device = self.coordinator.get_device(self._device_id) or {}
        return device.get("props") or {}

    @property
    def is_on(self) -> bool:
        value = self._props.get(self._prop_key)
        if value is None:
            return bool(self._optimistic)
        self._optimistic = None
        return value == "1"

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.client.connected
            and self._prop_key in self._props
        )

    # ------------------------------------------------------------------ 控制

    async def _toggle(self) -> None:
        client = self.coordinator.client
        try:
            resp = await client.remote_control(self._device_id, self._prop_key)
            if resp.get("code") != 200:
                _LOGGER.warning(
                    "%s: 指令 %s 被云端拒绝 (code=%s %s)",
                    self.name,
                    self._prop_key,
                    resp.get("code"),
                    resp.get("codetxt", ""),
                )
        except GfClientError as err:
            _LOGGER.error("%s: 发送指令 %s 失败: %s", self.name, self._prop_key, err)
            raise

    async def async_turn_on(self, **kwargs) -> None:
        if self.is_on:
            return
        self._optimistic = True
        await self._toggle()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        if not self.is_on:
            return
        self._optimistic = False
        await self._toggle()
        self.async_write_ha_state()
