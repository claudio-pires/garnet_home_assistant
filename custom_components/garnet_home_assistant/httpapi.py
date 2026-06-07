"""Funciones de manejo de panel a traves de la api http de Garnet."""

from dataclasses import dataclass
from enum import StrEnum
import json
import logging
import time

import requests

from .const import (
    COMM_BASE_ID,
    DOCTORBUTTON_BASE_ID,
    FIREBUTTON_BASE_ID,
    GARNETAPITIMEOUT,
    GARNETAPIURL,
    HOWLER_BASE_ID,
    PARTITION_BASE_ID,
    POLICEBUTTON_BASE_ID,
    REFRESHBUTTON_BASE_ID,
    RETRY_LOGIN_ON_IRRESPONSIVE,
    TIMEDPANICBUTTON_BASE_ID,
    WAIT_ON_LOGIN_IRRESPONSIVE,
    ZONE_BASE_ID,
)
from .exceptions import GarnetPermissionError, GeneralGarnetError
from .httpdata import GarnetHTTPUser, GarnetPanelInfo, Zone

_LOGGER = logging.getLogger(__name__)

class DeviceType(StrEnum):
    """Tipos de entidades manejadas por la integracion."""

    PARTITION = "partition"
    ZONE = "zone"
    HOWLER = "howler"
    BUTTON = "button_switch"
    TEXT_SENSOR = "text_sensor"

@dataclass
class GarnetEntity:
    """Clase para encapsular una entidad que se asocia con un atributo del panel."""

    device_id: int
    device_unique_id: str
    name: str
    device_type: DeviceType
    native_state: int | bool | str
    alarmed: bool
    icon: str
    uptime: float


    def __str__(self):
        """Class to String."""

        return f"<GarnetEntity: device_id: {self.device_id!s}, device_unique_id: \"{self.device_unique_id}\", name: \"{self.name}\", device_type: \"{self.device_type!s}\", native_state: \"{self.native_state!s}\", alarmed: \"{self.alarmed!s}\", uptime: {self.uptime!s}, icon:{("None" if self.icon is None else ("\"" + str(self.icon) + "\""))}>"


class SessionData:
    """Datos de la session."""

    token: str = None
    creation: time = None

    def __init__(self, token: str | None = None, creation: time = 0) -> None:
        """Inicializa el objeto sesion."""

        self.token = token
        self.creation = creation


class HTTP_API:
    """Clase que maneja la interaccion con el panel a traves de socket SIA y API Garnet."""

    user :   GarnetHTTPUser             # Datos de la cuenta
    devices: list[GarnetEntity]         # dispositivos
    system:  GarnetPanelInfo = None     # Datos del panel
    partition_mask: int                 # mascara que define las particiones configuradas
    zone_mask: int                      # mascara que define las zonas configuradas
    seq: int
    zonas_abiertas: int
    zonas_con_alarma: int
    zonas_inhibidas: int


    def __init__(self, email: str, pwd: str, panelid: str, controller: str, lifespan: int) -> None:
        """Initialise."""

        self.panelid = panelid
        self.user = GarnetHTTPUser(email=email, password=pwd)
        self.session_token = SessionData()             # Token de session
        self.partition_mask = 0
        self.zone_mask = 0
        self.devices = None
        self.controller_name = controller
        self.token_time_span = lifespan


    def connect(self):
        """Se conecta a WEB GARNET y obtiene la informacion de la cuenta y del panel actualizando el modelo de datos."""

        try:
            
            retries = 5
            while(retries > 0):             # En el proceso de obtener estado inicial es importante varios retries porque la WEB de Garnet es lenta
                try:
                    # Por prueba y error detecte que este servicio de GARNET suele fallar por lo que le configuré 5 reintentos
                    self.get_state()        # Actualiza status
                    retries = 0
                except GeneralGarnetError: # Si la API no responde conviene esperar
                    time.sleep(3)
                    if retries > 0:
                        retries = retries -1
                    else:
                        raise
        except Exception:            # Catch solo para debug porque la excepcion se reenvia
            _LOGGER.exception("Exception on connect")
            raise


    def __token(self, force_get_state: bool = False) -> str:
        """Esta funcion devuelve el token de autenticacion si es mas viejo que lo configurado."""

        _span = time.time() - self.session_token.creation
        _LOGGER.debug("Token timespan is %d with max configured is %d", _span, self.token_time_span)
        if _span > self.token_time_span:
            self.__login()
            force_get_state = True
        if force_get_state:
            self.get_state()
        return self.session_token.token


    def __login(self) -> None:
        """Obtiene token de sesion."""
        _LOGGER.info("Executing Login() method")

        body = { }
        body["email"] = self.user.email
        body["password"] = self.user.password

        header = {}
        header["x-client-web"] = "1"

        retry = RETRY_LOGIN_ON_IRRESPONSIVE
        timeout = WAIT_ON_LOGIN_IRRESPONSIVE
        error = None

        try:
            while retry > 0:

                url = f"https://{GARNETAPIURL}/users_api/v1/auth/login"
                _LOGGER.debug("Executing POST on %s with body=%s and header=%s...", url, json.dumps(body), json.dumps(header))
                r = requests.post(url, json=body, headers=header, timeout=5)
                if r.status_code == 200:
                    response = r.json()
                    if(response.get("success")):
                        if retry == 3:
                            _LOGGER.info("Successful login to GARNET http")
                        else:
                            _LOGGER.warning("Successful login to GARNET http after %d tries",(4 - retry))
                        self.session_token.token = response["accessToken"]
                        self.session_token.creation = time.time()
                        self.seq = 1
                        if self.user.name is None:
                            # En el primer login completa los datos del usuario que usa para loguearse
                            self.user.name = f"{response["userData"]["nombre"]} {response["userData"]["apellido"]}"
                        error = None
                    elif("message" in response):
                        _LOGGER.error("Received 200 OK %s on login", response["message"])
                        error = f"Error 200 OK {response["message"]} on login"
                    else:
                        _LOGGER.error("Invalid response %s but 200 OK on login", str(response))
                        error = f"Invalid JSON {response!s} with 200 OK on login"
                    break
                if r.status_code == 504:
                    # En estos casos se esperan wait seconds y se reintenta hasta xxx veces
                    # 504 --> No se recibio respuesta en el tiempo maximo esperado
                    _LOGGER.warning("Received code %d on login. Message %s%s", r.status_code, r.text, f". Retry in {timeout} seconds" if retry > 1 else "")
                    error = f"Error code {r.status_code} with message {r.text} on login"
                    retry -= 1
                    time.sleep(timeout)
                else:
                    _LOGGER.warning("Received code %d on login. Message %s", r.status_code, r.text)
                    error = f"Error code {r.status_code} with message {r.text} on login"
                    break

        except Exception as err:  # noqa: BLE001
            error = f"login returned exception name {type(err).__name__} with description {err}"
            _LOGGER.error(error)

        if error:
            raise GeneralGarnetError(error)


    def __collect_system_info(self) -> None:
        """Obtiene informacion de zonas y sistema GARNET."""

        _LOGGER.info("Executing __collect_system_info() method")

        error = None

        try:
            _token = self.__token()
            header = {}
            header["x-client-web"] = "1"
            header["x-access-token"] = _token


            url = f"https://{GARNETAPIURL}/users_api/v1/systems/{self.panelid}"
            _LOGGER.debug("Executing GET on %s with no body and header=%s...", url, json.dumps(header))
            r = requests.get(url, headers=header, timeout=5)
            if r.status_code == 200:
                response = r.json()
                if(response.get("success")):
                    _LOGGER.info("Successful on __collect_system_info() method call")
                    if self.user.arm_permision is None:
                        self.user.arm_permision = response["message"]["sistema"]['userPermissions']["atributos"]["puedeArmar"]
                        self.user.disarm_permision = response["message"]["sistema"]['userPermissions']["atributos"]["puedeDesarmar"]
                        self.user.disable_zone_permision = response["message"]["sistema"]['userPermissions']["atributos"]["puedeInhibirZonas"]
                        self.user.horn_permision = response["message"]["sistema"]['userPermissions']["atributos"]["puedeInteractuarConSirena"]
                    if(self.system is None):
                        if response["message"]["sistema"]["id"] == self.panelid:
                            self.system = GarnetPanelInfo( id = response["message"]["sistema"]["id"], guid = response["message"]["sistema"]["id"], name = response["message"]["sistema"]["nombre"])
                            self.system.model = response["message"]["sistema"]["programation"]["data"]["alarmPanel"]["model"]
                            self.system.version = response["message"]["sistema"]["programation"]["data"]["alarmPanel"]["version"]
                            self.system.modelName = response["message"]["sistema"]["programation"]["data"]["alarmPanel"]["modelName"]
                            self.system.versionName = response["message"]["sistema"]["programation"]["data"]["alarmPanel"]["versionName"]
                        else:
                            error = f"El sistema con id {self.panelid} no se encuentra registrado en Garnet Control"

                    if error is None and self.devices is None:    # Se construye la estructura inicial de dispositivos

                        self.devices = []
                        for partition in response["message"]["sistema"]["programation"]["data"]["partitions"]:
                            if partition["enabled"]:
                                self.partition_mask = self.partition_mask | (2 ** (partition["number"] - 1))
                                self.devices.append(GarnetEntity(device_id=partition["number"]  + PARTITION_BASE_ID,
                                                                device_unique_id=f"{self.controller_name}_P_{partition["number"] }",
                                                                device_type=DeviceType.PARTITION, name=partition["name"],
                                                                alarmed=None, native_state="Unknown", uptime=0, icon=None))

                        for zone in response["message"]["sistema"]["programation"]["data"]["zones"]:
                            if zone["enabled"]:
                                self.zone_mask = self.zone_mask | (2 ** (zone["number"] - 1))
                                self.devices.append(GarnetEntity(device_id=zone["number"] + ZONE_BASE_ID, device_unique_id=f"{self.controller_name}_Z_{zone["number"]}",
                                                                device_type=DeviceType.ZONE, name=zone.get("name", ""),
                                                                alarmed=None, native_state="Unknown", uptime=0,
                                                                icon=Zone.translate_icon(icon=zone.get("icon", "0"))))

                        self.devices.append(GarnetEntity(device_id=HOWLER_BASE_ID, device_unique_id=f"{self.controller_name}_S_1",device_type=DeviceType.HOWLER,
                                                        name="Sirena", alarmed=False, native_state=None, uptime=0, icon="mdi:alarm-bell"))
                        self.devices.append(GarnetEntity(device_id=POLICEBUTTON_BASE_ID, device_unique_id=f"{self.controller_name}_B_1",device_type=DeviceType.BUTTON,
                                                        name="Panico", alarmed=False, native_state="Unknown", uptime=0, icon="mdi:police-badge-outline"))
                        self.devices.append(GarnetEntity(device_id=DOCTORBUTTON_BASE_ID, device_unique_id=f"{self.controller_name}_B_2",device_type=DeviceType.BUTTON,
                                                        name="Incendio", alarmed=False, native_state="Unknown", uptime=0, icon="mdi:fire-alert"))
                        self.devices.append(GarnetEntity(device_id=FIREBUTTON_BASE_ID, device_unique_id=f"{self.controller_name}_B_3",device_type=DeviceType.BUTTON,
                                                        name="Medico", alarmed=False, native_state="Unknown", uptime=0, icon="mdi:doctor"))
                        self.devices.append(GarnetEntity(device_id=TIMEDPANICBUTTON_BASE_ID, device_unique_id=f"{self.controller_name}_B_4",device_type=DeviceType.BUTTON,
                                                        name="Panico demorado", alarmed=False, native_state="Unknown", uptime=0, icon="mdi:alarm"))
                        self.devices.append(GarnetEntity(device_id=REFRESHBUTTON_BASE_ID, device_unique_id=f"{self.controller_name}_B_8",device_type=DeviceType.BUTTON,
                                                        name="Refrescar estado", alarmed=False, native_state="Unknown", uptime=0, icon="mdi:refresh"))
                        self.devices.append(GarnetEntity(device_id=COMM_BASE_ID, device_unique_id=f"{self.controller_name}_X_1",device_type=DeviceType.TEXT_SENSOR,
                                                        name="Comunicador", alarmed=False, native_state="Unknown", uptime=0, icon="mdi:wifi"))

                elif("message" in response):
                    _LOGGER.error("Received 200 OK %s when call __collect_system_info()", response["message"])
                    error = f"Error 200 OK {response["message"]} when calling __collect_system_info()"
                else:
                    _LOGGER.error("Received 200 OK but invalid json %s when call __collect_system_info()", str(response))
                    error = f"Error 200 OK with invalid json {response!s} when calling __collect_system_info()"
            else:
                _LOGGER.error("Received %d %s when call __collect_system_info()", r.status_code, r.text)
                error = f"Error code {r.status_code} with message {r.text} when calling __collect_system_info()"

        except Exception as err:
            error = f"__collect_system_info() returned Exception Name {type(err).__name__} with description {err}"
            _LOGGER.exception("Exception")

        if error:
            raise GeneralGarnetError(error)


    def __get_device_by_id__(self, device_id: int) -> GarnetEntity | None:
        """Devuelve un dispositivo."""

        for device in self.devices:
            if device.device_id == device_id:
                return device
        return None


    def __sequence(self, increment: int = 0) -> str:
        """Devuelve numero de sequencia consecutivo y limitado en 255."""

        # Despues de revisar la aplicacion me doy cuenta que el nro de secuencia se incrementa solo despues de enviar algunos comandos a la api
        self.seq = self.seq + increment
        if(self.seq == 256):
            self.seq = 0
        if increment > 0:
            return str(self.seq - 1).zfill(3)
        return str(self.seq).zfill(3)


    def __update_status(self, status: str) -> None:
        """Parseo del estado del panel."""

        # Nota: se obtiene de la funcion processStatus en js de la web de garnetcontrol

        _LOGGER.info("Executing __update_status() method")
        _LOGGER.debug("Se recibe trama %s", status)

        registroProblemas1 = int(status[1:3], 16) # No usado
        registroProblemas2 = int(status[3:5], 16) # No usado
        _LOGGER.debug("registroProblemas1 = %d y registroProblemas2 = %d",  registroProblemas1, registroProblemas2)

        self.zonas_abiertas = int(status[9:11], 16) + int(status[11:13], 16) * (256) + int(status[13:15], 16) * (256 ** 2) + int(status[15:17], 16) * (256 ** 3)
        _LOGGER.debug("Estado de apertura de zonas es %s", bin(self.zonas_abiertas))

        self.zonas_con_alarma = int(status[17:19], 16) + int(status[19:21], 16) * (256) + int(status[21:23], 16) * (256 ** 2) + int(status[23:25], 16) * (256 ** 3)
        _LOGGER.debug("Estado de alarma de zonas es %s", bin(self.zonas_con_alarma))

        self.zonas_inhibidas = int(status[25:27], 16) + int(status[27:29], 16) * (256) + int(status[29:31], 16) * (256 ** 2) + int(status[31:33], 16) * (256 ** 3)
        _LOGGER.debug("Estado de inhibicion de zonas es %s", bin(self.zonas_inhibidas))

        estadoDeParticiones1 = int(status[5:7], 16)
        if(len(status) > 37):
            estadoDeParticiones2 = int(status[35:37], 16)
            demorasPanel = int(status[37:39], 16)
        else:
            estadoDeParticiones2 = 0
            demorasPanel = 0
        _LOGGER.debug("estadoDeParticiones1 = %d, estadoDeParticiones2 = %d y demorasPanel = %d",  estadoDeParticiones1, estadoDeParticiones2, demorasPanel)

        flagArmado = False
        partitionStatus = [ "", "", "", ""]
        for i in range(4):
            if (estadoDeParticiones1 & (2 ** (7 - i))):
                partitionStatus[i] = "LISTO"
            else:
                partitionStatus[i] = "NO_LISTO"

            if (estadoDeParticiones1 & (2 ** (3 - i))) or (demorasPanel & (2 ** (7 - i))):
                partitionStatus[i] = "ARMADO"

            if (estadoDeParticiones2 & (2 ** (3 - i)) and (partitionStatus[i] == "ARMADO")):
                # DEMORADO
                partitionStatus[i] = "DEMORADO"
                flagArmado = True
            elif (estadoDeParticiones2 & (2 ** (7 - i)) and (partitionStatus[i] == "ARMADO")):
                # INSTANTANEO
                partitionStatus[i] = "INSTANTANEO"
                flagArmado = True

            if  self.partition_mask & (2 ** i):
                p = self.__get_device_by_id__(PARTITION_BASE_ID + i + 1)
                p.alarmed = False
                if partitionStatus[i] == "DEMORADO":
                    p.native_state = "home"
                    if self.zonas_con_alarma > 0:
                        p.alarmed = True        #TODO: confirmar si es correcto que se toma particion en alarma si las zonas estan en alarma
                elif partitionStatus[i] == "INSTANTANEO":
                    p.native_state = "away"
                    if self.zonas_con_alarma > 0:
                        p.alarmed = True        #TODO: confirmar si es correcto que se toma particion en alarma si las zonas estan en alarma
                elif partitionStatus[i] == "LISTO":
                    p.native_state = "disarmed"
                else:
                    p.native_state = "unknown"
                _LOGGER.debug("Particion %d en estado %s (%s)",  i + 1, partitionStatus[i], p.native_state)
            else:
                _LOGGER.debug("Particion no configurada %d en estado %s",  i + 1, partitionStatus[i] )


        for i in range(32):
            m = (2 ** i)
            if  self.zone_mask & m:
                z = self.__get_device_by_id__(ZONE_BASE_ID + i + 1)
                z.alarmed = (self.zonas_con_alarma & m) != 0
                z.native_state = (1 if (self.zonas_abiertas & m)  != 0 else 0) + \
                                 (2 if (self.zonas_inhibidas & m) != 0 else 0) + \
                                 (4 if flagArmado else 0)  #TODO confirmar que es correcto. Se asume que todas las zonas estan armadas si alguna particion esta armada


        estadoDeSalidas = int(status[7:9], 16)
        _LOGGER.debug("Estado de salidas cableadas es %d ", estadoDeSalidas)
        howler = self.__get_device_by_id__(HOWLER_BASE_ID)
        howler.native_state = "on" if (estadoDeSalidas & 1) > 0 else "off"
        _LOGGER.debug("Sirena en estado %s", howler.native_state )

        estadoDeSalidasInalambricas = int(status[33:35], 16)
        _LOGGER.debug("Estado de salidas inalambricas es %d ", estadoDeSalidasInalambricas)


    def get_state(self) -> None:
        """Chequeo de estado."""

        _LOGGER.info("Executing get_state() method")
        
        if self.devices is None:
            self.__collect_system_info()    # Levanta configuracion de la cuenta
      
       
        error = None

        retry = RETRY_LOGIN_ON_IRRESPONSIVE
        timeout = WAIT_ON_LOGIN_IRRESPONSIVE

        try:
            while retry > 0:

                _token = self.__token()

                body = {}
                body["seq"] = self.__sequence(increment = 1)
                body["timeout"] = GARNETAPITIMEOUT

                header = {}
                header["x-client-web"] = "1"
                header["x-access-token"] = _token
                header["Content-Type"] = 'application/json'


                url = f"https://{GARNETAPIURL}/users_api/v1/systems/{self.panelid}/commands/state"
                _LOGGER.debug("Executing POST on %s with body=%s and header=%s...", url, json.dumps(body), json.dumps(header))
                r = requests.post(url, json=body, headers=header, timeout=15)
                if r.status_code == 200:
                    response = r.json()
                    if(response.get("success")):
                        if retry == 3:
                            _LOGGER.info("Successful on get_state() method call")
                        else:
                            _LOGGER.warning("Successful on get_state() method call after %d tries",(4 - retry))
                        self.__update_status(response["message"]["status"])
                        error = None
                    elif("message" in response):
                        _LOGGER.error("Received 200 OK %s on get_state", response["message"])
                        error = f"Error 200 OK {response["message"]} on get_state"
                    else:
                        _LOGGER.error("Invalid response %s but 200 OK on get_state()", str(response))
                        error = f"Invalid JSON {response!s} with 200 OK on get_state()"
                    break
                if r.status_code == 504:
                    # En estos casos se esperan wait seconds y se reintenta hasta xxx veces
                    # 504 --> No se recibio respuesta en el tiempo maximo esperado
                    _LOGGER.warning("Received code %d on get_state(). Message %s%s", r.status_code, r.text, f". Retry in {timeout} seconds" if retry > 1 else "")
                    error = f"Error code {r.status_code} with message {r.text} on get_state()"
                    retry -= 1
                    time.sleep(timeout)
                else:
                    _LOGGER.warning("Received code %d on get_state(). Message %s", r.status_code, r.text)
                    error = f"Error code {r.status_code} with message {r.text} on get_state()"
                    break

        except Exception as err:  # noqa: BLE001
            error = f"get_state() returned exception name {type(err).__name__} with description {err}"
            _LOGGER.error(error)

        if error:
            raise GeneralGarnetError(error)


    def arm_system(self, partition: int, mode: str) -> None:
        """Armado de particion."""

        _LOGGER.info("Executing arm_system(%d) method", partition)

        # Chequeo si el usuario tiene permisos
        if(not self.user.arm_permision):
            raise GarnetPermissionError(f"User {self.user.name} has no permision for arming the partition")

        try:
            _token=self.__token(force_get_state = True)   # Obtiene el token, si no puede genera una excepcion
            if self.zonas_abiertas > 0:
                raise GeneralGarnetError("Open zones, Partition cannot be armed")

            error = None

            body = {}
            body["seq"] = self.__sequence(increment = 1)
            body["partNumber"] = str(partition)
            body["timeout"] = GARNETAPITIMEOUT

            header = {}
            header["x-client-web"] = "1"
            header["x-access-token"] = _token
            header["Content-Type"] = 'application/json'

            command = ("delayed" if mode == "home" else "away")

            url = f"https://{GARNETAPIURL}/users_api/v1/systems/{self.system.id}/commands/arm/{command}"
            _LOGGER.debug("Executing POST on %s with body=%s and header=%s...", url, json.dumps(body),json.dumps(header))
            r = requests.post(url, json=body, headers=header, timeout=5)
            if r.status_code == 200:
                response = r.json()
                if(response.get("success")):
                    _LOGGER.info("Successful on arm_system() method call")
                    self.__update_status(response["message"]["status"])
                elif("message" in response):
                    _LOGGER.error("Armando el panel se recibió %s", response["message"])
                    error = f"Error {response["message"]} al intentar armar el panel"
                else:
                    _LOGGER.error("Armando el panel se recibió un json inválido %s", str(response))
                    error = f"Invalid JSON {response!s}"
            else:
                _LOGGER.error("Armando el panel se recibió codigo %d con mensaje %s", r.status_code, r.text)
                error = f"Error code {r.status_code} with message {r.text}"

        except Exception as err:
            error = f"Arm system returned Exception Name {type(err).__name__} with description {err}"
            _LOGGER.exception("Exception")

        if error:
            raise GeneralGarnetError(error)


    def disarm_system(self, partition: int) -> None:
        """Desarmado de particion."""

        _LOGGER.info("Executing disarm_system(%d) method", partition)

       # Chequeo si el usuario tiene permisos
        if(not self.user.disarm_permision):
            raise GarnetPermissionError(f"User {self.user.name} has no permision for disarming the partition")

        try:
            _token=self.__token()   # Obtiene el token, si no puede genera una excepcion
            error = None

            body = {}
            body["seq"] = self.__sequence(increment = 1)
            body["partNumber"] = str(partition)
            body["timeout"] = GARNETAPITIMEOUT

            header = {}
            header["x-client-web"] = "1"
            header["x-access-token"] = _token
            header["Content-Type"] = 'application/json'

            url = f"https://{GARNETAPIURL}/users_api/v1/systems/{self.system.id}/commands/disarm"
            _LOGGER.debug("Executing POST on %s with body=%s and header=%s...", url, json.dumps(body),json.dumps(header))
            r = requests.post(url, json=body, headers=header, timeout=5)
            if r.status_code == 200:
                response = r.json()
                if(response.get("success")):
                    _LOGGER.info("Successful on disarm_system() method call")
                    self.__update_status(response["message"]["status"])
                elif("message" in response):
                    _LOGGER.error("Desarmando el panel se recibió %s", response["message"])
                    error = f"Error {response["message"]} al intentar desarmar el panel"
                else:
                    _LOGGER.error("Desarmando el panel se recibió un json inválido %s", str(response))
                    error = f"Invalid JSON {response!s}"
            else:
                _LOGGER.error("Desarmando el panel se recibió codigo %d con mensaje %s", r.status_code, r.text)
                error = f"Error code {r.status_code} with message {r.text}"

        except Exception as err:
            error = f"Disarm system returned Exception Name {type(err).__name__} with description {err}"
            _LOGGER.exception("Exception")

        if error:
            raise GeneralGarnetError(error)


    def horn_control(self, mode: str) -> None:
        """Control de sirena."""

        _LOGGER.info("Executing horn_control(%s) method", mode)

       # Chequeo si el usuario tiene permisos
        if(not self.user.horn_permision):
            raise GarnetPermissionError(f"User {self.user.name} hhas no permision for control the horn")

        try:
            _token=self.__token()   # Obtiene el token, si no puede genera una excepcion

            body = {}
            body["seq"] = self.__sequence(increment = 1)
            body["timeout"] = GARNETAPITIMEOUT

            header = {}
            header["x-client-web"] = "1"
            header["x-access-token"] = _token
            header["Content-Type"] = 'application/json'

            error = None

            command = ("set_bell" if mode == "on" else "unset_bell")
            url = f"https://{GARNETAPIURL}/users_api/v1/systems/{self.system.id}/commands/{command}"
            _LOGGER.debug("Executing POST on %s with body=%s and header=%s...", url, json.dumps(body),json.dumps(header))
            r = requests.post(url, json=body, headers=header, timeout=5)
            if r.status_code == 200:
                response = r.json()
                if(response.get("success")):
                    _LOGGER.info("Successful on horn_control() method call")
                    self.__update_status(response["message"]["status"])
                elif("message" in response):
                    _LOGGER.error("Controlando la sirena se recibió %s", response["message"])
                    error = f"Error {response["message"]} al intentar controlar la sirena"
                else:
                    _LOGGER.error("Controlando la sirena se recibió un json inválido %s", str(response))
                    error = f"Invalid JSON {response!s}"
            else:
                _LOGGER.error("Controlando la sirena se recibió codigo %d con mensaje %s", r.status_code, r.text)
                error = f"Error code {r.status_code} with message {r.text}"

        except Exception as err:
            error = f"Control the horn returned Exception Name {type(err).__name__} with description {err}"
            _LOGGER.exception("Exception")

        if error:
            raise GeneralGarnetError(error)


    def report_emergency(self, type: str, partition_id: int, partition_name: str) -> None:
        """Genera una emergencia."""

        _LOGGER.info("Executing report_emergency(%s,%d,%s) method", type, partition_id, partition_name)

        try:
            _token=self.__token()   # Obtiene el token, si no puede genera una excepcion

            body = {}
            body["partition"] = {}
            body["partition"]["name"] = partition_name
            body["partition"]["number"] = partition_id
            body["partition"]["enabled"] = True
            body["partition"]["editedName"] = partition_name
            body["emergencyType"] = 1 if type == "Medico" else (3 if type == "Incendio" else (4 if type == "Panico" else 2))
            body["timeout"] = GARNETAPITIMEOUT

            header = {}
            header["x-client-web"] = "1"
            header["x-access-token"] = _token
            header["Content-Type"] = 'application/json'

            error = None

            url = f"https://{GARNETAPIURL}/users_api/v1/systems/{self.system.id}/commands/emergency"
            _LOGGER.debug("Executing POST on %s with body=%s and header=%s...", url, json.dumps(body),json.dumps(header))
            r = requests.post(url, json=body, headers=header, timeout=5)
            if r.status_code == 200:
                response = r.json()
                if(response.get("success")):
                    _LOGGER.info("Successful on report_emergency() method call")
                    _LOGGER.info(response["message"]["response"])
                elif("message" in response):
                    # TODO: Determinar que hacer con este error
                    _LOGGER.error("Generando reporte de emergencia se recibió %s", response["message"])
                    error = f"Error {response["message"]} al intentar generar reporte de emergencia"
                else:
                    # TODO: Determinar que hacer con este error
                    _LOGGER.error("Generando reporte de emergencia se recibió un json inválido %s", str(response))
                    error = f"Invalid JSON {response!s}"
            else:
                # TODO: Determinar que hacer con este error
                _LOGGER.error("Generando reporte de emergencia se recibió codigo %d con mensaje %s", r.status_code, r.text)
                error = f"Error code {r.status_code} with message {r.text}"

        except Exception as err:
                # TODO: Determinar que hacer con este error
            error = f"Reporting an emergency system returned Exception Name {type(err).__name__} with description {err}"
            _LOGGER.exception("Exception")

        if error:
            raise GeneralGarnetError(error)


    def bypass_zone(self, zone: int, mode: int) -> None:
        """Bypass de zona."""
        #TODO: Implementar
        # BYPASS de ZONA
        #https://web.garnetcontrol.app/users_api/v1/systems/<id_sistema>/commands/bypass/<nro_zona>
        #body: {"seq":"002","partNumber":1,"timeout":4500}
        #respuesta: {"success":true,"message":{"response":"COMANDO ENVIADO CON EXITO","status":"10000F000000000000000000020000000000000"}}

        # Quitar BYPASS
        #https://web.garnetcontrol.app/users_api/v1/systems/<id_sistema>/commands/unbypass/<nro_zona>
        #respuesta: {"success":true,"message":{"response":"COMANDO ENVIADO CON EXITO","status":"10000F000000000000000000020000000000000"}}


    def program_panic(self, time: time) -> None:
        """Programa un panico a una hora especifica."""
        #TODO: Implementar
        # {"timeToGeneratePanic":1746310062654,"partition":{"name":"Partición principal","number":1,"enabled":true,"editedName":"Partición principal"},"seq":"013","timeout":4500}
        # POST https://web.garnetcontrol.app/users_api/v1/systems/a10050008d96/setpanic


    def delay_panic(self, time: time) -> None:
        """Suma 5 minutos a la programacion de panico."""
        #TODO: Implementar
        # {"partition":{"name":"Partición principal","number":1,"enabled":true,"editedName":"Partición principal"},"timeout":4500}
        # POST https://web.garnetcontrol.app/users_api/v1/systems/a10050008d96/setpanic


    def reset_panic(self) -> None:
        """Anula la programacion de panico."""
        #TODO: Implementar
        # {"partition":{"name":"Partición principal","number":1,"enabled":true,"editedName":"Partición principal"},"seq":"014","timeout":4500}
        # POST https://web.garnetcontrol.app/users_api/v1/systems/a10050008d96/resetpanic


    def get_panics(self) -> None:
        """Obtiene la programacion de panico activa."""
        #TODO: Implementar
        #sin header
        #https://web.garnetcontrol.app/users_api/v1/systems/a10050008d96/panics
        #{"success":true,"message":{"pendingPanics":[true,true,true,true]}}


    def get_system_info(self) -> None:
        """Obtiene la informacion de sistemas."""
        #TODO: Implementar
        #sin header
        #https://web.garnetcontrol.app/users_api/v1/systems/
        #{"success":true,"message":{"sistemas":[{"estados":{"1":{"estado":"disarm","nombre":"Partición principal"},"2":{"estado":"0","nombre":"Partición 2"},"3":{"estado":"0","nombre":"Partición 3"},"4":{"estado":"0","nombre":"Partición 4"}},"partitionKeys":{"0":"1111","1":"1111","2":"2222","3":"3333","4":"4444"},"id":"a10050008d96","nombre":"DelProgreso","_id":"60f785fac60d7c0016e4c3a4","icono":0}],"sistemasCompartidos":[]}}


    def get_timeout(self) -> None:
        """Obtiene el timeout de sistema."""
        #TODO: Implementar
        #sin header
        #https://web.garnetcontrol.app/users_api/v1/systems/a10050008d96/timeout
        #{"success":true,"message":{"timeout":4500}}


    def get_lastupdate(self) -> None:
        """Obtiene fecha del ultimo update."""
        #TODO: Implementar
        #sin header
        #https://web.garnetcontrol.app/users_api/v1/systems/a10050008d96/lastUpdate
        #{"success":true,"message":{"lastUpdate":"2024-10-15T03:28:44.993Z","lastEvent":"2024-10-14T11:19:09.045Z"}}


    def get_lasteventreport(self) -> None:
        """Obtiene el fecha del ultimo reporte de eventos."""
        #TODO: Implementar
        #https://web.garnetcontrol.app/users_api/v1/systems/a10050008d96/lastEventReport
        #{"success":true,"message":1746308980819}




