import http.client
import json
import time
import logging


from .data import Zone, Partition, GarnetPanelInfo, User
from .siaserver import MessageServer, siacode
from .const import *
from collections.abc import Callable


_LOGGER = logging.getLogger(__name__)


class GarnetAPI:
    """Implementacion de API WEB Garnet."""
    #TODO: cada comando devuelve el estado???? parsearlo

    messageserver: MessageServer = None

    def __init__(self, email: str, password: str, client: str) -> None:
        """Inicializacion de la API."""

        _LOGGER.debug("Inicializando API")
        self.email = email
        self.password = password
        self.client = client
        self.session_token = ""
        self.seq = 0
        self.zones = [Zone(id = x + 1) for x in range(32)]
        self.partitions = [Partition(id = x + 1) for x in range(4)]
        self.api = http.client.HTTPSConnection(GARNETAPIURL)
        self.user = None
        self.system = None
        self.__login()	       # Necesario para levantar la configuracion inicial
        self.__system_info()   # Necesario para levantar la configuracion restante
        self.keep_alive_handler = None
        if(GarnetAPI.messageserver == None):
            GarnetAPI.messageserver = MessageServer()
        GarnetAPI.messageserver.add(self.__sia_client, self.client)
        

    def finalize(self) -> None:
        _LOGGER.debug("Removiendo  API")
        GarnetAPI.messageserver.remove(self.client)
        self.keep_alive_handler = None


    def set_keep_alive_handler(self, message_callback: Callable | None = None ) -> bool:
        """Assignas keep alive callback."""
        _LOGGER.info("Setting set_keep_alive_handler " + str(message_callback))
        self.keep_alive_handler = message_callback



    def get_status(self) -> bool:
        """Devuelve estado del panel. True si todo esta bien. False si algo no esta bien."""
        #TODO: implementar
        return True

    def __sia_client(self, message: str = "", partition: int = 0, zone: int = 0, user: int = 0, action: siacode = siacode.none, keepalive: bool = False) -> None:
        """Funcion que recibe notificaciones del cliente. No debe ser bloqueante"""

        _LOGGER.debug("message:" + message +", partition:"+str(partition)+", zone:"+str(zone)+", user:"+str(user)+", action:"+str(action)+", keepalive:"+str(keepalive)+"")
        if(keepalive):
            if self.keep_alive_handler is not None:
                _LOGGER.info("Calling self.keep_alive_handler")
                self.keep_alive_handler()
        else:
            if(action == siacode.none):
                _LOGGER.warning(message) # Se trata de un codigo que no se procesa
            elif(action == siacode.bypass):
                self.zones[zone - 1].bypassed = True
            elif(action == siacode.unbypass):
                self.zones[zone - 1].bypassed = False
            elif(action == siacode.group_bypass):
                for z in self.zones:
                    if(z.enabled): z.bypassed = True
            elif(action == siacode.group_unbypass):
                for z in self.zones:
                    if(z.enabled): z.bypassed = False
            elif(action == siacode.present_arm or action == siacode.arm or action == siacode.keyboard_arm):
                self.partitions[partition - 1].armed = True
            elif(action == siacode.present_disarm or action == siacode.disarm or action == siacode.keyboard_disarm or action == siacode.alarm_disarm):
                self.partitions[partition - 1].armed = False
            elif(action == siacode.triggerzone):
                self.zones[zone - 1].alarmed = True
            elif(action == siacode.restorezone):
                 self.zones[zone - 1].alarmed = False
            elif(action == siacode.trigger):
                self.partitions[partition - 1].alarmed = True
            elif(action == siacode.restore):
                self.partitions[partition - 1].alarmed = False
            else:
                _LOGGER.warning("siacode " + str(action) + " no se esta procesando") # Se trata de un codigo que no se procesa
        

    def __sequence(self) -> str:
        """Devuelve numero de sequencia consecutivo y limitado en 255."""
        self.seq += 1
        if(self.seq == 256): self.seq = 0
        return str(self.seq).zfill(3)

    def get_enabled_zones(self):
        """Devuelve solo las zonas activas"""
        return [
                zone
                for zone in self.zones
                if zone.enabled
            ]

    def __login(self) -> None:
        """Obtiene token de sesion y configuraciones iniciales."""
        body = {}
        body["email"] = self.email
        body["password"] = self.password

        response = {}
        try:
            self.api.request("POST", "/users_api/v1/auth/login", json.dumps(body), { 'Content-Type': 'application/json' })
            response = json.loads(self.api.getresponse().read().decode("utf-8"))
        except Exception as err:
            raise ExceptionCallingGarnetAPI(err)
        if("success" in response and response["success"]):
            _LOGGER.info("Login a sistema GARTNET exitoso!")
            self.session_token = response["accessToken"]
            if(self.user == None):
                self.user = User( name = (response["userData"]["nombre"] + " " + response["userData"]["apellido"]), email = response["userData"]["email"])
            if(self.system == None):
                if len(response["userData"]["sistemas"]) == 0:
                    self.system = GarnetPanelInfo( id = "N/A", guid = "N/A", name = "N/A")
                else:
                    self.system = GarnetPanelInfo( id = response["userData"]["sistemas"][0]["id"], guid = response["userData"]["sistemas"][0]["_id"], name = response["userData"]["sistemas"][0]["nombre"])
        else:
            if("message" in response):
                if((response["message"] == "No se recibió respuesta del sistema en el tiempo máximo esperado") or (response["message"] == "Ya hay un comando en progreso")):
                    raise UnresponsiveGarnetAPI(response["message"])
                else:                
                    raise Exception(response["message"])
            else:
                raise Exception("Invalid JSON " + str(response))


    def __system_info(self) -> None:
        """Obtiene informacion de zonas y sistema GARTNET."""

        response = {}
        try:
            self.api.request("GET", "/users_api/v1/systems/" + self.system.id , '', { 'x-access-token': self.session_token })
            response = json.loads(self.api.getresponse().read().decode("utf-8"))
        except Exception as err:
            raise ExceptionCallingGarnetAPI(err)

        if("success" in response and response["success"]):
            # Update user data
            self.user.arm_permision = response["message"]["sistema"]["userPermissions"]["atributos"]["puedeArmar"]
            self.user.disarm_permision = response["message"]["sistema"]["userPermissions"]["atributos"]["puedeDesarmar"]
            self.user.disable_zone_permision = response["message"]["sistema"]["userPermissions"]["atributos"]["puedeInhibirZonas"]
            self.user.horn_permision = response["message"]["sistema"]["userPermissions"]["atributos"]["puedeInteractuarConSirena"]
            # Update system data
            self.system.model = response["message"]["sistema"]["programation"]["data"]["alarmPanel"]["model"]                                                                                 
            self.system.version = response["message"]["sistema"]["programation"]["data"]["alarmPanel"]["version"]                                                                                 
            self.system.modelName = response["message"]["sistema"]["programation"]["data"]["alarmPanel"]["modelName"]                                                                                 
            self.system.versionName = response["message"]["sistema"]["programation"]["data"]["alarmPanel"]["versionName"]

            for zone in response["message"]["sistema"]["programation"]["data"]["zones"]:
                self.zones[zone["number"] - 1].name = zone["name"]
                self.zones[zone["number"] - 1].enabled = zone["enabled"]
                self.zones[zone["number"] - 1].interior = zone["isPresentZone"]
                self.zones[zone["number"] - 1].icon = zone["icon"]

            for partition in response["message"]["sistema"]["programation"]["data"]["partitions"]:
                self.partitions[partition["number"] - 1].name = partition["name"]
                self.partitions[partition["number"] - 1].enabled = partition["enabled"]

        else:
            if("message" in response):
                if((response["message"] == "No se recibió respuesta del sistema en el tiempo máximo esperado") or (response["message"] == "Ya hay un comando en progreso")):
                    raise UnresponsiveGarnetAPI(response["message"])
                elif((response["message"] == "Failed to authenticate token.") or (response["message"] == "No token provided.")):
                    _LOGGER.warning(response["message"] + " //  Se intenta nuevamente el login")
                    self.__login()
                    return self.system_info()
                else:                
                    raise Exception(response["message"])
            else:
                raise Exception("Invalid JSON " + str(response))


    def __parse_frame(self, frame: str) -> None:
        """Parseo de trama de sistema."""

        txt = "Mascara de estado: 0x" + frame[9:11] + " / "
        m = int(frame[9:11], 16) & 255
        if(m == 0):
            txt = txt + "Todas las zonas cerradas"
        else:
            s = 16
            while(s > 0):
                txt = (txt + "Zona " + str(17 - s) + " abierta, ") if(m & 1) else txt
                m = m >> 1
                s = s - 1                    
        _LOGGER.debug(txt)

        txt = "Mascara de alarma: 0x" + frame[11:19] + " / "
        m = int(frame[11:19], 16) & 255
        if(m == 0):
            txt = txt + "Sin alarmas"
        else:
            s = 16
            while(s > 0):
                txt = (txt + "Zona " + str(17 - s) + " alarmada, ") if(m & 1) else txt
                m = m >> 1
                s = s - 1                    
        _LOGGER.debug(txt)

        txt = "Mascara de inhibicion: 0x" + frame[19:27] + " / "
        m = int(frame[19:27], 16) & 255
        if(m == 0):
            txt = txt + "No hay zonas inhibidas"
        else:
            s = 16
            while(s > 0):
                txt = (txt + "Zona " + str(17 - s) + " inhibida, ") if(m & 1) else txt
                m = m >> 1
                s = s - 1                    
        _LOGGER.debug(txt)

        m = int(frame[8:9], 16) & 1
        _LOGGER.debug("Mascara de sirena: 0x" + frame[8:9] + " / " + ("Sirena apagada" if(m == 0) else "Sirena activada"))


        txt = "Mascara de inhibicion: 0x" + frame[5:9] + " / "
        m = int(frame[5:9], 16)
        if((m & 0xF000) == 0xF000):
            txt = txt + "Desarmada. Lista para armar"
        else:
            if((m & 0x7800) == 0x7800):
                txt = txt + "Armada"
            else:
                if((m & 0x4000) == 0x4000):
                    txt = txt + "Desarmada. No se puede armar hay zonas abiertas"
                else:
                    txt = txt + "????????????"
        _LOGGER.debug(txt)


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


    def state(self) -> None:
        """Chequeo de estado."""
        body = {}
        body["seq"] = self.__sequence()
        body["timeout"] = 4500

        response = {}
        try:
            self.api.request("POST", "/users_api/v1/systems/" + self.system.id + "/commands/state", json.dumps(body), { 'x-access-token': self.session_token, 'Content-Type': 'application/json' })
            response = json.loads(self.api.getresponse().read().decode("utf-8"))
        except Exception as err:
            raise ExceptionCallingGarnetAPI(err)

        if("success" in response and response["success"]):
            status = response["message"]["status"]
            _LOGGER.debug("Se recibe trama " + status)
            self.__parse_frame(status)
        else:
            if("message" in response):
                if((response["message"] == "Failed to authenticate token.") or (response["message"] == "No token provided.")):
                    _LOGGER.warning(response["message"] + " //  Se intenta nuevamente el login")
                    self.login()
                    return self.state()
                elif((response["message"] == "No se recibió respuesta del sistema en el tiempo máximo esperado") or (response["message"] == "Ya hay un comando en progreso")):
                    raise UnresponsiveGarnetAPI(response["message"])
                elif((response["message"] == "Failed to authenticate token.") or (response["message"] == "No token provided.")):
                    _LOGGER.warning(response["message"] + " //  Se intenta nuevamente el login")
                    self.__login()
                    return self.state()
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


    def report_emergency(self, type: emergencytype) -> None:
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


class UnresponsiveGarnetAPI(Exception):
    """Excepcion para API Garnet sin respuesta."""

class ExceptionCallingGarnetAPI(Exception):
    """Excepcion ante error en API Garnet."""
