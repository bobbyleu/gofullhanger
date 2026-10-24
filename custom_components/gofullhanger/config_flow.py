"""格峰晾衣架配置流程。"""

from __future__ import annotations

import uuid
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_CLIENTID,
    CONF_MOBILE,
    CONF_PASSWORD,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DOMAIN,
    PACKAGE_NAME,
)
from .gf_client import GfAuthError, GfClient, GfClientError

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MOBILE): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _validate(mobile: str, password: str) -> None:
    """尝试登录一次以校验凭据。失败抛出对应异常。"""
    client = GfClient(DEFAULT_HOST, DEFAULT_PORT, PACKAGE_NAME)
    try:
        await client.connect(mobile, password, uuid.uuid4().hex, timeout=30)
    finally:
        await client.close()


class GfHangerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            mobile = user_input[CONF_MOBILE].strip()
            password = user_input[CONF_PASSWORD]
            await self.async_set_unique_id(mobile)
            self._abort_if_unique_id_configured()
            try:
                await _validate(mobile, password)
            except GfAuthError:
                errors["base"] = "invalid_auth"
            except (GfClientError, OSError):
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"
            if not errors:
                return self.async_create_entry(
                    title="格峰晾衣架",
                    data={
                        CONF_MOBILE: mobile,
                        CONF_PASSWORD: password,
                        CONF_CLIENTID: uuid.uuid4().hex,
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(self, user_input=None):
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            mobile = user_input[CONF_MOBILE].strip()
            password = user_input[CONF_PASSWORD]
            try:
                await _validate(mobile, password)
            except GfAuthError:
                errors["base"] = "invalid_auth"
            except (GfClientError, OSError):
                errors["base"] = "cannot_connect"
            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data={
                        **entry.data,
                        CONF_MOBILE: mobile,
                        CONF_PASSWORD: password,
                    },
                    title="格峰晾衣架",
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MOBILE, default=entry.data.get(CONF_MOBILE)
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return GfHangerOptionsFlowHandler(config_entry)


class GfHangerOptionsFlowHandler:
    """选项流: 目前仅提供重新配置入口说明。"""

    def __init__(self, config_entry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        return self.async_create_entry(title="", data={})
