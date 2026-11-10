"""Platform tipo Switch, Sirena."""

import logging

from homeassistant.components.switch import SwitchEntity
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
    """Set up the Binary Sensors. En este momento solo la sirena."""

    _LOGGER.debug("Setting up HowlerSwitch (SwitchEntity) entities...")

    coordinator: GarnetPanelIntegrationCoordinator = _hass.data[DOMAIN][_config_entry.entry_id].coordinator
    _async_add_entities([
        HowlerSwitch(coordinator, device)
        for device in coordinator.data.devices
        if device.device_type == DeviceType.HOWLER
    ])


class HowlerSwitch(CoordinatorEntity, SwitchEntity):
    """Implementacion del control de sirena."""

    def __init__(self, _coordinator: GarnetPanelIntegrationCoordinator, _device: GarnetEntity) -> None:
        """Initialise sensor."""

        super().__init__(_coordinator)

        _LOGGER.debug("Instantiating HowlerSwitch for device=%s", _device)

        self.device = _device
        self.device_id = _device.device_id
        self._icon = _device.icon


    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""

        self.schedule_update_ha_state()


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

        return self.device.native_state == "on"


    @property
    def unique_id(self) -> str:
        """Return unique id."""
        return f"{DOMAIN}-{self.device.device_unique_id}"


    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        await self.coordinator.async_force_device_status(self.device_id, "on")
        await self.coordinator.async_request_refresh()


    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        await self.coordinator.async_force_device_status(self.device_id, "off")
        await self.coordinator.async_request_refresh()


    @property
    def icon(self):
        if(self._icon):
            return self._icon
        return None
