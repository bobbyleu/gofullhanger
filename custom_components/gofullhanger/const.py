# custom_components/gf_cover/const.py
DOMAIN = "gofullhanger"

# 旧的配置选项（保留用于兼容）
CONF_MOBILE = "mobile"
CONF_PASSWORD = "password"
CONF_CLIENTID = "clientid"

# MQTT相关配置选项
CONF_MQTT_BROKER = "mqtt_broker"
CONF_MQTT_PORT = "mqtt_port"
CONF_MQTT_USERNAME = "mqtt_username"
CONF_MQTT_PASSWORD = "mqtt_password"
CONF_MQTT_TOPIC_PREFIX = "mqtt_topic_prefix"

# MQTT主题
MQTT_TOPIC_COMMAND = "command"
MQTT_TOPIC_STATE = "state"
MQTT_TOPIC_AVAILABILITY = "availability"

# 操作命令
MQTT_COMMAND_OPEN = "open"
MQTT_COMMAND_CLOSE = "close"
MQTT_COMMAND_STOP = "stop"

# 设备状态
MQTT_STATE_OPEN = "open"
MQTT_STATE_CLOSED = "closed"
MQTT_STATE_STOPPED = "stopped"
MQTT_STATE_OPENING = "opening"
MQTT_STATE_CLOSING = "closing"

# 可用性状态
MQTT_AVAILABILITY_ONLINE = "online"
MQTT_AVAILABILITY_OFFLINE = "offline"
