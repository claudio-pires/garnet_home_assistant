
import threading
import socket
import time
from .siadata import SIAData
from .const import *
from .enums import siacode
import logging


_LOGGER = logging.getLogger(__name__)


class MessageServer():
    """Clase para manejar mensajeria SIA"""

    t = None
    errorcode = None
    active = False

    def __init__(self):
        """Thread que recibe los mensajes SIA."""
        MessageServer.subscribers = {}
        MessageServer.active = True
        MessageServer.t = threading.Thread(target=MessageServer.__messageserver_thread)
        MessageServer.t.start()
        timeout = 0
        while(timeout < MESSAGESERVER_TIMEOUT and MessageServer.errorcode == None):
            time.sleep(1)
            timeout = timeout + 1
        if(MessageServer.errorcode != "success"):
            MessageServer.active = False
            if(MessageServer.errorcode == None):
                raise Exception("timeout")
            else:
                raise Exception(MessageServer.errorcode)


    def __messageserver_thread():
        try:
            _LOGGER.info("Starting SIA parser on UDP port #" + str(UDP_PORT))
            UDPServerSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)  # Create a datagram UDP socket
            UDPServerSocket.bind(('' , UDP_PORT))                                               # Bind to address and ip
            MessageServer.errorcode = "success"
            #TODO: descartar los eventos de 2 minutos porque el panel suele escupir todo lo que no envio. 
            while(MessageServer.active):
                (datagram,senderAddr) = UDPServerSocket.recvfrom(SIA_BUFFERSIZE)                # Listen for incoming datagrams
                data = SIAData(bytearray(datagram))
                _LOGGER.debug("Data " + str(data))
                if(data.valid):                                                             # Valid packet
                    UDPServerSocket.sendto(str.encode(data.replyMessage()), senderAddr)

                    if(data.account in MessageServer.subscribers):
                        if(data.token != "ADM-CID"):
                            MessageServer.subscribers[data.account](keepalive = True)
                        else:
                            data.parseADMCID()
                            _LOGGER.debug("eventcode = " + str(data.eventcode) + ", qualifier = " + str(data.qualifier) + ", zona = " + str(data.zone) + ", partition = " + str(data.partition) )
                            if(data.eventcode == 602):
                                MessageServer.subscribers[data.account](message = "El panel esta notificando eventcode: " + str(data.eventcode) + " (TEST PERIODICO), qualifier: " + str(data.qualifier) + ", particion: " + str(data.partition) + ", zona: " + str(data.zone) + " con optionalExtendedData: " + data.optionalExtendedData + " - " + data.timestamp)
                            elif(data.eventcode == 570):
                                if(data.qualifier == 1):
                                    MessageServer.subscribers[data.account](action = siacode.bypass, zone = data.zone, partition = data.partition)
                                elif(data.qualifier == 3):
                                    MessageServer.subscribers[data.account](action = siacode.unbypass, zone = data.zone, partition = data.partition)
                                else:
                                    MessageServer.subscribers[data.account](message = "El panel esta notificando eventcode: " + str(data.eventcode) + " (BYPASS), qualifier: " + str(data.qualifier) + ", particion: " + str(data.partition) + ", zona: " + str(data.zone) + " con optionalExtendedData: " + data.optionalExtendedData + " - " + data.timestamp)
                            elif(data.eventcode == 574):
                                if(data.qualifier == 1):
                                    MessageServer.subscribers[data.account](action = siacode.group_bypass, partition = data.partition)
                                elif(data.qualifier == 3):
                                    MessageServer.subscribers[data.account](action = siacode.group_unbypass, partition = data.partition)
                                else:
                                    MessageServer.subscribers[data.account](message = "El panel esta notificando eventcode: " + str(data.eventcode) + " (GROUP BYPASS), qualifier: " + str(data.qualifier) + ", particion: " + str(data.partition) + ", zona: " + str(data.zone) + " con optionalExtendedData: " + data.optionalExtendedData + " - " + data.timestamp)
                            elif(data.eventcode == 441):
                                if(data.qualifier == 1):
                                    MessageServer.subscribers[data.account](action = siacode.present_disarm, user = data.zone, partition = data.partition)
                                elif(data.qualifier == 3):
                                    MessageServer.subscribers[data.account](action = siacode.present_arm, user = data.zone, partition = data.partition)
                                else:
                                    MessageServer.subscribers[data.account](message = "El panel esta notificando eventcode: " + str(data.eventcode) + " (ARMADO PRESENTE), qualifier: " + str(data.qualifier) + ", particion: " + str(data.partition) + ", zona: " + str(data.zone) + " con optionalExtendedData: " + data.optionalExtendedData + " - " + data.timestamp)
                            elif(data.eventcode == 407):
                                if(data.qualifier == 1):
                                    MessageServer.subscribers[data.account](action = siacode.disarm, user = data.zone, partition = data.partition)
                                elif(data.qualifier == 3):
                                    MessageServer.subscribers[data.account](action = siacode.arm, user = data.zone, partition = data.partition)
                                else:
                                    MessageServer.subscribers[data.account](message = "El panel esta notificando eventcode: " + str(data.eventcode) + " (ARMADO AUSENTE), qualifier: " + str(data.qualifier) + ", particion: " + str(data.partition) + ", zona: " + str(data.zone) + " con optionalExtendedData: " + data.optionalExtendedData + " - " + data.timestamp)
                            elif(data.eventcode == 406):
                                if(data.qualifier == 1):
                                    MessageServer.subscribers[data.account](action = siacode.alarm_disarm, user = data.zone, partition = data.partition)
                                else:
                                    MessageServer.subscribers[data.account](message = "El panel esta notificando eventcode: " + str(data.eventcode) + " (ARMADO ALARMADO), qualifier: " + str(data.qualifier) + ", particion: " + str(data.partition) + ", zona: " + str(data.zone) + " con optionalExtendedData: " + data.optionalExtendedData + " - " + data.timestamp)
                            elif(data.eventcode == 401):
                                if(data.qualifier == 1):
                                    MessageServer.subscribers[data.account](action = siacode.keyboard_disarm, user = data.zone, partition = data.partition)
                                elif(data.qualifier == 3):
                                    MessageServer.subscribers[data.account](action = siacode.keyboard_arm, user = data.zone, partition = data.partition)
                                else:
                                    MessageServer.subscribers[data.account](message = "El panel esta notificando eventcode: " + str(data.eventcode) + " (ARMADO x TECLADO), qualifier: " + str(data.qualifier) + ", particion: " + str(data.partition) + ", zona: " + str(data.zone) + " con optionalExtendedData: " + data.optionalExtendedData + " - " + data.timestamp)
                            elif(data.eventcode == 130):
                                if(data.qualifier == 1):
                                    MessageServer.subscribers[data.account](action = siacode.triggerzone, zona = data.zone, partition = data.partition)
                                elif(data.qualifier == 3):
                                    MessageServer.subscribers[data.account](action = siacode.restorezone, zona = data.zone, partition = data.partition)
                                else:
                                    MessageServer.subscribers[data.account](message = "El panel esta notificando eventcode: " + str(data.eventcode) + " (ALARMA ZONA), qualifier: " + str(data.qualifier) + ", particion: " + str(data.partition) + ", zona: " + str(data.zone) + " con optionalExtendedData: " + data.optionalExtendedData + " - " + data.timestamp)
                            elif(data.eventcode == 459):
                                if(data.qualifier == 1):
                                    MessageServer.subscribers[data.account](action = siacode.trigger, zona = data.zone, partition = data.partition)
                                elif(data.qualifier == 3):
                                    MessageServer.subscribers[data.account](action = siacode.restore, zona = data.zone, partition = data.partition)
                                else:
                                    MessageServer.subscribers[data.account](message = "El panel esta notificando eventcode: " + str(data.eventcode) + " (ALARMA), qualifier: " + str(data.qualifier) + ", particion: " + str(data.partition) + ", zona: " + str(data.zone) + " con optionalExtendedData: " + data.optionalExtendedData + " - " + data.timestamp)
                            else:
                                MessageServer.subscribers[data.account](message = "El panel esta notificando eventcode: " + str(data.eventcode) + ", qualifier: " + str(data.qualifier) + ", particion: " + str(data.partition) + ", zona: " + str(data.zone) + " con optionalExtendedData: " + data.optionalExtendedData + " - " + data.timestamp)
                    else:
                        _LOGGER.warning("Llega un mensaje que no corresponde a ninguna cuenta de usuario cuenta=\""  + data.account + "\" " + data.timestamp)   
                else:
                    _LOGGER.error("Paquete invalido")

        except Exception as err:
            MessageServer.errorcode = str(err)




    def add(self, callback, client: str):
        """Agrega un callback al message server"""
        if(client not in MessageServer.subscribers):
            _LOGGER.info("Se registra un suscriber para " + str(client))
            MessageServer.subscribers[client] = callback
        else:
            _LOGGER.warning("Suscriber para " + str(client) + " ya se encuentra registrado")


    def remove(self, client: str):
        """Quita un callback del message server"""
        if(client  in MessageServer.subscribers):
            _LOGGER.info("Se remueve un suscriber para " + str(client))
            MessageServer.subscribers.pop(client)
        else:
            _LOGGER.warning("Suscriber para " + str(client) + " no se encuentra registrado")
