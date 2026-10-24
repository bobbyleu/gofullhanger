"""晾衣架传感器: WiFi 信号强度 (RSSI)。"""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, SUPPORTED_MODEL
from .coordinator import GfDataCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    coordinator: GfDataCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities = [
        GfRssiSensor(coordinator, device["_id"])
        for device in coordinator.device_list
        if device.get("e_model") == SUPPORTED_MODEL
    ]
    async_add_entities(entities)


class GfRssiSensor(CoordinatorEntity[GfDataCoordinator], SensorEntity):
    """设备 WiFi 信号强度。"""

    _attr_has_entity_name = True
    _attr_name = "信号强度"
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = "dBm"
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator: GfDataCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_rssi"
        device = coordinator.get_device(device_id) or {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device.get("e_name") or "晾衣架",
            manufacturer=MANUFACTURER,
            model=device.get("e_model"),
            sw_version=device.get("wifiVersion"),
        )

    @property
    def _props(self) -> dict:
        device = self.coordinator.get_device(self._device_id) or {}
        return device.get("props") or {}

    @property
    def native_value(self):
        rssi = self._props.get("rssi")
        if rssi is None:
            return None
        try:
            return int(rssi)
        except (TypeError, ValueError):
            return None

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.client.connected
            and self._props.get("rssi") is not None
        )
