import asyncio
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .gf_client import GfClient

_LOGGER = logging.getLogger(__name__)

# 假设 host 和 port 在这里硬编码，实际可根据需求调整
HOST = "main.ortron.cn"
PORT = 13015

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    if entry.domain != "gofullhanger":
        return False

    mobile = entry.data.get("mobile")
    password = entry.data.get("password")
    clientid = entry.data.get("clientid")

    if not all([mobile, password, clientid]):
        _LOGGER.error("配置信息不完整，请检查mobile、password和clientid配置")
        return False

    # 添加重试机制
    max_retries = 3
    for attempt in range(max_retries):
        try:
            client = GfClient(HOST, PORT, hass, max_retries=3)
            
            _LOGGER.info(f"尝试连接Gf Hanger服务器 (第{attempt + 1}次尝试)...")
            
            connected = await client.connect()
            if not connected:
                _LOGGER.warning(f"连接失败，将在{2 ** attempt}秒后重试")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
                    continue
                else:
                    _LOGGER.error("达到最大重试次数，连接失败")
                    return False

            logged_in = await client.login(mobile, password, clientid)
            if not logged_in:
                _LOGGER.warning(f"登录失败，将在{2 ** attempt}秒后重试")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
                    continue
                else:
                    _LOGGER.error("达到最大重试次数，登录失败")
                    return False

            # 连接和登录成功
            hass.data.setdefault(entry.entry_id, {})
            hass.data[entry.entry_id]["client"] = client

            # 设置cover平台
            await hass.config_entries.async_forward_entry_setups(entry, ["cover"])
            
            _LOGGER.info("Gf Hanger集成设置成功")
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
            _LOGGER.error(f"设置Gf Hanger时出错 (第{attempt + 1}次尝试): {e}")
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
        client.close()
        hass.data.pop(entry.entry_id)
    return unload_ok
