
"""nothing."""


class SIAData:

    def __init__(self, data: bytearray) -> None:
        """Initialise."""
        
        self.valid: bool = False
        self.token: str = ""
        self.sequence: str = ""
        self.receiver: str = ""
        self.prefix: str = ""
        self.account: str = ""
        self.mdata: str = ""
        self.timestamp: str = ""
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

                self.timestamp = self.message_str[self.n + 1:]


    def crc16(self, data: bytearray):
        if data is None: return 0
        crcx = 0x0000
        for i in (range(0, len(data))):
            crcx ^= data[i]
            for j in range(0, 8):
                crcx = ((crcx >> 1) ^ 0xA001) if ((crcx & 0x0001) > 0) else (crcx >> 1)
        return crcx


    def replyMessage(self):
        replymessage = "\"ACK\"" + self.sequence + self.receiver + self.prefix + self.account + "[]"
        replyCRC = self.crc16(bytearray(replymessage.encode()))
        return "\n" + format(replyCRC, '#04x') + "0" + str(len(replymessage)) + replymessage + "\r"


    def parseADMCID(self):
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


    def __str__(self):
        return "<Token:" + self.token + ",Seq:" + self.sequence + ",Rec:" + self.receiver + ",Pref:" + self.prefix + \
            ",Acc:" + self.account + ",info:" + self.mdata + ",TS:" + self.timestamp + ">"

