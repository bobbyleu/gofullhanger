"""格峰 (Ortron) 云端 Pomelo 协议异步客户端。

协议要点 (均经抓包 + 实测验证):
- TCP 长连接 main.ortron.cn:13015
- 包格式: [type:1][length:3 大端][body]
- 握手: type=1, body={"sys":{"version":"0.3.0","type":"unity-socket"},"user":{}}
  -> 响应 {"code":200,"sys":{"heartbeat":10}}; 随后发送 type=2 (ack, 空 body)
- 心跳: type=3, 空 body, 每 10 秒一次 (服务端约 30 秒无心跳即断开)
- 消息 (type=4): [flag][varint id][1字节路由长度][路由][JSON body]
  flag bit0=路由压缩(0), bits1-3=消息类型 (0请求/1通知/2响应/3推送)
  响应(type=2)不带路由; 推送(type=3)不带 id
- 登录: 请求 connector.userEntryHandler.login
  {mobile, password, packageName:"ypr", clientid} -> 响应带 token
  之后服务端推送 onLoginInfoStart/onServerTime/onHomeInfo/onDeviceStatusData/onLoginInfoEnd
- 控制: 请求 main.userHandler.remoteControll
  {deviceId, props:[{name, method:"set", value:null}]}
- 状态推送: onDeviceStatusData {devices:[{...props...}]}
  设备级执行结果: onDeviceOperationMsg {deviceId, msg:"操作失败"}

本模块不依赖 homeassistant, 可独立测试。
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

_LOGGER = logging.getLogger(__name__)

# 包类型
PKG_HANDSHAKE = 0x01
PKG_HANDSHAKE_ACK = 0x02
PKG_HEARTBEAT = 0x03
PKG_DATA = 0x04
PKG_KICK = 0x05

# 消息类型 (flag bits 1-3)
MSG_REQUEST = 0
MSG_NOTIFY = 1
MSG_RESPONSE = 2
MSG_PUSH = 3

FLAG_ROUTE_COMPRESSED_MASK = 0x01
FLAG_MSG_TYPE_MASK = 0x0E

HANDSHAKE_SYS = {"version": "0.3.0", "type": "unity-socket"}
DEFAULT_HEARTBEAT = 10
DEFAULT_REQUEST_TIMEOUT = 15.0
DEFAULT_LOGIN_TIMEOUT = 30.0
MAX_BACKOFF = 60.0


class GfClientError(Exception):
    """客户端通用错误。"""


class GfAuthError(GfClientError):
    """登录被拒绝 (账号或密码错误)。"""


class GfConnectionError(GfClientError):
    """连接未建立或已断开。"""


def encode_varint(value: int) -> bytes:
    """Pomelo 消息 id 使用 LEB128 varint。"""
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def decode_varint(data: bytes, pos: int) -> tuple[int, int]:
    shift = 0
    value = 0
    while True:
        if pos >= len(data):
            raise GfClientError("truncated varint")
        byte = data[pos]
        value |= (byte & 0x7F) << shift
        pos += 1
        if not byte & 0x80:
            return value, pos
        shift += 7


class GfClient:
    """与格峰云端保持长连接的异步客户端, 支持自动重连。"""

    def __init__(self, host: str, port: int, package_name: str = "ypr") -> None:
        self.host = host
        self.port = port
        self.package_name = package_name
        self.clientid = uuid.uuid4().hex

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._recv_task: asyncio.Task | None = None
        self._hb_task: asyncio.Task | None = None
        self._run_task: asyncio.Task | None = None

        self._should_run = False
        self._connected = False
        self._closed = False
        self._heartbeat_interval = DEFAULT_HEARTBEAT
        self._next_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._push_handlers: dict[str, list] = {}
        self._login_done = asyncio.Event()
        self._logged_in_event = asyncio.Event()
        self._startup_error: GfClientError | None = None
        self._login_data: dict | None = None
        self._creds: tuple[str, str] | None = None

    # ------------------------------------------------------------------ 公共 API

    @property
    def connected(self) -> bool:
        return self._connected

    def add_push_handler(self, route: str, handler) -> None:
        """注册推送处理器: handler(body_dict)。"""
        self._push_handlers.setdefault(route, []).append(handler)

    async def connect(
        self,
        mobile: str,
        password: str,
        clientid: str | None = None,
        timeout: float = DEFAULT_LOGIN_TIMEOUT,
    ) -> dict:
        """启动客户端并等待登录完成 (含初始数据推送)。

        失败抛出 GfAuthError (凭据错误) 或 GfClientError (网络/超时)。
        """
        if clientid:
            self.clientid = clientid
        self._creds = (mobile, password)
        self._should_run = True
        self._closed = False
        self._startup_error = None
        self._logged_in_event.clear()

        self._run_task = asyncio.create_task(self._run())
        try:
            await asyncio.wait_for(self._logged_in_event.wait(), timeout)
        except asyncio.TimeoutError as err:
            await self.close()
            raise GfClientError(f"等待登录超时: {err}") from err

        if self._startup_error is not None:
            error = self._startup_error
            await self.close()
            raise error
        return self._login_data or {}

    async def close(self) -> None:
        """停止客户端并关闭连接。"""
        self._should_run = False
        self._closed = True
        if self._run_task and not self._run_task.done():
            self._run_task.cancel()
            try:
                await self._run_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        await self._teardown_connection()
        # 唤醒所有等待者
        for future in list(self._pending.values()):
            if not future.done():
                future.set_exception(GfConnectionError("client closed"))
        self._pending.clear()

    async def request(self, route: str, msg, timeout: float = DEFAULT_REQUEST_TIMEOUT):
        """发送请求并等待响应, 返回响应 body (已解析 JSON)。"""
        if not self._connected or self._writer is None:
            raise GfConnectionError("未连接到服务器")
        self._next_id += 1
        mid = self._next_id
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[mid] = future
        try:
            body = json.dumps(msg, separators=(",", ":")) if msg is not None else ""
            await self._send(MSG_REQUEST, mid, route, body)
            return await asyncio.wait_for(future, timeout)
        finally:
            self._pending.pop(mid, None)

    async def notify(self, route: str, msg) -> None:
        """发送通知 (无响应)。"""
        if not self._connected or self._writer is None:
            raise GfConnectionError("未连接到服务器")
        body = json.dumps(msg, separators=(",", ":")) if msg is not None else ""
        await self._send(MSG_NOTIFY, None, route, body)

    async def remote_control(self, device_id: str, name: str, value=None) -> dict:
        """发送设备控制指令, 返回云端响应 body。"""
        return await self.request(
            "main.userHandler.remoteControll",
            {"deviceId": device_id, "props": [{"name": name, "method": "set", "value": value}]},
        )

    # ------------------------------------------------------------------ 连接管理

    async def _run(self) -> None:
        backoff = 5.0
        first_attempt = True
        while self._should_run:
            try:
                await self._establish()
                first_attempt = False
                backoff = 5.0
                # 阻塞直到连接断开
                await self._recv_task
            except asyncio.CancelledError:
                raise
            except GfAuthError as err:
                # 首次: connect() 会向上抛; 运行中: 账号密码可能已变更,
                # 不再无限退避重试, 停止客户端让实体转为不可用, 提示用户重新配置
                _LOGGER.error("登录被拒绝: %s (如账号密码已变更, 请在集成条目上「重新配置」)", err)
                self._startup_error = err
                self._logged_in_event.set()
                return
            except Exception as err:  # noqa: BLE001
                if first_attempt:
                    self._startup_error = GfClientError(str(err))
                    self._logged_in_event.set()
                    return
                _LOGGER.warning("连接断开 (%s), %.0f 秒后重连", err, backoff)
            finally:
                self._connected = False
                await self._teardown_connection()

            if not self._should_run:
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)

    async def _establish(self) -> None:
        self._reader, self._writer = await asyncio.open_connection(self.host, self.port)
        _LOGGER.debug("已连接 %s:%s", self.host, self.port)

        # 握手
        hs_body = json.dumps(
            {"sys": HANDSHAKE_SYS, "user": {}}, separators=(",", ":")
        ).encode()
        await self._write_package(PKG_HANDSHAKE, hs_body)
        ptype, body = await self._read_package()
        if ptype != PKG_HANDSHAKE:
            raise GfClientError(f"握手指令响应类型异常: {ptype}")
        info = json.loads(body.decode())
        if info.get("code") != 200:
            raise GfClientError(f"握手失败: {info}")
        self._heartbeat_interval = info.get("sys", {}).get("heartbeat", DEFAULT_HEARTBEAT)
        await self._write_package(PKG_HANDSHAKE_ACK, b"")
        self._connected = True  # 登录请求发生在 _establish 内部, 须先置位
        _LOGGER.debug("握手成功, 心跳间隔 %ss", self._heartbeat_interval)

        # 启动接收/心跳任务
        self._recv_task = asyncio.create_task(self._receive_loop())
        self._hb_task = asyncio.create_task(self._heartbeat_loop())

        # 登录并等待初始数据
        self._login_data = await self._login()
        self._logged_in_event.set()

    async def _login(self) -> dict:
        if self._creds is None:
            raise GfClientError("未提供登录凭据")
        mobile, password = self._creds
        self._login_done.clear()
        resp = await self.request(
            "connector.userEntryHandler.login",
            {
                "mobile": mobile,
                "password": password,
                "packageName": self.package_name,
                "clientid": self.clientid,
            },
            timeout=DEFAULT_LOGIN_TIMEOUT,
        )
        if resp.get("code") != 200:
            codetxt = resp.get("codetxt", "")
            raise GfAuthError(f"登录失败 (code={resp.get('code')}): {codetxt}")
        # 等待服务端推送完初始数据 (onLoginInfoEnd)
        try:
            await asyncio.wait_for(self._login_done.wait(), timeout=20.0)
        except asyncio.TimeoutError:
            _LOGGER.debug("未在时限内收到 onLoginInfoEnd, 继续等待推送")
        return resp

    async def _teardown_connection(self) -> None:
        for task in (self._hb_task, self._recv_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):  # noqa: BLE001
                    pass
        self._hb_task = None
        self._recv_task = None
        writer, self._writer = self._writer, None
        self._reader = None
        if writer is not None:
            try:
                writer.close()
                await asyncio.wait_for(writer.wait_closed(), timeout=2.0)
            except (asyncio.TimeoutError, Exception):  # noqa: BLE001
                pass
        # 断开时唤醒所有挂起请求
        for future in list(self._pending.values()):
            if not future.done():
                future.set_exception(GfConnectionError("连接已断开"))
        self._pending.clear()

    # ------------------------------------------------------------------ 收发

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            if self._writer is None:
                return
            try:
                await self._write_package(PKG_HEARTBEAT, b"")
            except (ConnectionError, OSError) as err:
                _LOGGER.debug("心跳发送失败: %s", err)
                return

    async def _receive_loop(self) -> None:
        assert self._reader is not None
        buffer = b""
        while True:
            data = await self._reader.read(65536)
            if not data:
                raise ConnectionError("服务端关闭了连接")
            buffer += data
            while len(buffer) >= 4:
                ptype = buffer[0]
                length = int.from_bytes(buffer[1:4], "big")
                if len(buffer) < 4 + length:
                    break
                body = buffer[4 : 4 + length]
                buffer = buffer[4 + length :]
                await self._handle_package(ptype, body)

    async def _handle_package(self, ptype: int, body: bytes) -> None:
        if ptype == PKG_HEARTBEAT:
            return  # 服务端心跳回应
        if ptype == PKG_KICK:
            _LOGGER.warning("服务端踢出会话 (kick), 将重连")
            raise ConnectionError("kicked by server")
        if ptype != PKG_DATA:
            _LOGGER.debug("忽略未知包类型 %d", ptype)
            return

        if not body:
            return
        flag = body[0]
        msg_type = (flag & FLAG_MSG_TYPE_MASK) >> 1
        route_compressed = flag & FLAG_ROUTE_COMPRESSED_MASK
        pos = 1
        mid = None
        route = None

        if msg_type in (MSG_REQUEST, MSG_RESPONSE):
            mid, pos = decode_varint(body, pos)
        if msg_type in (MSG_REQUEST, MSG_NOTIFY, MSG_PUSH):
            if route_compressed:
                pos += 2  # 字典压缩路由, 本服务端未启用
                route = "<compressed>"
            else:
                rlen = body[pos]
                pos += 1
                route = body[pos : pos + rlen].decode("utf-8", "replace")
                pos += rlen

        payload = body[pos:]
        try:
            data = json.loads(payload.decode("utf-8")) if payload else None
        except (ValueError, UnicodeDecodeError):
            _LOGGER.debug("消息体非 JSON: %r", payload[:120])
            return

        if msg_type == MSG_RESPONSE:
            future = self._pending.get(mid)
            if future is not None and not future.done():
                future.set_result(data)
            return

        if msg_type == MSG_PUSH and route:
            if route == "onLoginInfoEnd":
                self._login_done.set()
            self._dispatch_push(route, data)

    def _dispatch_push(self, route: str, body) -> None:
        for handler in self._push_handlers.get(route, []):
            try:
                handler(body)
            except Exception as err:  # noqa: BLE001
                _LOGGER.exception("处理推送 %s 出错: %s", route, err)

    async def _send(self, msg_type: int, mid, route: str, body: str) -> None:
        flag = (msg_type << 1) & 0xFF  # 路由不压缩
        parts = bytearray([flag])
        if msg_type in (MSG_REQUEST, MSG_RESPONSE) and mid is not None:
            parts += encode_varint(mid)
        if msg_type in (MSG_REQUEST, MSG_NOTIFY, MSG_PUSH):
            route_bytes = route.encode("utf-8")
            parts.append(len(route_bytes))
            parts += route_bytes
        parts += body.encode("utf-8")
        await self._write_package(PKG_DATA, bytes(parts))

    async def _write_package(self, ptype: int, body: bytes) -> None:
        if self._writer is None:
            raise GfConnectionError("连接未建立")
        header = bytes([ptype]) + len(body).to_bytes(3, "big")
        self._writer.write(header + body)
        await self._writer.drain()

    async def _read_package(self):
        assert self._reader is not None
        header = await self._reader.readexactly(4)
        ptype = header[0]
        length = int.from_bytes(header[1:4], "big")
        body = await self._reader.readexactly(length) if length else b""
        return ptype, body
