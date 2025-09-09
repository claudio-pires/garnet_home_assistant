"""Garnet integration using DataUpdateCoordinator."""

from dataclasses import dataclass

import logging

from homeassistant.config_entries import ConfigEntry 
from homeassistant.core import DOMAIN, HomeAssistant 
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed 
from homeassistant.helpers.device_registry import DeviceInfo 

from .api import APIAuthError, GarnetAPI
from .httpapi import DeviceType, GarnetEntity
from .const import (
    CONF_ACCOUNT, 
    CONF_GARNETUSER, 
    CONF_GARNETPASS, 
    CONF_SYSTEM, 
    CONF_KEEPALIVE_INTERVAL, 
    DEFAULT_KEEPALIVE_INTERVAL,
    CONF_REFRESH_INTERVAL, 
    DEFAULT_REFRESH_INTERVAL
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class APIData:
    """Class to hold api data."""

    controller_name: str
    devices: list[GarnetEntity]
  

class GarnetPanelIntegrationCoordinator(DataUpdateCoordinator):
    """Garnet Panel Integration coordinator."""

    data: APIData

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        self.account = config_entry.data[CONF_ACCOUNT]
        self.systemid = config_entry.data[CONF_SYSTEM]
        self.user = config_entry.data[CONF_GARNETUSER]
        self.pwd = config_entry.data[CONF_GARNETPASS]

        self.uniqueid = config_entry.unique_id
        super().__init__(hass, _LOGGER, name=f"{DOMAIN} ({self.uniqueid})", update_method=self.update_data, update_interval=None)   # Initialise DataUpdateCoordinator
                                                                                                              # update_method is the update method 
                                                                                                              # to get devices on first load.
                                                                                                              # update_interval = None makes data will be pushed.
        self.api = GarnetAPI(hass=hass, user=self.user, pwd=self.pwd, account=self.account, systemid=self.systemid)
        self.api.keepalive_interval = int(config_entry.options.get(CONF_KEEPALIVE_INTERVAL, DEFAULT_KEEPALIVE_INTERVAL))
        self.api.refresh_interval = int(config_entry.options.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL))
        self.api.setcallback(message_callback=self.devices_update_callback)

 
    def get_device_info(self) -> DeviceInfo | None:
        """Returns device info for panel"""
        panel = self.api.httpapi.system
        if panel is not None:
            return DeviceInfo(name = f"{panel.name} ({panel.id})", manufacturer = panel.manufacturer, model = panel.modelName, 
                              sw_version = panel.versionName, identifiers = {(DOMAIN, f"{DOMAIN} ({self.uniqueid})")})
        

    def devices_update_callback(self, devs: list[GarnetEntity]):
        """Receive callback from api with device update."""
        _LOGGER.debug("[devices_update_callback] Updating devices status")
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
            _LOGGER.exception(err)
            raise UpdateFailed(err) from err
        except Exception as err:
            # This will show entities as unavailable by raising UpdateFailed exception
            _LOGGER.exception(err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err

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
