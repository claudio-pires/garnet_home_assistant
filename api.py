"""API Placeholder."""

import logging

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from random import choice, randrange
import time
import threading

from .const import ( DOMAIN, PARTITION_BASE_ID, ZONE_BASE_ID, HOWLER_BASE_ID, POLICEBUTTON_BASE_ID,
                     DOCTORBUTTON_BASE_ID, FIREBUTTON_BASE_ID, TIMEDPANICBUTTON_BASE_ID, COMM_BASE_ID )
from .httpapi  import HTTP_API
from .httpdata import Zone, Partition

from homeassistant.core import HomeAssistant

from .siaserver import SIAUDPServer, siacode
from .const import *

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
    native_state: int | bool | str
    alarmed: bool
    icon: str 
    uptime: float


    def __str__(self):
        return "<PanelEntity: device_id: " + str(self.device_id) + \
                ", device_unique_id: \"" + self.device_unique_id + \
                "\", name: \"" + self.name + \
                "\", device_type: \"" + str(self.device_type) + \
                "\", native_state: \"" + str(self.native_state) + \
                "\", alarmed: \"" + str(self.alarmed) + \
                "\", uptime: " + str(self.uptime) + \
                ", icon: " + ("None" if self.icon is None else ("\"" + str(self.icon) + "\""))+ ">"



class GarnetAPI:
    """Class for example API."""

    zone_statuses = [ "normal", "disabled", "alarmed"]

    devices: list[PanelEntity]
    messageserver = None
    __coordinator_update_callback: Callable = None

    @property
    def controller_name(self) -> str:
        """Return the name of the controller."""
        return self.account.replace(".", "_")


    def __init__(self, hass: HomeAssistant, user: str, pwd: str, account: str, systemid: str) -> None:
        """Initialise."""
        self.account = account
        self.systemid = systemid
        self.email = user
        self.password = pwd
        self.panelid = ""
        self.connected: bool = False
        self.devices = None
        self.seq = 0
        self.user = None
        self.system = None
        self.hass = hass


    def connect(self) -> bool:
        """Devuelve estado de conexion al coordinador"""
        try:
            # Crea el socket UDP para recibir mensajes SIA. Solo uno no importa la cantidad de integraciones activas
            # Si falla no sigue.
            if(GarnetAPI.messageserver == None):
                GarnetAPI.messageserver = SIAUDPServer() 

            # Obtiene el modelo de datos de la WEB de garnet
            # SI no falla recien se registra como listener de mensajes SIA e informa que esta conectado
            self.httpapi = HTTP_API(email=self.email, pwd=self.password, panelid=self.systemid)    
            self.httpapi.connect()
            GarnetAPI.messageserver.add(self.__sia_processing_task, self.account)
            self.connected = True

            # Finalmente crea la tarea de monitoreo de keepalive
            self.connection_monitor_task = threading.Thread(target=self.__connection_monitor_task, name="keepalive")
            self.connection_monitor_task.start()

            return self.connected
        except Exception as err:                        #TODO: manejar diferentes tipos de excepciones
            _LOGGER.exception(err)
            raise APIConnectionError(err)


    def disconnect(self) -> bool:
        """Devuelve estado de desconexion al coordinador."""
        GarnetAPI.messageserver.remove(self.client)
        self.connected = False
        return True


    def setcallback(self, message_callback: Callable | None = None ) -> bool:
        """Aegistra la funcion de update de estado de entidades."""
        self.__coordinator_update_callback = message_callback


    def __connection_monitor_task(self):
        """Thread para monitoreo de la conexion"""
        time.sleep(60)
        s = self.__get_device_by_id__(COMM_BASE_ID)
        while(self.connected):
            try:
                time.sleep(60)      #TODO Tomar el tiempo de una configuracion del sistema, cada tablero tendra siu propia configuracion
                t = time.time() - s.uptime
                n = "Disconnected" if t > 90 else "Connected"
                _LOGGER.debug("Checking last keepalive received was %d seconds before, previous state was %s",t, s.native_state)
                if n != s.native_state:
                    s.native_state = n
                    self.__coordinator_update_callback(self.get_devices())
            except Exception as err:                        
                _LOGGER.exception(err)


    def __sia_processing_task(self, partition: int = 0, zone: int = 0, user: int = 0, action: siacode = siacode.none) -> None:
        """Funcion que recibe notificaciones del cliente. No debe ser bloqueante"""
        update = False
        _LOGGER.debug("[__sia_processing_task] Receiving action:%s, partition:%d, zone:%d and  user:%d",str(action), partition, zone, user)
        device = self.__get_device_by_id__(COMM_BASE_ID)
        device.uptime = time.time()                             # 25/05/30 Ahora se actualiza con cualquier mensaje no solo keep alive
        if(action == siacode.bypass):
            self.httpapi.zones[zone - 1].bypassed = True
            device = self.__get_device_by_id__(ZONE_BASE_ID + zone - 1)
            device.native_state = device.native_state | 2
            update = True
        elif(action == siacode.unbypass):
            self.httpapi.zones[zone - 1].bypassed = False 
            device = self.__get_device_by_id__(ZONE_BASE_ID + zone - 1)
            device.native_state = device.native_state & 5
            update = True
        elif(action == siacode.group_bypass):
            for z in self.httpapi.zones:
                if(z.enabled): z.bypassed = True
            for d in self.devices:
                if d.device_type == EntityType.ZONE:
                    d.native_state = d.native_state | 4
            update = True
        elif(action == siacode.group_unbypass):
            for z in self.httpapi.zones:
                if(z.enabled): z.bypassed = False
            for d in self.devices:
                if d.device_type == EntityType.ZONE:
                    d.native_state = d.native_state & 3
            update = True
        elif(action == siacode.present_arm or action == siacode.arm or action == siacode.keyboard_arm):
            self.httpapi.partitions[partition - 1].armed = True
            device = self.__get_device_by_id__(PARTITION_BASE_ID + partition - 1)
            f = False
            for z in self.httpapi.zones: 
                if(z.enabled): f = f or z.bypassed
            device.native_state = "home" if f else "away"
            if(not f):
                for d in self.devices:
                    if d.device_type == EntityType.ZONE:
                        d.native_state = (d.native_state | 4) & 5
            update = True
        elif(action == siacode.present_disarm or action == siacode.disarm or action == siacode.keyboard_disarm or action == siacode.alarm_disarm):
            self.httpapi.partitions[partition - 1].armed = False
            device = self.__get_device_by_id__(PARTITION_BASE_ID + partition - 1)
            device.native_state = "disarmed"
            for d in self.devices:
                if d.device_type == EntityType.ZONE:
                    d.native_state = d.native_state & 3
            update = True
        elif(action == siacode.triggerzone):
            self.httpapi.zones[zone - 1].alarmed = True
            device = self.__get_device_by_id__(ZONE_BASE_ID + zone - 1)
            device.alarmed = True
            update = True
        elif(action == siacode.restorezone):
            self.httpapi.zones[zone - 1].alarmed = False
            device = self.__get_device_by_id__(ZONE_BASE_ID + zone - 1)
            device.alarmed = False
            update = True
        elif(action == siacode.trigger):
            self.httpapi.partitions[partition - 1].alarmed = True
            device = self.__get_device_by_id__(PARTITION_BASE_ID + partition - 1)
            device.alarmed = True
            update = True
        elif(action == siacode.restore):
            self.httpapi.partitions[partition - 1].alarmed = False
            device = self.__get_device_by_id__(PARTITION_BASE_ID + partition - 1)
            device.alarmed = False
            update = True
        elif(action != siacode.keepalive):
            _LOGGER.warning("siacode " + str(action) + " no se esta procesando") # Se trata de un codigo que no se procesa
        if(update):
            self.__coordinator_update_callback(self.get_devices())

    def get_devices(self) -> list[PanelEntity]:
        """Get devices on api."""
        if self.devices == None and self.connected:
            self.devices = []
            i = PARTITION_BASE_ID
            for partition in self.httpapi.partitions:
                if partition.enabled:
                    self.devices.append(PanelEntity(device_id=i, device_unique_id=f"{self.controller_name}_P_{partition.id}",
                                                    device_type=EntityType.PARTITION, name=partition.name, 
                                                    alarmed=partition.alarmed, native_state=partition.armed, uptime=0, icon=None)); i += 1
            i = ZONE_BASE_ID
            for zone in self.httpapi.zones:
                if zone.enabled:
                    self.devices.append(PanelEntity(device_id=i, device_unique_id=f"{self.controller_name}_Z_{zone.id}",
                                                    device_type=EntityType.ZONE, name=zone.name, 
                                                    alarmed=zone.alarmed, native_state=((1 if zone.open else 0) + (2 if zone.bypassed else 0)),
                                                    uptime=0, icon=Zone.translate_icon(icon=zone.icon))); i += 1
            
            self.devices.append(PanelEntity(device_id=HOWLER_BASE_ID, device_unique_id=f"{self.controller_name}_S_1",device_type=EntityType.HOWLER, name="Sirena", 
                                            alarmed=False, native_state=self.httpapi.howler, uptime=0, icon="mdi:alarm-bell")); i += 1
            self.devices.append(PanelEntity(device_id=POLICEBUTTON_BASE_ID, device_unique_id=f"{self.controller_name}_B_1",device_type=EntityType.BUTTON, name="Panico", 
                                            alarmed=False, native_state="Unknown", uptime=0, icon="mdi:police-badge-outline")); i += 1
            self.devices.append(PanelEntity(device_id=DOCTORBUTTON_BASE_ID, device_unique_id=f"{self.controller_name}_B_2",device_type=EntityType.BUTTON, name="Incendio", 
                                            alarmed=False, native_state="Unknown", uptime=0, icon="mdi:fire-alert")); i += 1
            self.devices.append(PanelEntity(device_id=FIREBUTTON_BASE_ID, device_unique_id=f"{self.controller_name}_B_3",device_type=EntityType.BUTTON, name="Medico", 
                                            alarmed=False, native_state="Unknown", uptime=0, icon="mdi:doctor")); i += 1
            self.devices.append(PanelEntity(device_id=TIMEDPANICBUTTON_BASE_ID, device_unique_id=f"{self.controller_name}_B_4",device_type=EntityType.BUTTON, name="Panico demorado", 
                                            alarmed=False, native_state="Unknown", uptime=0, icon="mdi:alarm")); i += 1
            self.devices.append(PanelEntity(device_id=COMM_BASE_ID, device_unique_id=f"{self.controller_name}_X_1",device_type=EntityType.TEXT_SENSOR, name="Comunicador", 
                                            alarmed=False, native_state="Unknown", uptime=0, icon="mdi:wifi")); i += 1

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
            _LOGGER.debug("[async_force_device_status] API receives notification for partition to change with ID %i changed from %s to %s ", device_id, str(device.native_state), str(new_state))
            if(new_state == "home"):
                try:
                    result = await self.hass.async_add_executor_job(self.httpapi.arm_system, device_id + 1, "home")
                except Exception as err:
                    _LOGGER.exception(err)
                    device.native_state = device.native_state
            elif(new_state == "away"):
                try:
                    result = await self.hass.async_add_executor_job(self.httpapi.arm_system, device_id + 1, "away")
                except Exception as err:
                    _LOGGER.exception(err)
                    device.native_state = device.native_state
            elif(new_state == "disarmed"):
                try:
                    result = await self.hass.async_add_executor_job(self.httpapi.disarm_system, device_id + 1)
                except Exception as err:
                    _LOGGER.exception(err)
                    device.native_state = device.native_state
        if device.device_type == EntityType.HOWLER:
            _LOGGER.debug("[async_force_device_status] API receives notification for howler with ID %i changed from %s to %s ", device_id, "on" if device.native_state else "off", "on" if new_state else "off")
            device.native_state = new_state
        if device.device_type == EntityType.BUTTON:
            _LOGGER.debug("[async_force_device_status] API receives notification for button with ID %i activation", device_id)
        #self.__coordinator_update_callback(self.get_devices())


    def force_device_status(self, device_id: int, new_state: any) -> None:
        """Genera la accion sobre el device fisico"""
        device = self.__get_device_by_id__(device_id)
        if device.device_type == EntityType.PARTITION:
            _LOGGER.debug("[force_device_status] API receives notification for partition to change with ID %i changed from %s to %s ", device_id, str(device.native_state), str(new_state))
            if(new_state == "home"):
                try:
                    self.httpapi.arm_system(device_id + 1, "home")
                except Exception as err:
                    _LOGGER.exception(err)
                    device.native_state = device.native_state
            elif(new_state == "away"):
                try:
                    self.httpapi.arm_system(device_id + 1, "away")
                except Exception as err:
                    _LOGGER.exception(err)
                    device.native_state = device.native_state
            elif(new_state == "disarmed"):
                try:
                    self.httpapi.disarm_system(device_id + 1)
                except Exception as err:
                    _LOGGER.exception(err)
                    device.native_state = device.native_state
        if device.device_type == EntityType.HOWLER:
            _LOGGER.debug("[async_force_device_status] API receives notification for howler with ID %i changed from %s to %s ", device_id, "on" if device.native_state else "off", "on" if new_state else "off")
            device.native_state = new_state
        if device.device_type == EntityType.BUTTON:
            _LOGGER.debug("[async_force_device_status] API receives notification for button with ID %i activation", device_id)
        #self.__coordinator_update_callback


    def get_device_unique_id(self, device_id: str, device_type: EntityType) -> str:
        """Return a unique device id."""
        return f"{DOMAIN}_{self.controller_name}_{device_id}"


class APIAuthError(Exception):
    """Exception class for auth error."""


class APIConnectionError(Exception):
    """Exception class for connection error."""




