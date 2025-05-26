"""Interfaces with the Example api sensors."""

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .api import PanelEntity, EntityType
from .coordinator import GarnetPanelIntegrationCoordinator
from enum import StrEnum


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up the Sensors."""
    coordinator: GarnetPanelIntegrationCoordinator = hass.data[DOMAIN][config_entry.entry_id].coordinator
    async_add_entities([
        ZoneSensor(coordinator, device)
        for device in coordinator.data.devices
        if device.device_type == EntityType.ZONE
    ])
    async_add_entities([
        TextSensor(coordinator, device)
        for device in coordinator.data.devices
        if device.device_type == EntityType.TEXT_SENSOR
    ])
        
    
class ZoneSensor(CoordinatorEntity, SensorEntity):
    """Implementation of a zone monitoring sensor."""

    def __init__(self, coordinator: GarnetPanelIntegrationCoordinator, device: PanelEntity) -> None:
        """Initialise sensor."""
        super().__init__(coordinator)
        self.device = device
        self.device_id = device.device_id
        self._icon = device.icon


    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator. This method is called by your GarnetPanelIntegrationCoordinator when a successful update runs."""
        self.device = self.coordinator.get_device_by_id(self.device.device_type, self.device_id)
        #self._attr_native_value = self.device.native_state
        #self.async_write_ha_state()
        self.schedule_update_ha_state()


    @property
    def options(self) -> list[str] | None:
        return self.coordinator.api.zone_statuses


    @property
    def device_class(self) -> str:
        """Returns device class."""
        return SensorDeviceClass.ENUM
    

    @property
    def device_info(self) -> DeviceInfo:
        """Return panel device information. This is the parent device"""
        return self.coordinator.get_device_info()


    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self.device.name


    @property
    def unique_id(self) -> str:
        """Return unique id."""
        # All entities must have a unique id.  Think carefully what you want this to be as
        # changing it later will cause HA to create new entities.
        return f"{DOMAIN}-{self.device.device_unique_id}"


    @property
    def extra_state_attributes(self):
        """Return the extra state attributes. Add any additional attributes you want on your sensor."""
        attrs = {}                  
        #attrs["extra_info"] = "Extra Info"          
        return attrs


    @property
    def state(self) -> any:

        if self.device.alarmed:
            return "Alarmed"
        if self.device.native_state < 8:
            return ["Normal", "Open", "Inhibited", "Inhibited", "Armed", "ERROR", "Armed(Inhibited)", "ERROR"][self.device.native_state]
        _LOGGER.error("Combinacion no permitida de estado %s", str(self.device))
        return "ERROR"


    @property
    def icon(self):
        if(self._icon):
            return self._icon
        return None    


class TextSensor(CoordinatorEntity, SensorEntity):
    """Implementation of a zone monitoring sensor."""

    def __init__(self, coordinator: GarnetPanelIntegrationCoordinator, device: PanelEntity) -> None:
        """Initialise sensor."""
        super().__init__(coordinator)
        self.device = device
        self.device_id = device.device_id
        self._icon = device.icon


    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator. This method is called by your GarnetPanelIntegrationCoordinator when a successful update runs."""
        self.device = self.coordinator.get_device_by_id(self.device.device_type, self.device_id)
        #self._attr_native_value = self.device.native_state
        #self.async_write_ha_state()
        self.schedule_update_ha_state()
   

    @property
    def device_info(self) -> DeviceInfo:
        """Return panel device information. This is the parent device"""
        return self.coordinator.get_device_info()


    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self.device.name


    @property
    def unique_id(self) -> str:
        """Return unique id."""
        # All entities must have a unique id.  Think carefully what you want this to be as
        # changing it later will cause HA to create new entities.
        return f"{DOMAIN}-{self.device.device_unique_id}"


    @property
    def extra_state_attributes(self):
        """Return the extra state attributes. Add any additional attributes you want on your sensor."""
        attrs = {}                  
        #attrs["extra_info"] = "Extra Info"          
        return attrs


    @property
    def state(self) -> any:
        return self.device.native_state
    
    @property
    def icon(self):
        if(self._icon):
            return self._icon
        return None