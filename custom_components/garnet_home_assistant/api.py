"""API Placeholder."""

import logging

from collections.abc import Callable
import time
import threading

from .const import ( 
    DOMAIN, 
    PARTITION_BASE_ID, 
    ZONE_BASE_ID, 
    COMM_BASE_ID,
    DEFAULT_KEEPALIVE_INTERVAL,
    REFRESHBUTTON_BASE_ID,
    DEFAULT_UDP_PORT
)
from .httpapi import HTTP_API, GarnetEntity, DeviceType

from homeassistant.core import HomeAssistant 

from .siaserver import SIAUDPServer, siacode


_LOGGER = logging.getLogger(__name__)


class GarnetAPI:
    """Class for example API."""

    zone_statuses = [ "normal", "disabled", "alarmed"]

    messageserver = None
    __coordinator_update_callback: Callable = None
    keepalive_interval: int = DEFAULT_KEEPALIVE_INTERVAL

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
        self.user = None
        self.system = None
        self.hass = hass
        self.sia_port = DEFAULT_UDP_PORT


    def connect(self) -> bool:
        """Devuelve estado de conexion al coordinador"""
        try:
            # Crea el socket UDP para recibir mensajes SIA. Solo uno no importa la cantidad de integraciones activas
            # Si falla no sigue.
            if(GarnetAPI.messageserver == None):
                GarnetAPI.messageserver = SIAUDPServer(port=self.sia_port) 

            # Obtiene el modelo de datos de la WEB de garnet
            # SI no falla recien se registra como listener de mensajes SIA e informa que esta conectado
            self.httpapi = HTTP_API(email=self.email, pwd=self.password, panelid=self.systemid, controller=self.controller_name)    
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
        time.sleep(self.keepalive_interval)
        s = self.httpapi.__get_device_by_id__(COMM_BASE_ID)
        while(self.connected):
            try:
                time.sleep(self.keepalive_interval)    
                t = time.time() - s.uptime
                n = "Disconnected" if t > int(1.5 *self.keepalive_interval) else "Connected"
                _LOGGER.debug("Checking last keepalive received was %d seconds before, previous state was %s",t, s.native_state)
                if n != s.native_state:
                    s.native_state = n
                    self.__coordinator_update_callback(self.httpapi.devices)
            except Exception as err:                        
                _LOGGER.exception(err)


    def __sia_processing_task(self, partition: int = 0, zone: int = 0, user: int = 0, action: siacode = siacode.none) -> None:
        """Funcion que recibe notificaciones del cliente. No debe ser bloqueante"""
        update = False
        _LOGGER.debug("[__sia_processing_task] Receiving action:%s, partition:%d, zone:%d and  user:%d",str(action), partition, zone, user)
        device = self.httpapi.__get_device_by_id__(COMM_BASE_ID)
        device.uptime = time.time()                             # 25/05/30 Ahora se actualiza con cualquier mensaje no solo keep alive
        if(action == siacode.bypass): # bypass de una zona
            device = self.httpapi.__get_device_by_id__(ZONE_BASE_ID + zone)
            device.native_state = device.native_state | 2
            update = True
        elif(action == siacode.unbypass): # desactiva bypass de una zona
            device = self.httpapi.__get_device_by_id__(ZONE_BASE_ID + zone)
            device.native_state = device.native_state & 5
            update = True
        elif(action == siacode.group_bypass): # armado de todas las zonas
            for d in self.httpapi.devices:
                if d.device_type == DeviceType.ZONE:
                    d.native_state = d.native_state | 4
            update = True
        elif(action == siacode.group_unbypass): # desarmado de todas las zonas
            for d in self.httpapi.devices:
                if d.device_type == DeviceType.ZONE:
                    d.native_state = d.native_state & 3
            update = True
        elif(action == siacode.present_arm or action == siacode.arm or action == siacode.keyboard_arm): # armado de particion
            device = self.httpapi.__get_device_by_id__(PARTITION_BASE_ID + partition)
            f = False
            for z in self.httpapi.devices: 
                if(z.device_type == DeviceType.ZONE and z.native_state & 2): f = True  # Si hay alguna zona bypasseada es home sino away
            device.native_state = "home" if f else "away"
            if(not f):
                for d in self.httpapi.devices:
                    if d.device_type == DeviceType.ZONE:
                        d.native_state = (d.native_state | 4) & 5  # Bloquea las zonas
            update = True
        elif(action == siacode.present_disarm or action == siacode.disarm or action == siacode.keyboard_disarm or action == siacode.alarm_disarm): # desarmadp
            device = self.httpapi.__get_device_by_id__(PARTITION_BASE_ID + partition)
            device.native_state = "disarmed"
            for d in self.httpapi.devices:
                if d.device_type == DeviceType.ZONE:
                    d.native_state = d.native_state & 3
            update = True
        elif(action == siacode.triggerzone):  # Alarma en una zona
            device = self.httpapi.__get_device_by_id__(ZONE_BASE_ID + zone)
            device.alarmed = True
            update = True
        elif(action == siacode.restorezone): # Reestablecimiento de alarma en zona
            device = self.httpapi.__get_device_by_id__(ZONE_BASE_ID + zone)
            device.alarmed = False
            update = True
        elif(action == siacode.trigger): # Alarma en particion
            device = self.httpapi.__get_device_by_id__(PARTITION_BASE_ID + partition)
            device.alarmed = True
            update = True
        elif(action == siacode.restore): # Se desalarma particion
            device = self.httpapi.__get_device_by_id__(PARTITION_BASE_ID + partition)
            device.alarmed = False
            update = True
        elif(action != siacode.keepalive):
            _LOGGER.info("Mensaje con " + str(action) + " no se esta procesando") # Se trata de un codigo que no se procesa
        if(update):
            self.__coordinator_update_callback(self.httpapi.devices)


    def get_devices(self) -> list[GarnetEntity]:
        if self.connected:
            return self.httpapi.devices
        return None
    

    async def async_force_device_status(self, device_id: int, new_state: any) -> None:
        """Genera la accion sobre el device fisico. Version asincronica"""
        device = self.httpapi.__get_device_by_id__(device_id)
        if device.device_type == DeviceType.PARTITION:
            _LOGGER.debug("[async_force_device_status] API receives notification for partition to change with ID %i changed from %s to %s ", device_id, str(device.native_state), str(new_state))
            if(new_state == "home"):
                try:
                    result = await self.hass.async_add_executor_job(self.httpapi.arm_system, device_id, "home")
                except Exception as err:
                    _LOGGER.exception(err)
            elif(new_state == "away"):
                try:
                    result = await self.hass.async_add_executor_job(self.httpapi.arm_system, device_id, "away")
                except Exception as err:
                    _LOGGER.exception(err)
            elif(new_state == "disarmed"):
                try:
                    result = await self.hass.async_add_executor_job(self.httpapi.disarm_system, device_id)
                except Exception as err:
                    _LOGGER.exception(err)
        if device.device_type == DeviceType.HOWLER:
            _LOGGER.debug("[async_force_device_status] API receives notification for howler with ID %i changed from %s to %s ", device_id, device.native_state, new_state)
            try:
                result = await self.hass.async_add_executor_job(self.httpapi.horn_control, new_state)
                device.native_state = new_state
            except Exception as err:
                _LOGGER.exception(err)
        self.__coordinator_update_callback(self.httpapi.devices)


    def force_device_status(self, device_id: int, new_state: any) -> None:
        """Genera la accion sobre el device fisico. La funcion sincronica solo con botones"""
        device = self.httpapi.__get_device_by_id__(device_id)
        if device.device_type == DeviceType.BUTTON:
            _LOGGER.debug("[force_device_status] API receives notification for button %s with ID %i activation", device.name, device_id)
            if(device_id == REFRESHBUTTON_BASE_ID):
                try:
                    self.httpapi.get_state()
                except Exception as err:
                    _LOGGER.exception(err)
            else:
                p = self.httpapi.__get_device_by_id__(PARTITION_BASE_ID + 1)
                try:
                    result = self.httpapi.report_emergency(device.name, p.device_id, p.name)
                except Exception as err:
                    _LOGGER.exception(err)
        self.__coordinator_update_callback(self.httpapi.devices)


    def get_device_unique_id(self, device_id: str, device_type: DeviceType) -> str:
        """Return a unique device id."""
        return f"{DOMAIN}_{self.controller_name}_{device_id}"


class APIAuthError(Exception):
    """Exception class for auth error."""


class APIConnectionError(Exception):
    """Exception class for connection error."""




