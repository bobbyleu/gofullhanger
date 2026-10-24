# custom_components/gofullhanger/const.py
"""Constants for the gofullhanger (格峰晾衣架) integration."""

DOMAIN = "gofullhanger"

CONF_MOBILE = "mobile"
CONF_PASSWORD = "password"
CONF_CLIENTID = "clientid"

# 格峰/Ortron 云端 (Pomelo over TCP)
DEFAULT_HOST = "main.ortron.cn"
DEFAULT_PORT = 13015
PACKAGE_NAME = "ypr"

# ---- Pomelo 路由 ----
ROUTE_LOGIN = "connector.userEntryHandler.login"
ROUTE_REMOTE_CONTROL = "main.userHandler.remoteControll"

# ---- 服务端推送 ----
PUSH_HOME_INFO = "onHomeInfo"
PUSH_DEVICE_STATUS = "onDeviceStatusData"
PUSH_DEVICE_OPERATION = "onDeviceOperationMsg"
PUSH_LOGIN_INFO_END = "onLoginInfoEnd"

# ---- 设备过滤 ----
DEVICE_TYPE_HANGER = "hanger"
SUPPORTED_MODEL = "hanger_ypr"  # WiFi 直连晾衣机 (射频版 hanger_sp 等不走本协议)

# ---- 控制指令 (remoteControll props.name) ----
CMD_RAISE_UP = "raiseUp"      # 上升 / 收起
CMD_PUT_DOWN = "putDown"      # 下降 / 放下
CMD_STOP = "stop"             # 停止
CMD_CLOSE = "close"           # 关闭所有功能 (预留: 当前版本无实体使用)
CMD_STERILIZE = "sterilize"   # 消毒
CMD_AIRDRYING = "airdrying"   # 风干
CMD_DRYING = "drying"         # 烘干

# ---- props.position 取值 (实测: 一号, 机械模型验证) ----
# 机器运行停止后反馈三个固定档位, 运动中反馈两个状态
POS_UPPER_STOP = "0"    # 上升停止位 (下降停止位+上升的常规停止点)
POS_HIDDEN = "1"        # 隐藏位 (最高, 完全收起; 上升停止位再上升才到位)
POS_LOWER_STOP = "2"    # 下降停止位 (最低, 完全放下)
POS_ASCENDING = "3"     # 上升中
POS_DESCENDING = "4"    # 下降中

# 反馈码 -> 档位名称 (实体属性 position_name 用)
POSITION_NAMES = {
    POS_UPPER_STOP: "上升停止位",
    POS_HIDDEN: "隐藏位",
    POS_LOWER_STOP: "下降停止位",
    POS_ASCENDING: "上升中",
    POS_DESCENDING: "下降中",
}

# ---- 功能开关 (prop key, 名称, 图标) ----
# 对应实体默认在注册表禁用 (基础型号硬件不支持), 见 switch.py 与 README
SWITCH_FUNCTIONS = (
    (CMD_STERILIZE, "消毒", "mdi:shield-check"),
    (CMD_AIRDRYING, "风干", "mdi:weather-windy"),
    (CMD_DRYING, "烘干", "mdi:heat-wave"),
)

MANUFACTURER = "格峰"
