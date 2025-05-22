"""Interfaces with the Example api sensors."""

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import PanelEntity, EntityType
from .const import DOMAIN
from .coordinator import GarnetPanelIntegrationCoordinator


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up the Binary Sensors."""
    # This gets the data update coordinator from hass.data as specified in your __init__.py
    coordinator: GarnetPanelIntegrationCoordinator = hass.data[DOMAIN][config_entry.entry_id].coordinator

    async_add_entities([
        HowlerSwitch(coordinator, device)
        for device in coordinator.data.devices
        if device.device_type == EntityType.HOWLER
    ])


class HowlerSwitch(CoordinatorEntity, SwitchEntity):
    """Implementation of a partition sensor alarmed / no alarmed."""

    def __init__(self, coordinator: GarnetPanelIntegrationCoordinator, device: PanelEntity) -> None:
        """Initialise sensor."""
        super().__init__(coordinator)
        self.device = device
        self.device_id = device.device_id
        self._icon = device.icon


    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""
        _LOGGER.debug("[_handle_coordinator_update] Entity is now %s", str(self.device))
        self.async_write_ha_state()


    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return self.coordinator.get_device_info()


    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self.device.name
    

    @property
    def is_on(self) -> bool | None:
        """Return if the binary sensor is on."""
        return self.device.state == "on"


    @property
    def unique_id(self) -> str:
        """Return unique id."""
        # All entities must have a unique id.  Think carefully what you want this to be as
        # changing it later will cause HA to create new entities.
        return f"{DOMAIN}-{self.device.device_unique_id}"
    

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self.coordinator.async_force_device_status(self.device_id, "on")
        await self.coordinator.async_request_refresh()


    async def async_turn_off(self, **kwargs):
        """Turn the entity on."""
        await self.coordinator.async_force_device_status(self.device_id, "off")
        await self.coordinator.async_request_refresh()


    @property
    def icon(self):
        if(self._icon):
            return self._icon
        return None    
