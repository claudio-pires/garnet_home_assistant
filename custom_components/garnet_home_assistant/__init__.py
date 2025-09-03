"""Garnet Panel Integration ."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant 
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .coordinator import GarnetPanelIntegrationCoordinator


_LOGGER = logging.getLogger(__name__)

# Platforms required for the integration
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.ALARM_CONTROL_PANEL, Platform.SWITCH, Platform.BUTTON]


@dataclass
class RuntimeData:
    """Class to hold Integration data."""
    coordinator: DataUpdateCoordinator
    cancel_update_listener: Callable


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Garnet Panel Integration from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    coordinator = GarnetPanelIntegrationCoordinator(hass, config_entry)     # Initialises the coordinator
    await coordinator.async_config_entry_first_refresh()                    # Perform an initial data load from api.

    if not coordinator.api.connected:                       # TODO: Modificar para reflejar excepciones coherentes
        raise ConfigEntryNotReady
    
    cancel_update_listener = config_entry.add_update_listener(_async_update_listener)   # Initialise a listener for config flow options changes.
                                                                                        # See config_flow for defining an options setting that 
                                                                                        # shows up as configure on the integration.
    
    hass.data[DOMAIN][config_entry.entry_id] = RuntimeData(coordinator, cancel_update_listener) # Add the coordinator and update listener to hass data to make
                                                                                                # accessible throughout your integration
                                                                                                # Note: this will change on HA2024.6 to save on the config entry.
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, config_entry):
    """Handles config options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)       # Reload the integration when the options change.
                                                                        # TODO: Debe quitar el listener SIA  y reemplazarlo por el nuevo. Por el momento se hace solo


async def async_remove_config_entry_device(hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry) -> bool:
    """Delete device if selected from UI. Adding this function shows the delete device option in the UI."""
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry. This is called when you remove your integration or shutdown HA."""
    
    hass.data[DOMAIN][config_entry.entry_id].cancel_update_listener()       # Remove the config options update listener
    unload_ok = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)   # Unload platforms
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)        # Remove the config entry from the hass data object.
    return unload_ok                                        # Return that unloading was successful.
