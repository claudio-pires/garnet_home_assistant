"""Implementacion de servidor UDP que recibe los mensajes SIA"""

import logging
import threading
import socket
import time
import datetime

from enum import Enum

from .const import MESSAGESERVER_TIMEOUT, SIA_BUFFERSIZE, DEFAULT_UDP_PORT

_LOGGER = logging.getLogger(__name__)


class siacode(Enum):
    """Mapeo interno de codigos sia"""
    none =           -1
    bypass =          0
    unbypass =        1
    group_bypass =    2
    group_unbypass =  3
    present_arm =     4
    present_disarm =  5
    arm =             6
    disarm =          7
    alarm_disarm =    8
    keyboard_arm =    9
    keyboard_disarm = 10
    triggerzone =     11
    restorezone =     12
    trigger =         13
    restore =         14
    dontdoanything =  100
    keepalive      =  101


class SIAUDPServer():
    """Clase para manejar mensajeria SIA"""

    sia_thread = None
    errorcode = None
    active = False
    port = DEFAULT_UDP_PORT


    def __init__(self, port: int = DEFAULT_UDP_PORT):
        """Thread que recibe los mensajes SIA."""
        SIAUDPServer.subscribers = {}
        SIAUDPServer.active = True
        SIAUDPServer.port = port
        SIAUDPServer.sia_thread = threading.Thread(target=SIAUDPServer.__messageserver_thread, name="SIA-Thread")
        _LOGGER.info("Starting SIA UDP Server...")
        SIAUDPServer.sia_thread.start()
        timeout = 0
        while(timeout < MESSAGESERVER_TIMEOUT and SIAUDPServer.errorcode == None):
            _LOGGER.debug("Waiting for SIA Server socket to be ready...")
            time.sleep(1)
            timeout = timeout + 1
        if(SIAUDPServer.errorcode != "success"):
            SIAUDPServer.active = False
            if(SIAUDPServer.errorcode == None):
                raise Exception("timeout")
            else:
                raise Exception(SIAUDPServer.errorcode)
        _LOGGER.debug("SIA UDP Server socket ready...")


    def __messageserver_thread():
        """Thread que maneja el socket UDP. Recibe los mensajes, descarta los invalidos. los parsea y responde el ACK
           Luego envia al suscriptor que corresponda"""
        #TODO: Cuando inicia el socket deberia descartar los mensajes recibidos porque en general el panel escupe todo lo que no pudo enviar
        try:
            _LOGGER.info("[__messageserver_thread] Starting SIA parser @ UDP port #%s",str(SIAUDPServer.port))
            UDPServerSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)      # Create a datagram UDP socket
            UDPServerSocket.bind(('' , SIAUDPServer.port))                                               # Bind to address and ip
            SIAUDPServer.errorcode = "success"
            while(SIAUDPServer.active):
                (datagram,senderAddr) = UDPServerSocket.recvfrom(SIA_BUFFERSIZE)                # Listen for incoming datagrams
                data = SIAFrameProcessor(bytearray(datagram))
                _LOGGER.debug("[__messageserver_thread] Received %s", str(data))
                if(data.valid):                                                                 # Valid packet
                    UDPServerSocket.sendto(str.encode(data.replyMessage()), senderAddr)         # Responde ACK
                    if(data.account in SIAUDPServer.subscribers):
                        if(data.eventcode == 0 and data.token == "NULL"):        # No es CID es un keep alive
                            SIAUDPServer.subscribers[data.account](action=siacode.keepalive)
                        elif(data.eventcode == 627 or       # Ingresando al modo de programacion remota
                             data.eventcode == 628 or       # Saliendo del modo de programacion remota
                             data.eventcode == 602):        # Test Periodico no se hace nada. Solo se envia a modo de keep alive pero ni haria falta enviarlo 
                             SIAUDPServer.subscribers[data.account](action=siacode.dontdoanything)
                        elif(data.eventcode == 570 and data.qualifier == 1):
                            SIAUDPServer.subscribers[data.account](action = siacode.bypass, zone = data.zone, partition = data.partition)
                        elif(data.eventcode == 570 and data.qualifier == 3):
                            SIAUDPServer.subscribers[data.account](action = siacode.unbypass, zone = data.zone, partition = data.partition)
                        elif(data.eventcode == 574 and data.qualifier == 1):
                            SIAUDPServer.subscribers[data.account](action = siacode.group_bypass, partition = data.partition)
                        elif(data.eventcode == 574 and data.qualifier == 3):
                            SIAUDPServer.subscribers[data.account](action = siacode.group_unbypass, partition = data.partition)
                        elif(data.eventcode == 441 and data.qualifier == 1):
                            SIAUDPServer.subscribers[data.account](action = siacode.present_disarm, user = data.zone, partition = data.partition)
                        elif(data.eventcode == 441 and data.qualifier == 3):
                            SIAUDPServer.subscribers[data.account](action = siacode.present_arm, user = data.zone, partition = data.partition)
                        elif(data.eventcode == 407 and data.qualifier == 1):
                            SIAUDPServer.subscribers[data.account](action = siacode.disarm, user = data.zone, partition = data.partition)
                        elif(data.eventcode == 407 and data.qualifier == 3):
                            SIAUDPServer.subscribers[data.account](action = siacode.arm, user = data.zone, partition = data.partition)
                        elif(data.eventcode == 406 and data.qualifier == 1):
                            SIAUDPServer.subscribers[data.account](action = siacode.alarm_disarm, user = data.zone, partition = data.partition)
                        elif(data.eventcode == 401 and data.qualifier == 1):
                            SIAUDPServer.subscribers[data.account](action = siacode.keyboard_disarm, user = data.zone, partition = data.partition)
                        elif(data.eventcode == 401 and data.qualifier == 3):
                            SIAUDPServer.subscribers[data.account](action = siacode.keyboard_arm, user = data.zone, partition = data.partition)
                        elif(data.eventcode == 130 and data.qualifier == 1):
                            SIAUDPServer.subscribers[data.account](action = siacode.triggerzone, zone = data.zone, partition = data.partition)
                        elif(data.eventcode == 130 and data.qualifier == 3):
                            SIAUDPServer.subscribers[data.account](action = siacode.restorezone, zone = data.zone, partition = data.partition)
                        elif(data.eventcode == 459 and data.qualifier == 1):
                            SIAUDPServer.subscribers[data.account](action = siacode.trigger, zone = data.zone, partition = data.partition)
                        elif(data.eventcode == 459 and data.qualifier == 3):
                            SIAUDPServer.subscribers[data.account](action = siacode.restore, zone = data.zone, partition = data.partition)
                        else:
                            # Se trata de un codigo que no se interpreta aun. Analizar si se debe interpretar o descartar
                            _LOGGER.warning("[__messageserver_thread] Panel has sent a message with eventcode: %d, qualifier: %d, partition: %d, zone: %d with  optionalExtendedData: %s and timestamp %s", data.eventcode, data.qualifier, data.partition, data.zone, data.mdata, data.timestamp)
                            _LOGGER.warning("[__messageserver_thread] Please submit an issue on https://github.com/claudio-pires/garnet-home-assistant/issues/new/choose indicating this code ") # Se trata de un codigo que no se procesa
                    else:
                        _LOGGER.warning("[__messageserver_thread] Account %s is not a valid suscriber. This message comes from %s", data.account, str(senderAddr))   
                else:
                    _LOGGER.error("[__messageserver_thread] Invalid packet")
            SIAUDPServer.sia_thread = None
            SIAUDPServer.active = False
            _LOGGER.info("[__messageserver_thread] Finalizing thread")
        except Exception as err:
            _LOGGER.exception(err)
            SIAUDPServer.errorcode = str(err)


    def add(self, callback, client: str):
        """Agrega un callback al message server"""
        if(client not in SIAUDPServer.subscribers):
            _LOGGER.info("[add] New suscriber account %s", str(client))
        else:
            _LOGGER.warning("[add] Suscriber %s already registered", str(client))
            SIAUDPServer.subscribers.pop(client)
        SIAUDPServer.subscribers[client] = callback     # Siempre se registra el ultimo


    def remove(self, client: str):
        """Quita un callback del message server"""
        if(client in SIAUDPServer.subscribers):
            _LOGGER.info("[remove] Suscriber account %s removed", str(client))
            SIAUDPServer.subscribers.pop(client)
        else:
            _LOGGER.warning("[remove] Suscriber %s is not registered", str(client))
        if(len(SIAUDPServer.subscribers) == 0):
            _LOGGER.info("[remove] UDP socket killed because there are no more suscribers")
            SIAUDPServer.active = False


class SIAFrameProcessor:
    """Procesador de trama SIA."""

    def __init__(self, data: bytearray) -> None:
        """Initialise."""
        self.valid: bool = False
        self.token: str = ""
        self.sequence: str = ""
        self.receiver: str = ""
        self.prefix: str = ""
        self.account: str = ""
        self.mdata: str = ""
        self.timestamp: datetime = None
        self.qualifier: int = 0
        self.eventcode: int = 0
        self.partition: int = 0
        self.zone: int = 0

        
        if(data[:1].decode("utf-8") == "\n"):   # Si el paquete no comienza con /n se descarta    

            
            self.ExpectedCRC = int.from_bytes(data[1:3], byteorder='big', signed=False)     # Se separa el CRC del paquete

            self.l = int(data[4:7].decode("utf-8"),16)      # Se obtiene el largo del bloque de datos
            self.DataBlock = data[7:self.l + 7]             # Se obtiene el bloque de datos


            if(self.crc16(self.DataBlock) == self.ExpectedCRC):     # Calcula CRC del bloque de datos y lo compara con el recibido  

                self.valid = True                                   # Si llega aca el paquete ya es valido

                self.message_str = self.DataBlock.decode()
                
#                _LOGGER.debug("Message is " + self.message_str)
                
                self.n = self.message_str.find('"',1) + 1
                self.token = self.message_str[:self.n].replace('"','')

                self.message_str = self.message_str[self.n:]
                self.n = self.message_str.find('R')
                self.sequence = self.message_str[:self.n]

                self.message_str = self.message_str[self.n:]
               
                self.n = self.message_str.find('L')
                self.receiver = self.message_str[:self.n]

                self.message_str = self.message_str[self.n:]
               
                self.n = self.message_str.find('#')
                self.prefix = self.message_str[:self.n]

                self.message_str = self.message_str[self.n:]
               
                self.n = self.message_str.find('[')
                self.account = self.message_str[1:self.n] # Se agrega 1 para quitar el numeral al comienzo

                self.message_str = self.message_str[self.n:]
               
                self.n = self.message_str.find('_') 
                self.mdata = self.message_str[:self.n]

                self.timestamp = datetime.datetime.strptime(self.message_str[self.n + 1:], "%H:%M:%S,%m-%d-%Y")

                if(self.token == "ADM-CID"):
                    if(self.mdata.find('][') > 1):        
                        (_messagedata,self.optionalExtendedData) = self.mdata.split('][')
                    else:
                        _messagedata = self.mdata
                        self.optionalExtendedData = None
                    if(not(self.optionalExtendedData is None)):
                        self.optionalExtendedData = self.optionalExtendedData.replace(']','').replace('[','')
                    _messagedata = _messagedata.replace(']','').replace('[','')
                    if(_messagedata.find('|') > 1): 
                        (_acc, _d) = _messagedata.split('|')
                    else:
                        _acc = None
                        _d = _messagedata
                    (_a,_b,_c) = _d.split(' ')

                    self.qualifier = int(_a[0], 10)
                    self.eventcode = int(_a[1:], 10)
                    self.partition = int(_b,10)
                    self.zone = int(_c,10)


    def crc16(self, data: bytearray):
        """Calcula CRC de un bytearray"""
        if data is None: return 0
        crcx = 0x0000
        for i in (range(0, len(data))):
            crcx ^= data[i]
            for j in range(0, 8):
                crcx = ((crcx >> 1) ^ 0xA001) if ((crcx & 0x0001) > 0) else (crcx >> 1)
        return crcx


    def replyMessage(self):
        """Genera mensaje de respuesta"""
        replymessage = f"\"ACK\"{self.sequence}{self.receiver}{self.prefix}{self.account}[]"
        replyCRC = self.crc16(bytearray(replymessage.encode()))
        return f"\n{format(replyCRC, '#04x')}0{str(len(replymessage))}{replymessage}\r"
    

    def __str__(self):
        return f"<SIAFrameProcessor: Token: {self.token}, Sequence: {self.sequence}, Receiver: {self.receiver}, Prefix: {self.prefix}, Account: {self.account}, info: {self.mdata}, qualifier: {self.qualifier}, eventcode: {self.eventcode}, partition: {self.partition}, zone: {self.zone }, Timestamp: {self.timestamp}>"


