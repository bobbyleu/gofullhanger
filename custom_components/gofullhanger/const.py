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
CMD_CLOSE = "close"           # 关闭所有功能
CMD_STERILIZE = "sterilize"   # 消毒
CMD_AIRDRYING = "airdrying"   # 风干
CMD_DRYING = "drying"         # 烘干
CMD_LIGHTING = "lighting"     # 照明 (部分机型无此硬件)

# ---- props.position 取值 (实测) ----
POS_TOP = "0"          # 收起 (最高位)
POS_MID = "1"          # 中位
POS_BOTTOM = "2"       # 放下 (最低位)
POS_ASCENDING = "3"    # 上升中
POS_DESCENDING = "4"   # 下降中

# ---- 功能开关 (prop key, 名称, 图标) ----
SWITCH_FUNCTIONS = (
    (CMD_STERILIZE, "消毒", "mdi:shield-check"),
    (CMD_AIRDRYING, "风干", "mdi:weather-windy"),
    (CMD_DRYING, "烘干", "mdi:heat-wave"),
)

MANUFACTURER = "格峰"
