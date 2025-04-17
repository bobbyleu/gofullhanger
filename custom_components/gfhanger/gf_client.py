import asyncio
import json
import logging
from homeassistant.core import Event

# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
_LOGGER = logging.getLogger(__name__)

SEQUENCE_NUMBER = 0

class GfClient:
    def __init__(self, host, port, hass, max_retries=3):
        self.hass = hass
        self.host = host
        self.port = port
        self.recv_buffer = b""
        self.login_event = asyncio.Event()
        self.last_sent_type = None
        self.response_received = asyncio.Event()
        self.last_operation = None
        self.receive_task = None
        self.last_on_home_info = {}
        self.devices_info = []
        self.on_device_status_count = 0
        self.operation_success = False
        self.should_exit = False
        self.max_retries = max_retries
        # 新增变量，用于判断服务器连接是否断开
        self.is_connection_closed = False
        # 操作结束
        self.operation_ended_event = asyncio.Event()


    async def connect(self):
        if self.receive_task and not self.receive_task.done():
            return True  # 已经连接，直接返回
        retries = 0
        while retries < self.max_retries:
            try:
                self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
                self._log_info(f"已连接到服务器 {self.host}:{self.port}")
                self.receive_task = asyncio.create_task(self.receive_messages())
                self.is_connection_closed = False  # 连接成功，将连接断开标志置为 False
                return True
            except ConnectionError as e:
                self._log_error(f"连接服务器失败: {e}, 重试第 {retries + 1} 次")
                retries += 1
        self._log_error("达到最大重试次数，连接失败")
        self._exit_program()
        self.is_connection_closed = True  # 连接失败，将连接断开标志置为 True
        return False

    def close(self):
        if self.receive_task:
            self.receive_task.cancel()
        if self.writer:
            self.writer.close()
        self._log_info("连接已关闭")
        self._exit_program()
        self.is_connection_closed = True  # 关闭连接，将连接断开标志置为 True

    async def send_message(self, hex_str, operation=None, retries=0):
        if self.is_connection_closed:
            if not await self.connect():
                return
        try:
            message_bytes = bytes.fromhex(hex_str)
            self.writer.write(message_bytes)
            await self.writer.drain()
            self.last_sent_type = hex_str[:4]
            self.response_received.clear()
            self.last_operation = operation
            # self._log_info(f"发送: {hex_str}")
        except ValueError as e:
            self._log_error(f"无效的十六进制消息: {hex_str}")
        except ConnectionError as e:
            if retries < self.max_retries:
                self._log_error(f"发送消息时连接错误: {e}, 尝试重新连接并再次发送")
                if await self.connect():
                    await self.send_message(hex_str, operation, retries + 1)
            else:
                self._log_error("达到最大重试次数，发送消息失败")
                self._exit_program()

    async def receive_messages(self):
        incomplete_message = b""
        while not self.should_exit:
            try:
                if self.is_connection_closed:
                    break
                data = await self.reader.read(4096)
                if not data:
                    self._log_info("服务器断开连接")
                    self.is_connection_closed = True  # 服务器断开连接，将连接断开标志置为 True
                    break
                self.recv_buffer += data
                self._log_info(f"原始接收: {self.recv_buffer.hex()}")
                while len(self.recv_buffer) > 0:
                    if len(self.recv_buffer) < 4:
                        incomplete_message += self.recv_buffer
                        self.recv_buffer = b""
                        break
                    data_type_hex = self.recv_buffer[:2].hex()
                    if data_type_hex in ["0100", "0300", "0400"]:
                        if incomplete_message:
                            self.recv_buffer = incomplete_message + self.recv_buffer
                            incomplete_message = b""
                        length_hex = self.recv_buffer[2:4].hex()
                        data_length = int(length_hex, 16)
                        total_length = 4 + data_length
                        if len(self.recv_buffer) >= total_length:
                            message = self.recv_buffer[:total_length]
                            if not self.is_connection_closed:
                                self.process_complete_message(message)
                            self.recv_buffer = self.recv_buffer[total_length:]
                            self.response_received.set()
                    else:
                        incomplete_message += self.recv_buffer[:1]
                        self.recv_buffer = self.recv_buffer[1:]

            except Exception as e:
                self._log_error(f"接收消息出错: {str(e)}，当前 recv_buffer: {self.recv_buffer}")

        if incomplete_message and not self.is_connection_closed:
            self.process_complete_message(incomplete_message)

    def process_complete_message(self, message):
        data_type = message[:2].hex()
        if data_type == "0300":
            self._log_info(f"收到心跳数据，原始数据: {message.hex()}")
            return

        length_hex = message[2:4].hex()
        data_length = 4 + int(length_hex, 16)
        content = message[4:data_length]
        if data_type == "0400":
            content = message[6:data_length]

        try:
            content_str = content.decode('utf-8')
            if content_str.strip():
                index_dict = content_str.find('{')
                index_list = content_str.find('[')

                if index_dict != -1 or index_list != -1:
                    if index_dict == -1:
                        start_index = index_list
                    elif index_list == -1:
                        start_index = index_dict
                    else:
                        start_index = min(index_dict, index_list)

                    method = content_str[:start_index]
                    json_str = content_str[start_index:]
                    try:
                        parsed_content = json.loads(json_str)
                        self._log_info(f"解析成功: {data_type} 消息解析结果 - 方法: {method}, 内容: {parsed_content}")

                        if method == "onHomeInfo":
                            self._process_on_home_info(parsed_content)
                        elif method == "onLoginInfoEnd":
                            self._process_on_login_info_end(parsed_content)
                        elif method == "onDeviceStatusData":
                            # 当字典中有originUid字段时，跳过不设置设备位置状态
                            if 'originUid' in parsed_content:
                                self._log_info(f"原始状态获取成功,直接返回")
                                return

                            device = parsed_content.get('devices', [])[0]
                            if device:
                                e_name = device.get('e_name')
                                _id = device.get('_id')
                                status = device.get('props', {}).get('status')
                                position = device.get('props', {}).get('position')
                                event = Event("gf_device_status_update", {"device_id": _id, "position": position})
                                self.hass.bus.fire(event.event_type, event.data)


                                # 根据 _id 更新 devices_info 中对应设备的 position 值
                                for dev in self.devices_info:
                                    if dev.get('_id') == _id:
                                        dev['position'] = position
                                        self._log_info(f"更新设备 {e_name} 的位置为 {position}")
                                        break

                                # 当postion值为3或者4时，不设置设备位置状态
                                if position in ['3', '4']:
                                    status_msg = "上升中" if position == '3' else "下降中"
                                    self._log_info(f"{e_name} {status_msg}，位置显示 {position}")
                                    return

                                if position in ['0', '1', '2']:
                                    self.operation_ended_event.set()
                                    self._log_info(f"{e_name} 运行完成，位置显示 {position}")

                        if data_type == "0400" and len(message) >= 5 and message[4] == 0x04:
                            self._process_operation_feedback(parsed_content)

                    except json.JSONDecodeError:
                        self._log_error(f"消息内容不是有效的 JSON 格式: {json_str}")
                else:
                    self._log_error(f"未找到有效的 JSON 起始标识，内容为: {content_str}")
            else:
                self._log_error("接收到的消息内容为空，无法解析")
        except UnicodeDecodeError:
            self._log_error(f"消息解码错误: 原始数据: {content.hex()}")

    def _process_on_home_info(self, parsed_content):
        self.last_on_home_info = parsed_content
        self.devices_info = []
        homes = parsed_content.get('homes', [])
        for home in homes:
            layers = home.get('layers', [])
            for layer in layers:
                home_grids = layer.get('homeGrids', [])
                for home_grid in home_grids:
                    devices = home_grid.get('devices', [])
                    for device in devices:
                        e_name = device.get('e_name')
                        _id = device.get('_id')
                        status = device.get('props', {}).get('status')
                        position = device.get('props', {}).get('position')
                        if e_name and _id and status is not None and position is not None:
                            self.devices_info.append({
                                'e_name': e_name,
                                '_id': _id,
                                'status': status,
                                'position': position,
                            })
        self._log_info(f"设备如下：")
        self._log_info(f"--{self.devices_info[0]}")
        self._log_info(f"--{self.devices_info[1]}")
        if not self.devices_info:
            self._log_error("未从 onHomeInfo 中获取到设备信息，关闭连接并退出程序")
            self.close()

    def _process_on_login_info_end(self, parsed_content):
        code = parsed_content.get('code')
        if code == 200:
            self._log_info("登录成功")
            self.login_event.set()
        else:
            self._log_error("登录失败")
            self.close()

    def _process_operation_feedback(self, parsed_content):
        if self.is_connection_closed:
            return
        code = parsed_content.get('code')
        codetxt = parsed_content.get('codetxt')
        self._log_info(f"操作反馈信息 - code: {code}, codetxt: {codetxt}")
        self.operation_success = code == 200
        if code != 200:
            self._log_error("操作返回码非 200，关闭连接并退出程序")
            self.close()
        elif self.last_operation == 'remote_control' and not self.operation_success:
            self._log_info("设备操作失败")

    def generate_hex_message(self, method_name, data, is_operation_command=False):
        global SEQUENCE_NUMBER
        SEQUENCE_NUMBER += 1
        sequence_hex = format(SEQUENCE_NUMBER, '04X')

        method_hex = method_name.encode('utf-8').hex().upper()
        json_hex = json.dumps(data, separators=(',', ':')).encode('utf-8').hex().upper()

        middle_part = "20" if not is_operation_command else "1F"
        full_content_hex = sequence_hex + middle_part + method_hex + json_hex
        length_hex = format(len(full_content_hex) // 2, '04X')

        return f"0400{length_hex}{full_content_hex}"

    async def login(self, mobile, password, clientid):
        if not await self.connect():
            return False
        await self.send_message(
            "0100003B7B22737973223A7B2276657273696F6E223A22302E332E30222C2274797065223A22756E6974792D736F636B6574227D2C2275736572223A7B7D7D")
        # 限制等待时间为 2 秒
        await asyncio.wait_for(self.response_received.wait(), timeout=1)

        await self.send_message("02000000")
        # 限制等待时间为 2 秒
        await asyncio.wait_for(self.response_received.wait(), timeout=1)

        method_name = "connector.userEntryHandler.login"
        login_data = {
            "mobile": mobile,
            "password": password,
            "packageName": "ypr",
            "clientid": clientid
        }

        hex_message = self.generate_hex_message(method_name, login_data)
        await self.send_message(hex_message, operation='login')
        await asyncio.wait_for(self.response_received.wait(), timeout=1)

        try:
            await asyncio.wait_for(self.login_event.wait(), timeout=1)
            return True
        except asyncio.TimeoutError:
            self._log_error("登录超时，请检查网络或服务器状态。")
            self.close()
            return False

    async def remote_control(self, mobile, password, clientid, deviceId, operation_code):
        operation_mapping = {
            1: "putDown",
            2: "raiseUp",
            3: "stop"
        }
        name = operation_mapping.get(operation_code)

        # 判断连接是否断开
        if self.is_connection_closed:
            self._log_info("连接已断开，尝试重新连接并登录...")
            if not await self.login(mobile, password, clientid):
                return False

        # 重置事件
        self.on_device_status_count = 0
        self.operation_success = False
        self.operation_ended_event.clear()

        method_name = "main.userHandler.remoteControll"
        control_data = {
            "deviceId": deviceId,
            "props": [{"name": name, "method": "set", "value": None}]
        }

        hex_message = self.generate_hex_message(method_name, control_data, is_operation_command=True)
        await self.send_message(hex_message, operation='remote_control')
        return True

    def _log_info(self, message):
        _LOGGER.info(message)

    def _log_error(self, message):
        _LOGGER.error(message)

    def _exit_program(self):
        self.should_exit = True