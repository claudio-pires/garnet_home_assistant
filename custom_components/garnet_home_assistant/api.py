"""API Placeholder."""

from collections.abc import Callable
import logging
import threading
import time
import uuid

from homeassistant.core import HomeAssistant

from .const import (
    COMM_BASE_ID,
    DEFAULT_KEEPALIVE_INTERVAL,
    DEFAULT_REFRESH_INTERVAL,
    DEFAULT_UDP_PORT,
    DOMAIN,
    PARTITION_BASE_ID,
    REFRESHBUTTON_BASE_ID,
    ZONE_BASE_ID,
    DEFAULT_GARNET_SESSION_TTL

)
from .exceptions import GeneralGarnetError
from .httpapi import HTTP_API, DeviceType, GarnetEntity
from .siaserver import SIAUDPServer, siacode

_LOGGER = logging.getLogger(__name__)


class GarnetAPI:
    """Integracion con mensajeria SIA y API Web Garnet."""

    zone_statuses = [ "normal", "disabled", "alarmed"]

    messageserver = None
    __coordinator_update_callback: Callable = None
    keepalive_interval: int = DEFAULT_KEEPALIVE_INTERVAL
    refresh_interval: int = DEFAULT_REFRESH_INTERVAL
    tokenlifespan: int = DEFAULT_GARNET_SESSION_TTL

    @property
    def controller_name(self) -> str:
        """Return the name of the controller."""
        return self.account.replace(".", "_")


    def __init__(self, hass: HomeAssistant, user: str, pwd: str, account: str, systemid: str, uniqueid: str) -> None:
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
        self.status_refresh_task = None
        self.connection_monitor_task = None
        self.uniqueId = uniqueid


    def connect(self) -> bool:
        """Inicia las servicios que interactuan con la API Garnet."""

        _LOGGER.info("Starting GARNET API services ")
        try:
            # Crea el socket UDP para recibir mensajes SIA. Solo crea uno no importa la cantidad de integraciones activas.
            # Si falla devuelve una excepcion.
            if(GarnetAPI.messageserver is None):
                GarnetAPI.messageserver = SIAUDPServer(port=self.sia_port)

            # Se conecta a la API por primera vez y obtiene el modelo de datos del sistema configurado desde la WEB de garnet
            # Si falla devuelve una excepcion.
            self.httpapi = HTTP_API(email=self.email, pwd=self.password, panelid=self.systemid, controller=self.controller_name, lifespan=self.tokenlifespan)
            self.httpapi.connect()

            # Si llega aca significa que se pudo conectar a la WEB Garnet y que generó el modelo de entidades por lo que seeeeee suscribe
            # a mensajes sia
            GarnetAPI.messageserver.add(self.__sia_processing_task, self.account)

            # Crea la tarea de monitoreo de estado de zonas. Esta tarea no deberia ser muy frecuente.
            # No sabemos cada cuanto espera Garnet que se llame
            self.status_refresh_task_identity = uuid.uuid4() # se usa esta variable para que la thread sepa que es la activa.
            self.status_refresh_task = threading.Thread(target=self.__status_refresh_task, name="statusrefresh", args=(self.status_refresh_task_identity,))
            self.status_refresh_task.start()

            # Finalmente crea la tarea de monitoreo de keepalive del socket UDP. TODO: deberia generar una notificacion si no se recibe keepalive
            self.connection_monitor_task_identity = uuid.uuid4()
            self.connection_monitor_task = threading.Thread(target=self.__connection_monitor_task, name="keepalive", args=(self.connection_monitor_task_identity,))
            self.connection_monitor_task.start()

            _LOGGER.info("GARNET API services succesfuly setup")
            # Si llega aca sin errores es porque pudo conectarse
            self.connected = True
            return self.connected  # noqa: TRY300

        except Exception as err:                        #TODO: manejar diferentes tipos de excepciones  # noqa: BLE001
            _LOGGER.debug("connect() Exception Name: %s", type(err).__name__)
            _LOGGER.debug("connect() Exception Desc: %s", err)
            raise APIConnectionError(err)  # noqa: B904


    def disconnect(self) -> bool:
        """Devuelve estado de desconexion al coordinador."""

        GarnetAPI.messageserver.remove(self.client)     # Esto detiene el socket
        self.connected = False
        self.status_refresh_task_identity = None
        self.connection_monitor_task_identity = None
        self.connection_monitor_task = None
        return True


    def setcallback(self, message_callback: Callable | None = None ) -> bool:
        """Aegistra la funcion de update de estado de entidades."""

        self.__coordinator_update_callback = message_callback


    def __connection_monitor_task(self, identity):
        """Thread para monitoreo de la conexion."""

        _LOGGER.info("__connection_monitor_task will awake every %d seconds", self.keepalive_interval)
        threadIdentity = identity
        time.sleep(self.keepalive_interval)

        s = self.httpapi.__get_device_by_id__(COMM_BASE_ID)

        while(threadIdentity == self.connection_monitor_task_identity):
            try:
                time.sleep(self.keepalive_interval)
                t = time.time() - s.uptime
                n = "Disconnected" if t > int(1.5 *self.keepalive_interval) else "Connected"
                _LOGGER.debug("Checking last keepalive received was %d seconds before, previous state was %s",t, s.native_state)
                if n != s.native_state:
                    s.native_state = n
                    self.__coordinator_update_callback(self.httpapi.devices)
            except Exception:
                _LOGGER.exception("Exception:")
        _LOGGER.info("Thread with identity %s finishes because current identity is %s", threadIdentity, self.connection_monitor_task_identity)


    def __status_refresh_task(self, identity):
        """Thread para refresco de estado de zonas solo actualiza si la particion esta desarmada."""

        _LOGGER.info("__status_refresh_task will awake every %d seconds", self.refresh_interval)

        threadIdentity = identity
        time.sleep(self.refresh_interval)
        while(threadIdentity == self.status_refresh_task_identity):
            try:
                time.sleep(self.refresh_interval)
                disarm = True
                for device in self.httpapi.devices:
                    if device.device_type == DeviceType.PARTITION:
                        if device.native_state in {"home", "away"}:
                            disarm = False
                if disarm:
                    _LOGGER.debug("Actualizando estado de sensores")
                    self.httpapi.get_state()
                    self.__coordinator_update_callback(self.httpapi.devices)
                else:
                    _LOGGER.debug("No actualiza estado de sensores por estar alguna particion armada")
            except GeneralGarnetError as err:
                _LOGGER.error("No se pudo obtener estado debido a que se recibe error %s.", err)
            except Exception:
                _LOGGER.exception("Exception")
        _LOGGER.info("Thread with identity %s finishes because current identity is %s", threadIdentity, self.status_refresh_task_identity)


    def __sia_processing_task(self, partition: int = 0, zone: int = 0, user: int = 0, action: siacode = siacode.none) -> None:
        """Funcion que recibe notificaciones del cliente. No debe ser bloqueante."""

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
        elif(action in (siacode.present_arm, siacode.arm, siacode.keyboard_arm)): # armado de particion
            device = self.httpapi.__get_device_by_id__(PARTITION_BASE_ID + partition)
            f = False
            for z in self.httpapi.devices:
                if(z.device_type == DeviceType.ZONE and z.native_state & 2):
                    f = True  # Si hay alguna zona bypasseada es home sino away
            device.native_state = "home" if f else "away"
            if(not f):
                for d in self.httpapi.devices:
                    if d.device_type == DeviceType.ZONE:
                        d.native_state = (d.native_state | 4) & 5  # Bloquea las zonas
            update = True
        elif(action in (siacode.present_disarm, siacode.disarm, siacode.keyboard_disarm, siacode.alarm_disarm)): # desarmadp
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
            _LOGGER.warning("Mensaje con %s no se esta procesando", str(action)) # Se trata de un codigo que no se procesa
        if(update):
            self.__coordinator_update_callback(self.httpapi.devices)


    def get_devices(self) -> list[GarnetEntity]:
        """Devuelve la lista de dispositivos."""

        if self.connected:
            return self.httpapi.devices
        return None


    async def async_force_device_status(self, device_id: int, new_state: any) -> None:
        """Genera la accion sobre el device fisico. Version asincronica."""

        device = self.httpapi.__get_device_by_id__(device_id)
        if device.device_type == DeviceType.PARTITION:
            _LOGGER.debug("[async_force_device_status] API receives notification for partition to change with ID %i changed from %s to %s ", device_id, str(device.native_state), str(new_state))
            if(new_state in {"home", "away"}):
                try:
                    await self.hass.async_add_executor_job(self.httpapi.arm_system, device_id, new_state)
                except Exception as e:
                    _LOGGER.exception("Exception")
                    self.hass.services.async_call(
                        "persistent_notification",
                        "create",
                        {
                            "message": f"On panel arm it was received {e}",
                            "title": f"{self.uniqueId} reporting an error",
                        },
                    )
            elif(new_state == "disarmed"):
                try:
                    await self.hass.async_add_executor_job(self.httpapi.disarm_system, device_id)
                except Exception as e:
                    _LOGGER.exception("Exception")
                    self.hass.services.async_call(
                        "persistent_notification",
                        "create",
                        {
                            "message": f"On disarm panel it was received {e}",
                            "title": f"{self.uniqueId} reporting an error",
                        },
                    )
        if device.device_type == DeviceType.HOWLER:
            _LOGGER.debug("[async_force_device_status] API receives notification for howler with ID %i changed from %s to %s ", device_id, device.native_state, new_state)
            try:
                await self.hass.async_add_executor_job(self.httpapi.horn_control, new_state)
                device.native_state = new_state
            except Exception as e:
                _LOGGER.exception("Exception")
                self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "message": f"On activate horn it was received {e}",
                        "title": f"{self.uniqueId} reporting an error",
                    },
                )

        self.__coordinator_update_callback(self.httpapi.devices)


    def force_device_status(self, device_id: int, new_state: any) -> None:
        """Genera la accion sobre el device fisico. La funcion sincronica solo con botones."""
        device = self.httpapi.__get_device_by_id__(device_id)
        if device.device_type == DeviceType.BUTTON:
            _LOGGER.debug("[force_device_status] API receives notification for button %s with ID %i activation", device.name, device_id)
            if(device_id == REFRESHBUTTON_BASE_ID):
                try:
                    self.httpapi.get_state()
                except Exception as e:  # noqa: BLE001
                    _LOGGER.error(e)
                    self.hass.services.call(
                        "persistent_notification",
                        "create",
                        {
                            "message": f"On user action for update state it was received {e}",
                            "title": f"{self.uniqueId} reporting an error",
                        },
                    )
            else:
                p = self.httpapi.__get_device_by_id__(PARTITION_BASE_ID + 1)
                try:
                    self.httpapi.report_emergency(device.name, p.device_id, p.name)
                except Exception as e:  # noqa: BLE001
                    _LOGGER.error(e)
                    self.hass.services.call(
                        "persistent_notification",
                        "create",
                        {
                            "message": f"On report emergency it was received {e}",
                            "title": f"{self.uniqueId} reporting an error",
                        },
                    )
        self.__coordinator_update_callback(self.httpapi.devices)


    def get_device_unique_id(self, device_id: str, device_type: DeviceType) -> str:
        """Return a unique device id."""
        return f"{DOMAIN}_{self.controller_name}_{device_id}"


class APIAuthError(Exception):
    """Exception class for auth error."""


class APIConnectionError(Exception):
    """Exception class for connection error."""




