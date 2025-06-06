"""Funciones de manejo de panel a traves de la api http de Garnet"""

import logging
import http.client
import json
import time

from enum import StrEnum
from dataclasses import dataclass

from .const import (GARNETAPIURL, TOKEN_TIME_SPAN, PARTITION_BASE_ID, ZONE_BASE_ID, HOWLER_BASE_ID, POLICEBUTTON_BASE_ID,
                     DOCTORBUTTON_BASE_ID, FIREBUTTON_BASE_ID, TIMEDPANICBUTTON_BASE_ID, COMM_BASE_ID, GARNETAPITIMEOUT, REFRESHBUTTON_BASE_ID)

from .httpdata import GarnetHTTPUser, GarnetPanelInfo, Zone,Partition


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
    device_id: int
    device_unique_id: str
    name: str
    device_type: DeviceType
    native_state: int | bool | str
    alarmed: bool
    icon: str 
    uptime: float


    def __str__(self):
        return f"<GarnetEntity: device_id: {str(self.device_id)}, device_unique_id: \"{self.device_unique_id}\", name: \"{self.name}\", device_type: \"{str(self.device_type)}\", native_state: \"{str(self.native_state)}\", alarmed: \"{str(self.alarmed)}\", uptime: {str(self.uptime)}, icon:{("None" if self.icon is None else ("\"" + str(self.icon) + "\""))}>"


class SessionData:
    """Datos de la session"""
    token: str = None
    creation: time = None

    def __init__(self, token: str = None, creation: time = 0) -> None:
        self.token = token
        self.creation = creation


class HTTP_API:

    user :   GarnetHTTPUser             # Datos de la cuenta
    devices: list[GarnetEntity]         # dispositivos
    system:  GarnetPanelInfo = None     # Datos del panel
    partition_mask: int                 # mascara que define las particiones configuradas
    zone_mask: int                      # mascara que define las zonas configuradas
    seq: int
    

    def __init__(self, email: str, pwd: str, panelid: str, controller: str) -> None:        
        """Initialise."""
        self.panelid = panelid
        self.user = GarnetHTTPUser(email=email, password=pwd)
        self.session_token = SessionData()             # Token de session
        self.partition_mask = 0
        self.zone_mask = 0
        self.devices = None
        self.controller_name = controller


    def connect(self):
        """Se conecta a la api y obtiene la informacion de la cuenta y panel actualizando el modelo de datos """
        try:
            self.__collect_system_info()    # Levanta configuracion 
            retries = 5
            while(retries > 0):             # En el proceso de obtener estado inicial es importante varios retries porque la WEB de Garnet es lenta
                try:
                    self.get_state()        # Actualiza status
                    retries = 0
                except UnresponsiveGarnetAPI as err: # Si la API no responde conviene esperar
                    time.sleep(3)
                    if retries > 0:
                        retries = retries -1
                    else:
                        raise(err)
        except Exception as err:            # Catch solo para debug porque la excepcion se reenvia
            _LOGGER.exception(err)
            raise err


    def __token(self) -> str:
        if (time.time() - self.session_token.creation) > TOKEN_TIME_SPAN:
            self.__login()            #TODO catchear excepcion y plan de recovery
        return self.session_token.token


    def __login(self) -> None:
        """Obtiene token de sesion."""
        body = {}
        body["email"] = self.user.email
        body["password"] = self.user.password

        response = {}
        try:
            conn = http.client.HTTPSConnection(GARNETAPIURL)
            conn.request("POST", "/users_api/v1/auth/login", json.dumps(body), { 'Content-Type': 'application/json' })
            response = json.loads(conn.getresponse().read().decode("utf-8"))
            conn.close()
        except Exception as err:
            _LOGGER.exception(err)
            raise InvokeGarnetAPIException(err)
        if("success" in response and response["success"]):
            _LOGGER.info("Successful login to GARTNET http")            
            self.session_token.token = response["accessToken"]
            self.session_token.creation = time.time()
            self.seq = 1
            if self.user.name is None:                  # En el primer login completa los datos del usuario que usa para loguearse
                self.user.name = f"{response["userData"]["nombre"]} {response["userData"]["apellido"]}" 
        else:
            if("message" in response):
                if((response["message"] == "No se recibió respuesta del sistema en el tiempo máximo esperado") or (response["message"] == "Ya hay un comando en progreso")):
                    raise UnresponsiveGarnetAPI(response["message"])   
                else:                
                    raise InvokeGarnetAPIException(response["message"])
            else:
                raise InvokeGarnetAPIException(f"Invalid JSON {str(response)}")


    def __collect_system_info(self) -> None:
        """Obtiene informacion de zonas y sistema GARNET."""
        response = {}
        try:
            conn = http.client.HTTPSConnection(GARNETAPIURL)
            conn.request("GET", "/users_api/v1/systems/" + self.panelid , '', { 'x-access-token': self.__token() })
            response = json.loads(conn.getresponse().read().decode("utf-8"))
            conn.close()
        except Exception as err:
            _LOGGER.exception(err)
            raise InvokeGarnetAPIException(err)
        if("success" in response and response["success"]):
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
                    raise SystemDoesNotExistException(f"El sistema con id {self.panelid} no se encuentra registrado en Garnet Control")

            if self.devices == None:    # Se construye la estructura inicial de dispositivos

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
                                                        device_type=DeviceType.ZONE, name=zone["name"] if ("name" in zone) else "", 
                                                        alarmed=None, native_state="Unknown", uptime=0, 
                                                        icon=Zone.translate_icon(icon=zone["icon"] if ("icon" in zone) else "0")))
            
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

        else:
            if("message" in response):
                if((response["message"] == "No se recibió respuesta del sistema en el tiempo máximo esperado") or (response["message"] == "Ya hay un comando en progreso")):
                    raise UnresponsiveGarnetAPI(response["message"])
                else:
                    raise InvokeGarnetAPIException(response["message"])
            else:
                raise InvokeGarnetAPIException(f"Invalid JSON {str(response)}")


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
        if(self.seq == 256): self.seq = 0
        if increment > 0:
            return str(self.seq - 1).zfill(3)
        return str(self.seq).zfill(3)


    def __update_status(self, status: str) -> None:
        """Parseo del estado del panel"""
        # Nota: se obtiene de la funcion processStatus en js de la web de garnetcontrol

        _LOGGER.debug("Se recibe trama " + status)

        registroProblemas1 = int(status[1:3], 16) # No usado
        registroProblemas2 = int(status[3:5], 16) # No usado
        _LOGGER.debug("registroProblemas1 = %d y registroProblemas2 = %d",  registroProblemas1, registroProblemas2)

        estadoDeParticiones1 = int(status[5:7], 16)
        estadoDeParticiones2 = int(status[35:37], 16)
        demorasPanel = int(status[37:39], 16)
        _LOGGER.debug("estadoDeParticiones1 = %d, estadoDeParticiones2 = %d y demorasPanel = %d",  estadoDeParticiones1, estadoDeParticiones2, demorasPanel)

        partitionStatus = [ "", "", "", ""]
        for i in range(0,4):
            if (estadoDeParticiones1 & (2 ** (7 - i))):
                partitionStatus[i] = "LISTO"
            else:
                partitionStatus[i] = "NO_LISTO"

            if (estadoDeParticiones1 & (2 ** (3 - i))) or (demorasPanel & (2 ** (7 - i))):
                partitionStatus[i] = "ARMADO"

            if (estadoDeParticiones2 & (2 ** (3 - i)) and (partitionStatus[i] == "ARMADO")):
                # DEMORADO
                partitionStatus[i] = "DEMORADO"
            elif (estadoDeParticiones2 & (2 ** (7 - i)) and (partitionStatus[i] == "ARMADO")):
                # INSTANTANEO
                partitionStatus[i] = "INSTANTANEO"

            if  self.partition_mask & (2 ** i):
                p = self.__get_device_by_id__(PARTITION_BASE_ID + i + 1)
                if partitionStatus[i] == "DEMORADO":
                    p.native_state = "home"
                elif partitionStatus[i] == "INSTANTANEO":
                    p.native_state = "away"
                elif partitionStatus[i] == "LISTO":
                    p.native_state = "disarmed"
                else:
                    p.native_state = "unknown"
                _LOGGER.debug("Particion %d en estado %s (%s)",  i + 1, partitionStatus[i], p.native_state)
            else:
                _LOGGER.debug("Particion no configurada %d en estado %s",  i + 1, partitionStatus[i] )

        zonasAbiertas = []
        zonasAbiertas.append(int(status[9:11], 16))
        zonasAbiertas.append(int(status[11:13], 16))
        zonasAbiertas.append(int(status[13:15], 16))
        zonasAbiertas.append(int(status[15:17], 16))
        _LOGGER.debug("Estado de apertura de zonas (1 a 8)=%d, (9 a 16)=%d, (17 a 24)=%d y (25 a 32)=%d", zonasAbiertas[0], zonasAbiertas[1], zonasAbiertas[2], zonasAbiertas[3])

        zonasEnAlarma = []
        zonasEnAlarma.append(int(status[17:19], 16))
        zonasEnAlarma.append(int(status[19:21], 16))
        zonasEnAlarma.append(int(status[21:23], 16))
        zonasEnAlarma.append(int(status[23:25], 16))
        _LOGGER.debug("Estado de alarma de zonas (1 a 8)=%d, (9 a 16)=%d, (17 a 24)=%d y (25 a 32)=%d", zonasEnAlarma[0], zonasEnAlarma[1], zonasEnAlarma[2], zonasEnAlarma[3])

        zonasInhibidas = []
        zonasInhibidas.append(int(status[25:27], 16))
        zonasInhibidas.append(int(status[27:29], 16))
        zonasInhibidas.append(int(status[29:31], 16))
        zonasInhibidas.append(int(status[31:33], 16))
        _LOGGER.debug("Estado de inhibicion de zonas (1 a 8)=%d, (9 a 1update_status(6)=%d, (17 a 24)=%d y (25 a 32)=%d", zonasInhibidas[0], zonasInhibidas[1], zonasInhibidas[2], zonasInhibidas[3])

        estadoDeSalidas = int(status[7:9], 16)
        _LOGGER.debug("Estado de salidas cableadas es %d ", estadoDeSalidas)

        estadoDeSalidasInalambricas = int(status[33:35], 16)
        _LOGGER.debug("Estado de salidas inalambricas es %d ", estadoDeSalidasInalambricas)


        _LOGGER.debug("Mascara de estado de zona: 0x%s", status[9:11])
        _LOGGER.debug("Mascara de estado de alarma: 0x%s", status[11:19])
        _LOGGER.debug("Mascara de estado de inhibicion: 0x%s", status[19:27])
        m_open = int(status[9:11], 16) & 255
        m_alm = int(status[11:19], 16) & 255
        m_inh = int(status[19:27], 16) & 255
        s = 16
        while(s > 0):
            z = 17 - s
            v_open = m_open & 1
            v_alm = m_alm & 1
            v_inh = m_inh & 1
            if self.zone_mask & (2 ** (z - 1)):
                zone = self.__get_device_by_id__(ZONE_BASE_ID + z)
                zone.alarmed = v_alm != 0
                zone.native_state = (1 if v_open != 0 else 0) + (2 if v_inh != 0 else 0)  # + (4 if v_armed != 0 else 0)  #TODO
            m_open = m_open >> 1
            m_alm = m_alm >> 1
            m_inh = m_inh >> 1
            s = s - 1                    

        m = int(status[8:9], 16) & 1
        _LOGGER.debug("Mascara de sirena: 0x%s / %s", status[8:9], "Sirena apagada" if(m == 0) else "Sirena activada")
        howler = self.__get_device_by_id__(HOWLER_BASE_ID)
        howler.native_state = "on" if m > 0 else "off"

        m = int(status[5:9], 16)

        for p in self.devices:
            if p.device_type == DeviceType.PARTITION:
                #TODO: Esto esta maaaaaaaaal hay que sacar la informacion de forma correcta de la trama para todas las particiones
                p.alarmed = (int(status[11:19], 16) & 255) != 0 
 

    def get_state(self) -> None:

        """Chequeo de estado."""
        body = {}
        body["seq"] = self.__sequence()
        body["timeout"] = GARNETAPITIMEOUT

        response = {}
        try:
            conn = http.client.HTTPSConnection(GARNETAPIURL)
            conn.request("POST", "/users_api/v1/systems/" + self.panelid + "/commands/state", json.dumps(body), { 'x-access-token': self.__token(), 'Content-Type': 'application/json' })
            response = json.loads(conn.getresponse().read().decode("utf-8"))
            conn.close()
        except Exception as err:
            _LOGGER.exception(err)
            raise InvokeGarnetAPIException(err)

        if("success" in response and response["success"]):
            self.__update_status(response["message"]["status"])
        else: 
            if("message" in response):
                if((response["message"] == "Failed to authenticate token.") or (response["message"] == "No token provided.")):
                    _LOGGER.warning(response["message"])
                    raise Exception(response["message"])        # Esto no deberia ocurrir porque se supone que el tiempo de vida del token esta controlado
                elif((response["message"] == "No se recibió respuesta del sistema en el tiempo máximo esperado") or (response["message"] == "Ya hay un comando en progreso")):
                    raise UnresponsiveGarnetAPI(response["message"])
                else:                
                    raise InvokeGarnetAPIException(response["message"])
            else:
                raise InvokeGarnetAPIException("Invalid JSON " + str(response))


    def arm_system(self, partition: int, mode: str) -> None:
        """Armado de particion."""

        if(not self.user.arm_permision):
            raise PermissionError("User " + self.user.name + " has no permision for arming the partition")

        #TODO: Si hay zonas abiertas no armar

        body = {}
        body["seq"] = self.__sequence(increment = 1)
        body["partNumber"] = str(partition)
        body["timeout"] = GARNETAPITIMEOUT

        response = {}
        try:
            command = ("delayed" if mode == "home" else "away")
            conn = http.client.HTTPSConnection(GARNETAPIURL)
            conn.request("POST", "/users_api/v1/systems/" + self.system.id + "/commands/arm/" + command, json.dumps(body), { 'x-access-token': self.__token(), 'Content-Type': 'application/json' })
            response = json.loads(conn.getresponse().read().decode("utf-8"))
            conn.close()
        except Exception as err:
            _LOGGER.exception(err)
            raise InvokeGarnetAPIException(err)

        if("success" in response and response["success"]):
            self.__update_status(response["message"]["status"])
        else: 
            if("message" in response):
                if((response["message"] == "Failed to authenticate token.") or (response["message"] == "No token provided.")):
                    _LOGGER.warning(response["message"])
                    raise Exception(response["message"])        # Esto no deberia ocurrir porque se supone que el tiempo de vida del token esta controlado
                elif((response["message"] == "No se recibió respuesta del sistema en el tiempo máximo esperado") or (response["message"] == "Ya hay un comando en progreso")):
                    raise UnresponsiveGarnetAPI(response["message"])
                else:                
                    raise InvokeGarnetAPIException(response["message"])
            else:
                raise InvokeGarnetAPIException("Invalid JSON " + str(response))


    def disarm_system(self, partition: int) -> None:
        """Desarmado de particion."""

        if(not self.user.disarm_permision):
            raise PermissionError("User " + self.user.name + " has no permision for disarming the partition")

        body = {}
        body["seq"] = self.__sequence(increment = 1)
        body["partNumber"] = str(partition)
        body["timeout"] = GARNETAPITIMEOUT

        response = {}
        try:
            conn = http.client.HTTPSConnection(GARNETAPIURL)
            conn.request("POST", "/users_api/v1/systems/" + self.system.id + "/commands/disarm", json.dumps(body), { 'x-access-token': self.__token(), 'Content-Type': 'application/json' })
            response = json.loads(conn.getresponse().read().decode("utf-8"))
            conn.close()
        except Exception as err:
            _LOGGER.exception(err)
            raise InvokeGarnetAPIException(err)

        if("success" in response and response["success"]):
            self.__update_status(response["message"]["status"])
        else: 
            if("message" in response):
                if((response["message"] == "Failed to authenticate token.") or (response["message"] == "No token provided.")):
                    _LOGGER.warning(response["message"])
                    raise Exception(response["message"])        # Esto no deberia ocurrir porque se supone que el tiempo de vida del token esta controlado
                elif((response["message"] == "No se recibió respuesta del sistema en el tiempo máximo esperado") or (response["message"] == "Ya hay un comando en progreso")):
                    raise UnresponsiveGarnetAPI(response["message"])
                else:                
                    raise InvokeGarnetAPIException(response["message"])
            else:
                raise InvokeGarnetAPIException("Invalid JSON " + str(response))


    def horn_control(self, mode: str) -> None:
        """Control de sirena."""

        if(not self.user.horn_permision):
            raise PermissionError("User " + self.user.name + " has no permision control the horn")

        body = {}
        body["seq"] = self.__sequence(increment = 1)
        body["timeout"] = GARNETAPITIMEOUT

        response = {}
        try:
            conn = http.client.HTTPSConnection(GARNETAPIURL)
            command = ("set_bell" if mode == "on" else "unset_bell")
            conn.request("POST", "/users_api/v1/systems/" + self.system.id + "/commands/" + command, json.dumps(body), { 'x-access-token': self.__token(), 'Content-Type': 'application/json' })
            response = json.loads(conn.getresponse().read().decode("utf-8"))
            conn.close()
        except Exception as err:
            _LOGGER.exception(err)
            raise InvokeGarnetAPIException(err)

        if("success" in response and response["success"]):
            self.__update_status(response["message"]["status"])
        else: 
            if("message" in response):
                if((response["message"] == "Failed to authenticate token.") or (response["message"] == "No token provided.")):
                    _LOGGER.warning(response["message"])
                    raise Exception(response["message"])        # Esto no deberia ocurrir porque se supone que el tiempo de vida del token esta controlado
                elif((response["message"] == "No se recibió respuesta del sistema en el tiempo máximo, json.dumps(body),  esperado") or (response["message"] == "Ya hay un comando en progreso")):
                    raise UnresponsiveGarnetAPI(response["message"])
                else:                
                    raise InvokeGarnetAPIException(response["message"])
            else:
                raise InvokeGarnetAPIException("Invalid JSON " + str(response))


    def report_emergency(self, type: str, partition_id: int, partition_name: str) -> None:
        """Genera una emergencia."""
        body = {}
        body["partition"] = {}
        body["partition"]["name"] = partition_name
        body["partition"]["number"] = partition_id
        body["partition"]["enabled"] = True
        body["partition"]["editedName"] = partition_name
        body["emergencyType"] = 1 if type == "Medico" else (3 if type == "Incendio" else (4 if type == "Panico" else 2))
        body["timeout"] = GARNETAPITIMEOUT

        response = {}
        try:
            conn = http.client.HTTPSConnection(GARNETAPIURL)
            conn.request("POST", f"/users_api/v1/systems/{self.system.id}/commands/emergency", json.dumps(body), { 'x-access-token': self.__token(), 'Content-Type': 'application/json' })
            response = json.loads(conn.getresponse().read().decode("utf-8"))
            conn.close()
        except Exception as err:
            _LOGGER.exception(err)
            raise InvokeGarnetAPIException(err)
        if("success" in response and response["success"]):
            _LOGGER.info(response["message"]["response"])
        else: 
            if("message" in response):
                if((response["message"] == "Failed to authenticate token.") or (response["message"] == "No token provided.")):
                    _LOGGER.warning(response["message"])
                    raise Exception(response["message"])        # Esto no deberia ocurrir porque se supone que el tiempo de vida del token esta controlado
                elif((response["message"] == "No se recibió respuesta del sistema en el tiempo máximo esperado") or (response["message"] == "Ya hay un comando en progreso")):
                    raise UnresponsiveGarnetAPI(response["message"])
                else:                
                    raise InvokeGarnetAPIException(response["message"])
            else:
                raise InvokeGarnetAPIException("Invalid JSON " + str(response))


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


class UnresponsiveGarnetAPI(Exception):
    """Excepcion para API Garnet sin respuesta."""

class InvokeGarnetAPIException(Exception):
    """Excepcion ante error en API Garnet."""

class SystemDoesNotExistException(Exception):
    """ID de panel no existe en Garnet Control."""

    