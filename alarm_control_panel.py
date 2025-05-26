"""Interfaces with the Garnet Panel Integration api sensors."""

import logging

from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState, AlarmControlPanelEntityFeature, CodeFormat
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .coordinator import GarnetPanelIntegrationCoordinator
from .api import PanelEntity, EntityType


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up the Sensors."""
    coordinator: GarnetPanelIntegrationCoordinator = hass.data[DOMAIN][config_entry.entry_id].coordinator

    async_add_entities([
        GarnetAlarmPanel(coordinator, device)
        for device in coordinator.data.devices
        if device.device_type == EntityType.PARTITION
    ])


class GarnetAlarmPanel(CoordinatorEntity, AlarmControlPanelEntity):
    """Implementation of the Garnet Alarm Panel."""

    def __init__(self, coordinator: GarnetPanelIntegrationCoordinator, device: PanelEntity) -> None:
        """Initialise sensor."""
        super().__init__(coordinator)
        self.supported_features = AlarmControlPanelEntityFeature.ARM_AWAY | AlarmControlPanelEntityFeature.ARM_HOME 
        self.device = device
        self.device_id = device.device_id
        self._icon = device.icon


    @callback
    def _handle_coordinator_update(self) -> None:
        """Update sensor with latest data from coordinator."""
        #_LOGGER.debug("[_handle_coordinator_update] Entity is now %s", str(self.device))
        #self.async_write_ha_state()
        self.schedule_update_ha_state()

    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return self.coordinator.get_device_info()


    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self.device.name


 #   @property
 #   def is_on(self) -> bool | None:
  #      """Return if the binary sensor is on."""
  #      # This needs to enumerate to true or false
  #      return True


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


    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """One of the alarm values listed in the states."""
        if self.device.native_state == "disarmed":
            return AlarmControlPanelState.DISARMED
        elif self.device.native_state == "home":
            return AlarmControlPanelState.ARMED_HOME
        return AlarmControlPanelState.ARMED_AWAY


    @property
    def code_arm_required(self) -> bool:
        return False    # Not required for the integration


    @property
    def code_format(self) -> CodeFormat | None:
        return None
    

    @property
    def changed_by(self) -> str | None:
        """Last change triggered by."""
        _LOGGER.debug("Ejecutando changed_by")
        return "TODO: poner el nombre"
    

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        await self.coordinator.async_force_device_status(self.device_id, "disarmed")
        await self.coordinator.async_request_refresh()


    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        await self.coordinator.async_force_device_status(self.device_id, "home")
        await self.coordinator.async_request_refresh()



    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self.coordinator.async_force_device_status(self.device_id, "away")
        await self.coordinator.async_request_refresh()
        
    @property
    def icon(self):
        if(self._icon):
            return self._icon
        return None