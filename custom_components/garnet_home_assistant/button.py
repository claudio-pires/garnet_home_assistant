"""Interfaces with the Example api sensors."""

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GarnetPanelIntegrationCoordinator
from .httpapi import DeviceType, GarnetEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(_hass: HomeAssistant, _config_entry: ConfigEntry, _async_add_entities: AddEntitiesCallback):
    """Set up the Binary Sensors."""

    _LOGGER.debug("Setting up EmergencyButton (ButtonEntity) entities...")

    coordinator: GarnetPanelIntegrationCoordinator = _hass.data[DOMAIN][_config_entry.entry_id].coordinator

    _async_add_entities([
        EmergencyButton(coordinator, device)
        for device in coordinator.data.devices
        if device.device_type == DeviceType.BUTTON
    ])


class EmergencyButton(CoordinatorEntity, ButtonEntity):
    """Implementation of a button to trigger an emergency."""

    def __init__(self, _coordinator: GarnetPanelIntegrationCoordinator, _device: GarnetEntity) -> None:
        """Initialise sensor."""
        super().__init__(_coordinator)

        _LOGGER.debug("Instantiating EmergencyButton for device=%s", _device)

        self.c = _coordinator
        self.device = _device
        self.device_id = _device.device_id
        self._icon = _device.icon

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return self.coordinator.get_device_info()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""
        #_LOGGER.debug("[_handle_coordinator_update] Entity is now %s", str(self.device))
        self.schedule_update_ha_state()

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
        """Return the extra  attributes."""
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
