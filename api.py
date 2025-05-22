"""API Placeholder."""

import logging

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from random import choice, randrange

from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState

from .const import DOMAIN
from .garnetapi import GarnetAPI
from .data import GarnetPanelInfo

_LOGGER = logging.getLogger(__name__)


class EntityType(StrEnum):
    """Tipos de entidades manejadas por la integracion."""
    PARTITION = "partition"
    ZONE = "zone"
    HOWLER = "howler"
    BUTTON = "button_switch"
    TEXT_SENSOR = "text_sensor"


@dataclass
class PanelEntity:
    device_id: int
    device_unique_id: str
    name: str
    device_type: EntityType
    state: int | bool | str
    alarmed: bool
    icon: str 


    def __str__(self):
        return "<device_id: " + str(self.device_id) + \
                ", device_unique_id: \"" + self.device_unique_id + \
                "\", name: \"" + self.name + \
                "\", device_type: \"" + str(self.device_type) + \
                "\", state: \"" + str(self.state) + \
                "\", alarmed: \"" + str(self.alarmed) + \
                "\", icon: " + ("None" if self.icon is None else ("\"" + str(self.icon) + "\""))+ ">"



class API:
    """Class for example API."""

    zone_statuses = [ "normal", "disabled", "alarmed"]
    partition_statuses = [ "disarmed", "home", "away"]

    devices: list[PanelEntity]


    def __init__(self, user: str, pwd: str, account: str) -> None:
        """Initialise."""
        self.account = account
        self.user = user
        self.pwd = pwd
        self.connected: bool = False
        self.devices = None


    def setcallback(self, message_callback: Callable | None = None ) -> bool:
        """Assignas message callback."""
        self.message_callback = message_callback


    @property
    def controller_name(self) -> str:
        """Return the name of the controller."""
        return self.account.replace(".", "_")


    def connect(self) -> bool:
        """Genera la conexion a la API garnet."""
        try:
            self.api = GarnetAPI(email = self.user, password = self.pwd, client = self.account)     # Genera conexion con la API Garnet
            self.api.set_keep_alive_handler(self.keep_alive_handler)                                # Registra funcion para recibir las notificaciones
            self.connected = True
            return True
        except Exception as err:                        #TODO: manejar diferentes tipos de excepciones
            _LOGGER.exception(err)
            raise APIConnectionError(err)


    def disconnect(self) -> bool:
        """Disconnect from api."""
        self.api.finalize
        self.connected = False
        return True


    async def keep_alive_handler(self):
        """Receive callback from api with device update."""
        device = self.__get_device_by_id__(300)
        _LOGGER.error("keep_alive_handler")
        device.state = "xxxxxxxxxxxxxxxxxxxxxxxxx"
        self.message_callback

    def get_panel(self) -> GarnetPanelInfo:
        """Obtiene los datos del panel"""
        if self.connected:
            return self.api.system
        return None





    def __translate_icon(self, icon: int | None) -> str:
        """Translate icon based on id"""
        if icon is not None and int(icon) < 12:
            return ["mdi:door", "mdi:window-closed-variant", "mdi:door-closed", "mdi:bed", "mdi:sofa", "mdi:stove", 
                    "mdi:garage", "mdi:flower", "mdi:balcony", "mdi:fire", "mdi:briefcase", "mdi:leak"][int(icon)]
        return None


    def get_devices(self) -> list[PanelEntity]:
        """Get devices on api."""
        if self.devices == None and self.connected:
            self.devices = []
            i = 0
            for partition in self.api.partitions:
                if partition.enabled:
                    self.devices.append(PanelEntity(device_id=i, device_unique_id=f"{self.controller_name}_P_{partition.id}",device_type=EntityType.PARTITION, 
                                                    name=partition.name,  alarmed=partition.alarmed, state=partition.enabled, icon=None)); i += 1
            i = 50
            for zone in self.api.zones:
                if zone.enabled:
                    self.devices.append(PanelEntity(device_id=i, device_unique_id=f"{self.controller_name}_Z_{zone.id}",device_type=EntityType.ZONE, 
                                                    name=zone.name,  alarmed=zone.alarmed, state=zone.enabled, icon=self.__translate_icon(zone.icon)));
            
            self.devices.append(PanelEntity(device_id=100, device_unique_id=f"{self.controller_name}_S_1",device_type=EntityType.HOWLER, name="Sirena", 
                                            alarmed=False, state="off", icon="mdi:alarm-bell")); i += 1
            self.devices.append(PanelEntity(device_id=200, device_unique_id=f"{self.controller_name}_B_1",device_type=EntityType.BUTTON, name="Panico", 
                                            alarmed=False, state="off", icon="mdi:police-badge-outline")); i += 1
            self.devices.append(PanelEntity(device_id=201, device_unique_id=f"{self.controller_name}_B_2",device_type=EntityType.BUTTON, name="Incendio", 
                                            alarmed=False, state="off", icon="mdi:fire-alert")); i += 1
            self.devices.append(PanelEntity(device_id=202, device_unique_id=f"{self.controller_name}_B_3",device_type=EntityType.BUTTON, name="Medico", 
                                            alarmed=False, state="off", icon="mdi:doctor")); i += 1
            self.devices.append(PanelEntity(device_id=203, device_unique_id=f"{self.controller_name}_B_4",device_type=EntityType.BUTTON, name="Panico demorado", 
                                            alarmed=False, state="off", icon="mdi:alarm")); i += 1
            self.devices.append(PanelEntity(device_id=300, device_unique_id=f"{self.controller_name}_X_1",device_type=EntityType.TEXT_SENSOR, name="Comunicador", 
                                            alarmed=False, state="off", icon="mdi:wifi")); i += 1

        return self.devices
    

    def __get_device_by_id__(self, device_id: int) -> PanelEntity | None:
        """Devuelve un dispositivo."""
        for device in self.devices:
            if device.device_id == device_id:
                return device
        return None
    

    async def async_force_device_status(self, device_id: int, new_state: any) -> None:
        """Genera la accion sobre el device fisico"""
        device = self.__get_device_by_id__(device_id)
        if device.device_type == EntityType.PARTITION:
            _LOGGER.debug("[async_force_device_status] API receives notification for partition to change with ID %i changed from %s to %s ", device_id, str(device.state), str(new_state))
            device.state = new_state
        if device.device_type == EntityType.HOWLER:
            _LOGGER.debug("[async_force_device_status] API receives notification for howler with ID %i changed from %s to %s ", device_id, "on" if device.state else "off", "on" if new_state else "off")
            device.state = new_state
        if device.device_type == EntityType.BUTTON:
            _LOGGER.debug("[async_force_device_status] API receives notification for button with ID %i activation", device_id)
        self.message_callback

    def force_device_status(self, device_id: int, new_state: any) -> None:
        """Genera la accion sobre el device fisico"""
        device = self.__get_device_by_id__(device_id)
        if device.device_type == EntityType.PARTITION:
            _LOGGER.debug("[async_force_device_status] API receives notification for partition to change with ID %i changed from %s to %s ", device_id, str(device.state), str(new_state))
            device.state = new_state
        if device.device_type == EntityType.HOWLER:
            _LOGGER.debug("[async_force_device_status] API receives notification for howler with ID %i changed from %s to %s ", device_id, "on" if device.state else "off", "on" if new_state else "off")
            device.state = new_state
        if device.device_type == EntityType.BUTTON:
            _LOGGER.debug("[async_force_device_status] API receives notification for button with ID %i activation", device_id)
        self.message_callback


    def get_device_unique_id(self, device_id: str, device_type: EntityType) -> str:
        """Return a unique device id."""
        return f"{DOMAIN}_{self.controller_name}_{device_id}"


    def get_device_value(self, device_id: str, device_type: EntityType) -> str | bool:
        """Get device random value."""
        if device_type == EntityType.PARTITION:
            _LOGGER.debug("[get_device_value] device_id " + str(device_id) + " with type EntityType.PARTITION")
            return False
        if device_type == EntityType.ZONE:
            _LOGGER.debug("[get_device_value] device_id " + str(device_id)  + ", device_type: EntityType.ZONE")
            return choice(self.zone_statuses)
        if device_type == EntityType.HOWLER:
            return False
        if device_type == EntityType.BUTTON:
            return False
        if device_type == EntityType.TEXT_SENSOR:
            return "Todo normal"
        return ""
    

class APIAuthError(Exception):
    """Exception class for auth error."""


class APIConnectionError(Exception):
    """Exception class for connection error."""
