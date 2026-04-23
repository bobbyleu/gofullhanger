import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .const import (
    CONF_MQTT_BROKER,
    CONF_MQTT_PORT,
    CONF_MQTT_USERNAME,
    CONF_MQTT_PASSWORD,
    CONF_MQTT_TOPIC_PREFIX,
)

class GfHangerConfigFlow(config_entries.ConfigFlow, domain="gofullhanger"):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title="Gf Hanger MQTT",
                data={
                    CONF_MQTT_BROKER: user_input[CONF_MQTT_BROKER],
                    CONF_MQTT_PORT: user_input[CONF_MQTT_PORT],
                    CONF_MQTT_USERNAME: user_input.get(CONF_MQTT_USERNAME),
                    CONF_MQTT_PASSWORD: user_input.get(CONF_MQTT_PASSWORD),
                    CONF_MQTT_TOPIC_PREFIX: user_input.get(CONF_MQTT_TOPIC_PREFIX, "gofullhanger"),
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_MQTT_BROKER): str,
                vol.Required(CONF_MQTT_PORT, default=1883): int,
                vol.Optional(CONF_MQTT_USERNAME): str,
                vol.Optional(CONF_MQTT_PASSWORD): str,
                vol.Optional(CONF_MQTT_TOPIC_PREFIX, default="gofullhanger"): str,
            }),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return GfHangerOptionsFlowHandler(config_entry)

class GfHangerOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_MQTT_BROKER: user_input[CONF_MQTT_BROKER],
                    CONF_MQTT_PORT: user_input[CONF_MQTT_PORT],
                    CONF_MQTT_USERNAME: user_input.get(CONF_MQTT_USERNAME),
                    CONF_MQTT_PASSWORD: user_input.get(CONF_MQTT_PASSWORD),
                    CONF_MQTT_TOPIC_PREFIX: user_input.get(CONF_MQTT_TOPIC_PREFIX, "gofullhanger"),
                },
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_MQTT_BROKER, default=self._config_entry.data.get(CONF_MQTT_BROKER)): str,
                vol.Required(CONF_MQTT_PORT, default=self._config_entry.data.get(CONF_MQTT_PORT, 1883)): int,
                vol.Optional(CONF_MQTT_USERNAME, default=self._config_entry.data.get(CONF_MQTT_USERNAME)): str,
                vol.Optional(CONF_MQTT_PASSWORD, default=self._config_entry.data.get(CONF_MQTT_PASSWORD)): str,
                vol.Optional(CONF_MQTT_TOPIC_PREFIX, default=self._config_entry.data.get(CONF_MQTT_TOPIC_PREFIX, "gofullhanger")): str,
            }),
        )
