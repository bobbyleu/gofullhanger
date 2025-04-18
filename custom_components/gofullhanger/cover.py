# cover.py
import logging
import asyncio
from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
    ATTR_POSITION,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from .gf_client import GfClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    client = hass.data[entry.entry_id]["client"]
    entities = []
    for device_info in client.devices_info:
        entities.append(GfCover(hass,device_info, client, entry.data))
    async_add_entities(entities)


class GfCover(CoverEntity):
    def __init__(self, hass, device_info, client, config_data):
        self.hass = hass
        self._attr_unique_id = device_info["_id"]
        self._attr_name = device_info["e_name"]
        self._device_info = device_info
        self._client = client
        self._config_data = config_data
        self._attr_supported_features = (
                CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        )
        # 监听自定义事件
        self.hass.bus.async_listen("gf_device_status_update", self._handle_device_status_update)

    @property
    def is_stopped(self):
        return self._device_info["position"] == '0'

    @property
    def is_closed(self):
        return self._device_info["position"] == '1'

    @property
    def is_opened(self):
        return self._device_info["position"] == "2"

    @property
    def is_closing(self):
        return self._device_info["position"] == '3'

    @property
    def is_opening(self):
        return self._device_info["position"] == '4'

    @property
    def current_cover_position(self):
        return self._device_info["position"]

    async def async_open_cover(self, **kwargs):
        await self._client.remote_control(
            self._config_data["mobile"],
            self._config_data["password"],
            self._config_data["clientid"],
            self._device_info["_id"],
            1
        )

    async def async_close_cover(self, **kwargs):
        await self._client.remote_control(
            self._config_data["mobile"],
            self._config_data["password"],
            self._config_data["clientid"],
            self._device_info["_id"],
            2
        )

    async def async_stop_cover(self, **kwargs):
        await self._client.remote_control(
            self._config_data["mobile"],
            self._config_data["password"],
            self._config_data["clientid"],
            self._device_info["_id"],
            3
        )

    async def async_update(self):
        # 可添加更新设备状态的逻辑
        pass

    @callback
    def _handle_device_status_update(self, event):
        device_id = event.data.get("device_id")
        position = event.data.get("position")
        if device_id == self._device_info["_id"]:
            self._device_info["position"] = position
            self.schedule_update_ha_state()


