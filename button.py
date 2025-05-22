"""Interfaces with the Example api sensors."""

import logging

from homeassistant.components.button import ButtonEntity 
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
    coordinator: GarnetPanelIntegrationCoordinator = hass.data[DOMAIN][config_entry.entry_id].coordinator

    async_add_entities([
        EmergencyButton(coordinator, device)
        for device in coordinator.data.devices
        if device.device_type == EntityType.BUTTON
    ])


class EmergencyButton(CoordinatorEntity, ButtonEntity):
    """Implementation of a button to trigger an emergency."""

    def __init__(self, coordinator: GarnetPanelIntegrationCoordinator, device: PanelEntity) -> None:
        """Initialise sensor."""
        super().__init__(coordinator)
        self.device = device
        self.device_id = device.device_id
        self._icon = device.icon

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return self.coordinator.get_device_info()


    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self.device.name


    @property
    def unique_id(self) -> str:
        """Return unique id."""
        return f"{DOMAIN}-{self.device.device_unique_id}"


    @property
    def extra_state_attributes(self):
        """Return the extra state attributes."""
        attrs = {}
        #attrs["extra_info"] = "Extra Info"
        return attrs


    def press(self) -> None:
        """Handle the button press."""
        self.coordinator.set_device_data(self.device_id, True)

    @property
    def icon(self):
        if(self._icon):
            return self._icon
        return None