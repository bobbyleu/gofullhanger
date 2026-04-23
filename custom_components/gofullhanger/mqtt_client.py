import logging
import json
from homeassistant.core import HomeAssistant, Event
from homeassistant.components.mqtt import async_publish, async_subscribe
from .const import (
    MQTT_TOPIC_COMMAND,
    MQTT_TOPIC_STATE,
    MQTT_TOPIC_AVAILABILITY,
    MQTT_COMMAND_OPEN,
    MQTT_COMMAND_CLOSE,
    MQTT_COMMAND_STOP,
    MQTT_AVAILABILITY_ONLINE,
    MQTT_AVAILABILITY_OFFLINE,
)

_LOGGER = logging.getLogger(__name__)

class MqttClient:
    def __init__(self, hass: HomeAssistant, broker: str, port: int, username: str, password: str, topic_prefix: str):
        self.hass = hass
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.topic_prefix = topic_prefix
        self.devices_info = []
        self._subscriptions = []
        self._is_connected = False

    async def connect(self):
        # MQTT连接由Home Assistant的MQTT集成管理，这里我们只需要确保设备信息已初始化
        self._is_connected = True
        _LOGGER.info(f"MQTT客户端已初始化，主题前缀: {self.topic_prefix}")
        
        # 初始化设备信息（这里我们假设有一个默认设备）
        # 实际应用中，可能需要从配置或自动发现获取设备列表
        self.devices_info = [{
            '_id': 'default',
            'e_name': '格峰晾衣架',
            'status': 'online',
            'position': '0'  # 0: 停止, 1: 关闭, 2: 打开, 3: 正在关闭, 4: 正在打开
        }]
        
        # 发布可用性状态
        await self._publish_availability(self.devices_info[0]['_id'], MQTT_AVAILABILITY_ONLINE)
        
        # 订阅状态更新主题
        await self._subscribe_to_state_topics()
        
        return True

    async def close(self):
        # 取消所有订阅
        for subscription in self._subscriptions:
            try:
                await subscription()
            except Exception as e:
                _LOGGER.error(f"取消订阅时出错: {e}")
        self._subscriptions.clear()
        
        # 发布离线状态
        for device in self.devices_info:
            await self._publish_availability(device['_id'], MQTT_AVAILABILITY_OFFLINE)
        
        self._is_connected = False
        _LOGGER.info("MQTT客户端已关闭")

    async def login(self, *args, **kwargs):
        # MQTT不需要登录，直接返回成功
        return True

    async def remote_control(self, *args, deviceId: str, operation_code: int):
        # 根据操作码映射到MQTT命令
        operation_mapping = {
            1: MQTT_COMMAND_OPEN,    # 放下
            2: MQTT_COMMAND_CLOSE,   # 升起
            3: MQTT_COMMAND_STOP     # 停止
        }
        
        command = operation_mapping.get(operation_code)
        if not command:
            _LOGGER.error(f"无效的操作码: {operation_code}")
            return False
        
        # 发布控制命令
        topic = f"{self.topic_prefix}/{deviceId}/{MQTT_TOPIC_COMMAND}"
        await self._publish(topic, command)
        _LOGGER.info(f"已发布命令到 {topic}: {command}")
        
        return True

    async def _publish(self, topic: str, payload: str, qos: int = 1, retain: bool = False):
        try:
            await async_publish(self.hass, topic, payload, qos=qos, retain=retain)
            return True
        except Exception as e:
            _LOGGER.error(f"发布消息到 {topic} 失败: {e}")
            return False

    async def _publish_availability(self, device_id: str, availability: str):
        topic = f"{self.topic_prefix}/{device_id}/{MQTT_TOPIC_AVAILABILITY}"
        await self._publish(topic, availability, retain=True)

    async def _subscribe_to_state_topics(self):
        for device in self.devices_info:
            topic = f"{self.topic_prefix}/{device['_id']}/{MQTT_TOPIC_STATE}"
            subscription = await async_subscribe(
                self.hass,
                topic,
                lambda msg, dev_id=device['_id']: self._handle_state_update(dev_id, msg.payload),
                1
            )
            self._subscriptions.append(subscription)
            _LOGGER.info(f"已订阅状态主题: {topic}")

    def _handle_state_update(self, device_id: str, payload: str):
        try:
            # 解析状态更新
            if isinstance(payload, bytes):
                payload = payload.decode('utf-8')
            
            # 尝试解析JSON格式的状态
            try:
                state_data = json.loads(payload)
                position = state_data.get('position')
            except json.JSONDecodeError:
                # 如果不是JSON格式，直接使用payload作为状态
                position = payload
            
            # 更新设备状态
            for device in self.devices_info:
                if device['_id'] == device_id:
                    old_position = device['position']
                    device['position'] = position
                    _LOGGER.info(f"设备 {device['e_name']} 状态更新: {old_position} -> {position}")
                    
                    # 触发状态更新事件
                    event = Event("gf_device_status_update", {"device_id": device_id, "position": position})
                    self.hass.bus.fire(event.event_type, event.data)
                    break
        except Exception as e:
            _LOGGER.error(f"处理状态更新时出错: {e}")

    @property
    def is_connected(self):
        return self._is_connected