"""格峰晾衣架 (gofullhanger) Home Assistant 自定义集成。"""

from __future__ import annotations

import logging

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
)
from homeassistant.core import HomeAssistant

from .const import (
    CONF_CLIENTID,
    CONF_MOBILE,
    CONF_PASSWORD,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DOMAIN,
    PACKAGE_NAME,
)
from .coordinator import GfDataCoordinator
from .gf_client import GfAuthError, GfClient, GfClientError

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["cover", "switch", "sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    mobile = entry.data[CONF_MOBILE]
    password = entry.data[CONF_PASSWORD]
    clientid = entry.data.get(CONF_CLIENTID)

    client = GfClient(DEFAULT_HOST, DEFAULT_PORT, PACKAGE_NAME)
    coordinator = GfDataCoordinator(hass, client)

    try:
        await client.connect(mobile, password, clientid)
    except GfAuthError as err:
        await client.close()
        _LOGGER.error("格峰晾衣架登录失败: %s", err)
        raise ConfigEntryAuthFailed(str(err)) from err
    except (GfClientError, OSError) as err:
        await client.close()
        _LOGGER.warning("格峰晾衣架暂时无法连接: %s", err)
        raise ConfigEntryNotReady(str(err)) from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # clientid 首次生成后持久化
    if entry.data.get(CONF_CLIENTID) != client.clientid:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_CLIENTID: client.clientid}
        )

    _LOGGER.info(
        "格峰晾衣架集成已启动, 发现 %d 台设备", len(coordinator.device_list)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["client"].close()
    return unload_ok
