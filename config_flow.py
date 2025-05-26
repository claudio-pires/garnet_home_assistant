"""Config flow for Garnet Panel Integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .api import GarnetAPI, APIConnectionError
from .const import DOMAIN, CONF_ACCOUNT, CONF_SYSTEM, CONF_GARNETUSER, CONF_GARNETPASS, MIN_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL


_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_GARNETUSER): str,
        vol.Required(CONF_GARNETPASS): str,
        vol.Required(CONF_SYSTEM): str,
        vol.Required(CONF_ACCOUNT, description={"suggested_value": "0001"}): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    _LOGGER.debug("**** validate_input")
    api = GarnetAPI(hass, data[CONF_GARNETUSER], data[CONF_GARNETPASS], data[CONF_ACCOUNT], data[CONF_SYSTEM])
    try:
       await hass.async_add_executor_job(api.connect)
    except APIConnectionError as err:
        _LOGGER.exception(err)
        raise CannotConnect from err
    return {"title": f"Garnet Panel Integration - {data[CONF_SYSTEM]}"}


class GarnetIntConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handles the config flow for Garnet Panel Integration."""

    VERSION = 1
    _input_data: dict[str, Any]

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        _LOGGER.info("GarnetIntConfigFlow->async_get_options_flow()")
        return GarnetIntOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step. Called when you initiate adding an integration via the UI."""
        _LOGGER.info("GarnetIntConfigFlow->async_step_user()")
        errors: dict[str, str] = {}
        if user_input is not None:
            # The form has been filled in and submitted, so process the data provided.
            try:
                # Validate that the setup data is valid and if not handle errors.
                # The errors["base"] values match the values in your strings.json and translation files.
                info = await validate_input(self.hass, user_input)
            except CannotConnect as err: 
                _LOGGER.exception(err)
                errors["base"] = "cannot_connect"
            except InvalidAuth as err: 
                _LOGGER.exception(err)
                errors["base"] = "invalid_auth"
            except Exception as err:    # pylint: disable=broad-except
                _LOGGER.exception(err)
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if "base" not in errors:
                # Validation was successful, so create a unique id for this instance of your integration
                # and create the config entry.
                await self.async_set_unique_id(info.get("title"))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        # Show initial form.
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Add reconfigure step to allow to reconfigure a config entry."""
        # This methid displays a reconfigure option in the integration and is different to options.
        # It can be used to reconfigure any of the data submitted when first installed. This is optional and can be removed if you do not want to allow reconfiguration.
        _LOGGER.error("**** async_step_reconfigure")
        errors: dict[str, str] = {}
        config_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )

        if user_input is not None:
            try:
                user_input[CONF_SYSTEM] = config_entry.data[CONF_SYSTEM]
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    config_entry,
                    unique_id=config_entry.unique_id,
                    data={**config_entry.data, **user_input},
                    reason="reconfigure_successful",
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
#                    vol.Required(
#                        CONF_GARNETUSER, default=config_entry.data[CONF_GARNETUSER]
#                    ): str,
                    vol.Required(
                        CONF_GARNETPASS, default=config_entry.data[CONF_GARNETPASS]
                    ): str,
                }
            ),
            errors=errors,
        )


class GarnetIntOptionsFlowHandler(OptionsFlow):
    """Handles the options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        _LOGGER.error("**** __init__")
        #self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        _LOGGER.error("**** async_step_init")
        if user_input is not None:
            options = self.config_entry.options | user_input
            return self.async_create_entry(title="", data=options)

        # It is recommended to prepopulate options fields with default values if available.
        # These will be the same default values you use on your coordinator for setting variable values
        # if the option has not been set.
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=self.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): (vol.All(vol.Coerce(int), vol.Clamp(min=MIN_SCAN_INTERVAL))),
            }
        )

        return self.async_show_form(step_id="init", data_schema=data_schema)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
