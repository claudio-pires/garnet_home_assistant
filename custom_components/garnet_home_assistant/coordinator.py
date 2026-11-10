"""Garnet integration using DataUpdateCoordinator."""


import logging
from dataclasses import dataclass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import DOMAIN, HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .api import APIAuthError, GarnetAPI
from .const import (
    CONF_ACCOUNT,
    CONF_GARNETPASS,
    CONF_GARNETUSER,
    CONF_GARNET_SESSION_TTL,
    CONF_KEEPALIVE_INTERVAL,
    CONF_REFRESH_INTERVAL,
    CONF_SYSTEM,
    DEFAULT_GARNET_SESSION_TTL,
    DEFAULT_KEEPALIVE_INTERVAL,
    DEFAULT_REFRESH_INTERVAL,
)
from .httpapi import DeviceType, GarnetEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class APIData:
    """Class to hold api data."""

    controller_name: str
    devices: list[GarnetEntity]


class GarnetPanelIntegrationCoordinator(DataUpdateCoordinator):
    """Garnet Panel Integration coordinator."""

    data: APIData

    def __init__(self, _hass: HomeAssistant, _config_entry: ConfigEntry) -> None:
        """Initializes the coordinator."""

        self.account = _config_entry.data[CONF_ACCOUNT]
        self.systemid = _config_entry.data[CONF_SYSTEM]
        self.user = _config_entry.data[CONF_GARNETUSER]
        self.pwd = _config_entry.data[CONF_GARNETPASS]
        self.uniqueid = _config_entry.unique_id

        _LOGGER.info("\n===================================================================================================\n Garnet Alarm Panels integration for Home Assistant\n https://github.com/claudio-pires/garnet_home_assistant\n This integration is not affiliated with or endorsed by Garnet Security Systems.\n It has been created monitoring comunication protocols with no documentation from\n Garnet Technology and tested with a Garnet PC-732-G panel with a 500G communication module\n This integration is provided as-is and without warranty. Use at your own risk.\n Feel free to share your logs to support your configuration and/or contribute for the project.\n===================================================================================================")

        _LOGGER.debug("Initializing GarnetPanelIntegrationCoordinator with account=%s, systemid=%s, user=%s, pwd=%s and uniqueid=%s", self.account, self.systemid, self.user, "*" * len(self.pwd), self.uniqueid)

        super().__init__(_hass, _LOGGER, name=f"{DOMAIN} ({self.uniqueid})", update_method=self.update_data, update_interval=None)  # Initialise DataUpdateCoordinator
                                                                                                                                    # update_method is the update method
                                                                                                                                    # to get devices on first load.
                                                                                                                                    # update_interval = None makes data will be pushed.
        self.api = GarnetAPI(hass=_hass, user=self.user, pwd=self.pwd, account=self.account, systemid=self.systemid, uniqueid=self.uniqueid)
        self.api.keepalive_interval = int(_config_entry.options.get(CONF_KEEPALIVE_INTERVAL, DEFAULT_KEEPALIVE_INTERVAL))
        self.api.refresh_interval = int(_config_entry.options.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL))
        self.api.tokenlifespan = int(_config_entry.options.get(CONF_GARNET_SESSION_TTL, DEFAULT_GARNET_SESSION_TTL))
        self.api.setcallback(message_callback=self.devices_update_callback)


    def get_device_info(self) -> DeviceInfo | None:
        """Return device info for panel."""

        panel = self.api.httpapi.system
        if panel is not None:
            return DeviceInfo(name = f"{panel.name} ({panel.id})", manufacturer = panel.manufacturer, model = panel.modelName, sw_version = panel.versionName, identifiers = {(DOMAIN, f"{DOMAIN} ({self.uniqueid})")})
        return None

    def devices_update_callback(self, devs: list[GarnetEntity]):
        """Receive callback from api with device update."""

        _LOGGER.debug("Updating devices status...")
        self.async_set_updated_data(APIData(self.api.controller_name, devs))


    async def update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            if not self.api.connected:
                await self.hass.async_add_executor_job(self.api.connect)
            devices = await self.hass.async_add_executor_job(self.api.get_devices)
        except APIAuthError as err:
            _LOGGER.exception("Exception")
            raise UpdateFailed(err) from err
        except Exception as err:
            # This will show entities as unavailable by raising UpdateFailed exception
            _LOGGER.exception("Exception")
            raise UpdateFailed(f"Error on Garnet API communication: {err}") from err

        # What is returned here is stored in self.data by the DataUpdateCoordinator
        return APIData(self.api.controller_name, devices)


    def get_device_by_id(self, device_type: DeviceType, device_id: int) -> GarnetEntity | None:
        """Return device by device id."""
        # Called by the binary sensors and sensors to get their updated data from self.data
        try:
            return [
                device
                for device in self.data.devices
                if device.device_type == device_type and device.device_id == device_id
            ][0]
        except IndexError:
            return None


    def set_device_data(self, device_id: int, state: any) -> None:
        """Push device data into API."""
        self.api.force_device_status(device_id, state)


    async def async_force_device_status(self, device_id: int, state: any) -> None:
        """Push device data into API."""
        await self.api.async_force_device_status(device_id, state)
