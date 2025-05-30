"""Funciones de manejo de panel a traves de la api http de Garnet
   Crea un modelo de datos de la informacion en la WEB que usa al 
   inicio para crear el modelo en HA. 
   
   Importante: NO ACTUALIZA EL MODELO DURANTE LA OPERACION. 
   
   Cualquier cambio en la web requiere reiniciar la integracion"""

import logging
import http.client
import json
import time

from .const import GARNETAPIURL, TOKEN_TIME_SPAN
from .httpdata import GarnetHTTPUser, GarnetPanelInfo, Zone,Partition

_LOGGER = logging.getLogger(__name__)


class SessionData:
    """Datos de la session"""
    token: str = None
    creation: time = None

    def __init__(self, token: str = None, creation: time = 0) -> None:
        self.token = token
        self.creation = creation


class HTTP_API:

    user : GarnetHTTPUser               # Datos de la cuenta
    system: GarnetPanelInfo = None      # Datos del panel
    zones: Zone = []                    # Datos de las zonas. Los datos dinamicos se obtienen inicialmente aca y luego se actualizan x SIA 
                                        # salvo el estado abierto y cerrado. Es importante resolver esto porque si se arma la alarma con 
                                        # una zona abierta se dispara. EL workaround seria periodicamente llamar a self.update_status() 
                                        # pero pareceria que Garnet no esta preparado para estar constantemente llamarndo
    partitions: Partition = []          # Datos de la particion
    howler: str = None                  # Datos de la sirena. No se actualiza x SIA por lo tanto si se dispara a traves de la app mobile 
                                        # mo hay forma de saberlo . EL workaround seria periodicamente llamar a self.update_status() 
                                        # pero pareceria que Garnet no esta preparado para estar constantemente llamarndo
    partition_state: str = None


    def __init__(self, email: str, pwd: str, panelid: str) -> None:        
        """Initialise."""
        self.user = GarnetHTTPUser(email=email, password=pwd)
        self.panelid = panelid
        self.session_token = SessionData()             # Token de session
        self.zones = [Zone(id = x + 1) for x in range(32)]
        self.partitions = [Partition(id = x + 1) for x in range(4)]
        self.seq = 1


    def connect(self):
        """Se conecta a la api y obtiene la informacion de la cuenta y panel
            actualizando el modelo de datos """
        try:
            self.api = http.client.HTTPSConnection(GARNETAPIURL)

            self.__collect_system_info()    # Necesario para levantar la configuracion restante

            retries = 5
            while(retries > 0):             # En el proceso de obtener estado es importante varios retries porque la WEB de Garnet es lenta
                try:
                    self.update_status() 
                    retries = 0
                except UnresponsiveGarnetAPI as err:
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
            self.api.request("POST", "/users_api/v1/auth/login", json.dumps(body), { 'Content-Type': 'application/json' })
            response = json.loads(self.api.getresponse().read().decode("utf-8"))
        except Exception as err:
            _LOGGER.exception(err)
            raise ExceptionCallingGarnetAPI(err)
        if("success" in response and response["success"]):
            _LOGGER.info("Successful login to GARTNET http")            
            self.session_token.token = response["accessToken"]
            self.session_token.creation = time.time()
        else:
            if("message" in response):
                if((response["message"] == "No se recibió respuesta del sistema en el tiempo máximo esperado") or (response["message"] == "Ya hay un comando en progreso")):
                    raise UnresponsiveGarnetAPI(response["message"])
                else:                
                    raise ExceptionCallingGarnetAPI(response["message"])
            else:
                raise ExceptionCallingGarnetAPI(f"Invalid JSON {str(response)}")


    def __collect_system_info(self) -> None:
        """Obtiene informacion de zonas y sistema GARTNET."""

        response = {}
        try:
            self.api.request("GET", "/users_api/v1/systems/" + self.panelid , '', { 'x-access-token': self.__token() })
            response = json.loads(self.api.getresponse().read().decode("utf-8"))
        except Exception as err:
            _LOGGER.exception(err)
            raise ExceptionCallingGarnetAPI(err)

        if("success" in response and response["success"]):
            if self.user.name is None:
                for user in response["message"]["sistema"]["users"]:
                    if user["email"].lower() == self.user.email.lower():
                        self.user.name = f"{user["nombre"]} {user["apellido"]}"             # Obtiene el nombre real del usuario registrado en la Web
                        self.user.arm_permision = user["atributos"]["puedeArmar"]
                        self.user.disarm_permision = user["atributos"]["puedeDesarmar"]
                        self.user.disable_zone_permision = user["atributos"]["puedeInhibirZonas"]
                        self.user.horn_permision = user["atributos"]["puedeInteractuarConSirena"]
                        break
            if(self.system is None):
                if response["message"]["sistema"]["id"] == self.panelid:
                    self.system = GarnetPanelInfo( id = response["message"]["sistema"]["id"], guid = response["message"]["sistema"]["id"], name = response["message"]["sistema"]["nombre"])
                    self.system.model = response["message"]["sistema"]["programation"]["data"]["alarmPanel"]["model"]                                                                                 
                    self.system.version = response["message"]["sistema"]["programation"]["data"]["alarmPanel"]["version"]                                                                                 
                    self.system.modelName = response["message"]["sistema"]["programation"]["data"]["alarmPanel"]["modelName"]                                                                                 
                    self.system.versionName = response["message"]["sistema"]["programation"]["data"]["alarmPanel"]["versionName"]
                else:
                    raise SystemDoesNotExistException(f"El sistema con id {self.panelid} no se encuentra registrado en Garnet Control")

            for zone in response["message"]["sistema"]["programation"]["data"]["zones"]:
                self.zones[zone["number"] - 1].name = zone["name"] if ("name" in zone) else ""
                self.zones[zone["number"] - 1].enabled = zone["enabled"]
                self.zones[zone["number"] - 1].interior = zone["isPresentZone"]
                self.zones[zone["number"] - 1].icon = zone["icon"] if ("icon" in zone) else "0"

            for partition in response["message"]["sistema"]["programation"]["data"]["partitions"]:
                self.partitions[partition["number"] - 1].name = partition["name"]
                self.partitions[partition["number"] - 1].enabled = partition["enabled"]

        else:
            if("message" in response):
                if((response["message"] == "No se recibió respuesta del sistema en el tiempo máximo esperado") or (response["message"] == "Ya hay un comando en progreso")):
                    raise UnresponsiveGarnetAPI(response["message"])
                else:
                    raise ExceptionCallingGarnetAPI(response["message"])
            else:
                raise ExceptionCallingGarnetAPI(f"Invalid JSON {str(response)}")


    def update_status(self) -> None:
        """Chequeo de estado."""
        body = {}
        body["seq"] = self.__sequence()
        body["timeout"] = 4500

        response = {}
        try:
            self.api.request("POST", "/users_api/v1/systems/" + self.panelid + "/commands/state", json.dumps(body), { 'x-access-token': self.__token(), 'Content-Type': 'application/json' })
            response = json.loads(self.api.getresponse().read().decode("utf-8"))
        except Exception as err:
            _LOGGER.exception(err)
            raise ExceptionCallingGarnetAPI(err)

        if("success" in response and response["success"]):
            status = response["message"]["status"]
            _LOGGER.debug("Se recibe trama " + status)
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
                if self.zones[z - 1].enabled:
                    _LOGGER.debug("Zona: %d se encuentra %s, %s y %s", z , "abierta" if v_open else "cerrada", "alarmada" if v_alm else "sin alarma", "inhibida" if v_inh else "habilitada")
                    self.zones[z - 1].alarmed = v_alm != 0
                    self.zones[z - 1].bypassed = v_inh != 0
                    self.zones[z - 1].open = v_open != 0
                m_open = m_open >> 1
                m_alm = m_alm >> 1
                m_inh = m_inh >> 1
                s = s - 1                    

            m = int(status[8:9], 16) & 1
            _LOGGER.debug("Mascara de sirena: 0x%s / %s", status[8:9], "Sirena apagada" if(m == 0) else "Sirena activada")
            self.howler = "on" if m > 0 else "off"

            m = int(status[5:9], 16)
            for p in self.partitions:
                #TODO: Esto esta maaaaaaaaal hay que sacar la informacion de forma correcta de la trama para todas las particiones
                p.alarmed = (int(status[11:19], 16) & 255) != 0 
                p.armed = "disarmed" if((m & 0xF000) == 0xF000) else ("away" if(((m & 0x7800) == 0x7800) and ((int(status[19:27], 16) & 255) > 0)) else ("home" if((m & 0x7800) == 0x7800) else ("block" if((m & 0x4000) == 0x4000) else "unknown")))
                _LOGGER.debug("Mascara de inhibicion: 0x%s / alarmed: %s / armed: %s", status[5:9], str(p.alarmed), p.armed)

        else: 
            if("message" in response):
                if((response["message"] == "Failed to authenticate token.") or (response["message"] == "No token provided.")):
                    _LOGGER.warning(response["message"] + " //  Se intenta nuevamente el login")
                    self.__login()
                    return self.update_status()
                elif((response["message"] == "No se recibió respuesta del sistema en el tiempo máximo esperado") or (response["message"] == "Ya hay un comando en progreso")):
                    raise UnresponsiveGarnetAPI(response["message"])
                elif((response["message"] == "Failed to authenticate token.") or (response["message"] == "No token provided.")):
                    _LOGGER.warning(response["message"] + " //  Se intenta nuevamente el login")
                    self.__login()
                    return self.update_status()
                else:                
                    raise ExceptionCallingGarnetAPI(response["message"])
            else:
                raise ExceptionCallingGarnetAPI("Invalid JSON " + str(response))


    def arm_system(self, partition: int, mode: str) -> None:
        """Armado de particion."""

        if(not self.user.arm_permision):
            raise PermissionError("User " + self.user.name + " has no permision for arming the partition")

        #TODO: Si hay zonas abiertas no armar

        body = {}
        body["seq"] = self.__sequence()
        body["partNumber"] = str(partition)
        body["timeout"] = 4500

        response = {}
        try:
            command = ("delayed" if mode == "home" else "away")
            self.api.request("POST", "/users_api/v1/systems/" + self.system.id + "/commands/arm/" + command, json.dumps(body), { 'x-access-token': self.session_token, 'Content-Type': 'application/json' })
            response = json.loads(self.api.getresponse().read().decode("utf-8"))
        except Exception as err:
            _LOGGER.exception(err)
            raise ExceptionCallingGarnetAPI(err)

        if("success" in response and not response["success"]):
            if("message" in response):
                if((response["message"] == "Failed to authenticate token.") or (response["message"] == "No token provided.")):
                    _LOGGER.warning(response["message"] + " //  Se intenta nuevamente el login")
                    self.login()
                    return self.arm_system(partition,mode)
                elif((response["message"] == "No se recibió respuesta del sistema en el tiempo máximo esperado") or (response["message"] == "Ya hay un comando en progreso")):
                    raise UnresponsiveGarnetAPI(response["message"])
                elif((response["message"] == "Failed to authenticate token.") or (response["message"] == "No token provided.")):
                    _LOGGER.warning(response["message"] + " //  Se intenta nuevamente el login")
                    self.__login()
                    return self.arm_system(partition,mode)
                else:                
                    raise Exception(response["message"])
            else:
                raise Exception("Invalid JSON " + str(response))


    def disarm_system(self, partition: int) -> None:
        """Desarmado de particion."""

        if(not self.user.disarm_permision):
            raise PermissionError("User " + self.user.name + " has no permision for disarming the partition")

        body = {}
        body["seq"] = self.__sequence()
        body["partNumber"] = str(partition)
        body["timeout"] = 4500

        response = {}
        try:
            self.api.request("POST", "/users_api/v1/systems/" + self.system.id + "/commands/disarm", json.dumps(body), { 'x-access-token': self.session_token, 'Content-Type': 'application/json' })
            response = json.loads(self.api.getresponse().read().decode("utf-8"))
        except Exception as err:
            _LOGGER.exception(err)
            raise ExceptionCallingGarnetAPI(err)

        if("success" in response and not response["success"]):
            if("message" in response):
                if((response["message"] == "Failed to authenticate token.") or (response["message"] == "No token provided.")):
                    _LOGGER.warning(response["message"] + " //  Se intenta nuevamente el login")
                    self.login()
                    return self.disarm_system(partition)
                elif((response["message"] == "No se recibió respuesta del sistema en el tiempo máximo esperado") or (response["message"] == "Ya hay un comando en progreso")):
                    raise UnresponsiveGarnetAPI(response["message"])
                elif((response["message"] == "Failed to authenticate token.") or (response["message"] == "No token provided.")):
                    _LOGGER.warning(response["message"] + " //  Se intenta nuevamente el login")
                    self.__login()
                    return self.disarm_system(partition)
                else:                
                    raise Exception(response["message"])
            else:
                raise Exception("Invalid JSON " + str(response))


    def horn_control(self, mode: int) -> None:
        """Control de sirena."""

        if(not self.user.horn_permision):
            raise PermissionError("User " + self.user.name + " has no permision control the horn")

        body = {}
        body["seq"] = self.__sequence()
        body["timeout"] = 4500

        response = {}
        try:
            command = ("set_bell" if mode == 1 else "unset_bell")
            self.api.request("POST", "/users_api/v1/systems/" + self.system.id + "/commands/" + command, json.dumps(body), { 'x-access-token': self.session_token, 'Content-Type': 'application/json' })
            response = json.loads(self.api.getresponse().read().decode("utf-8"))
        except Exception as err:
            _LOGGER.exception(err)
            raise ExceptionCallingGarnetAPI(err)

        if("success" in response and not response["success"]):
            if("message" in response):
                if((response["message"] == "Failed to authenticate token.") or (response["message"] == "No token provided.")):
                    _LOGGER.warning(response["message"] + " //  Se intenta nuevamente el login")
                    self.login()
                    return self.horn_control(mode)
                elif((response["message"] == "No se recibió respuesta del sistema en el tiempo máximo esperado") or (response["message"] == "Ya hay un comando en progreso")):
                    raise UnresponsiveGarnetAPI(response["message"])
                elif((response["message"] == "Failed to authenticate token.") or (response["message"] == "No token provided.")):
                    _LOGGER.warning(response["message"] + " //  Se intenta nuevamente el login")
                    self.__login()
                    return self.horn_control(mode)
                else:                
                    raise Exception(response["message"])
            else:
                raise Exception("Invalid JSON " + str(response))


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


    def report_emergency(self, type: str) -> None:
        """Genera una alarma."""
        #TODO: Implementar
        # medico ----> {"partition":{"name":"Partición principal","number":1,"enabled":true,"editedName":"Partición principal"},"emergencyType":1,"timeout":4500}
        # ?????? ----> {"partition":{"name":"Partición principal","number":1,"enabled":true,"editedName":"Partición principal"},"emergencyType":2,"timeout":4500}
        # incendio --> {"partition":{"name":"Partición principal","number":1,"enabled":true,"editedName":"Partición principal"},"emergencyType":3,"timeout":4500} 
        # panico ----> {"partition":{"name":"Partición principal","number":1,"enabled":true,"editedName":"Partición principal"},"emergencyType":4,"timeout":4500}
        # POST https://web.garnetcontrol.app/users_api/v1/systems/a10050008d96/commands/emergency


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


    def __sequence(self) -> str:
        """Devuelve numero de sequencia consecutivo y limitado en 255."""
        self.seq += 1
        if(self.seq == 256): self.seq = 0
        return str(self.seq).zfill(3)





class UnresponsiveGarnetAPI(Exception):
    """Excepcion para API Garnet sin respuesta."""

class ExceptionCallingGarnetAPI(Exception):
    """Excepcion ante error en API Garnet."""

class SystemDoesNotExistException(Exception):
    """ID de panel no existe en Garnet Control."""

    