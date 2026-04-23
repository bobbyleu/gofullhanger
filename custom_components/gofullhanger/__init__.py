import asyncio
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .mqtt_client import MqttClient
from .const import (
    CONF_MQTT_BROKER,
    CONF_MQTT_PORT,
    CONF_MQTT_USERNAME,
    CONF_MQTT_PASSWORD,
    CONF_MQTT_TOPIC_PREFIX,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    if entry.domain != "gofullhanger":
        return False

    # 获取MQTT配置
    mqtt_broker = entry.data.get(CONF_MQTT_BROKER)
    mqtt_port = entry.data.get(CONF_MQTT_PORT, 1883)
    mqtt_username = entry.data.get(CONF_MQTT_USERNAME)
    mqtt_password = entry.data.get(CONF_MQTT_PASSWORD)
    mqtt_topic_prefix = entry.data.get(CONF_MQTT_TOPIC_PREFIX, "gofullhanger")

    if not mqtt_broker:
        _LOGGER.error("配置信息不完整，请检查MQTT broker配置")
        return False

    # 添加重试机制
    max_retries = 3
    for attempt in range(max_retries):
        try:
            client = MqttClient(
                hass,
                mqtt_broker,
                mqtt_port,
                mqtt_username,
                mqtt_password,
                mqtt_topic_prefix
            )
            
            _LOGGER.info(f"尝试初始化MQTT客户端 (第{attempt + 1}次尝试)...")
            
            connected = await client.connect()
            if not connected:
                _LOGGER.warning(f"初始化失败，将在{2 ** attempt}秒后重试")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
                    continue
                else:
                    _LOGGER.error("达到最大重试次数，初始化失败")
                    return False

            # 连接成功
            hass.data.setdefault(entry.entry_id, {})
            hass.data[entry.entry_id]["client"] = client

            # 设置cover平台
            await hass.config_entries.async_forward_entry_setups(entry, ["cover"])
            
            _LOGGER.info("Gf Hanger MQTT集成设置成功")
            return True
            
        except asyncio.TimeoutError:
            _LOGGER.warning(f"设置超时，将在{2 ** attempt}秒后重试")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            else:
                _LOGGER.error("达到最大重试次数，设置超时")
                return False
                
        except Exception as e:
            _LOGGER.error(f"设置Gf Hanger MQTT时出错 (第{attempt + 1}次尝试): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            else:
                _LOGGER.error("达到最大重试次数，设置失败")
                return False

    return False

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["cover"])
    if unload_ok:
        client = hass.data[entry.entry_id]["client"]
        await client.close()
        hass.data.pop(entry.entry_id)
    return unload_ok
