class GarnetPanelInfo():
    """Encapsula datos del panel."""

    def __init__(self, id: str, guid: str, name: str) -> None:
        self.id = id
        self.guid = guid
        self.name = name
        self.model = ""
        self.version = ""
        self.modelName = ""
        self.versionName = ""
        self.manufacturer = "Garnet Technologies"

    def __str__(self):
        return "<id: "+ str(self.id) + ", name: \""+ str(self.name) + "\", guid: "+ str(self.guid) + ", modelName: \"" + self.modelName + "\", model: " + str(self.model) + ", versionName: " + str(self.versionName) + ", version: " + str(self.version) + ">"


class User():
    """Encapsula datos del usuario."""

    def __init__(self, name: str, email: str) -> None:
        self.name = name
        self.email = email
        self.arm_permision = False
        self.disarm_permision = False
        self.disable_zone_permision = False
        self.horn_permision = False

    def __str__(self):
        return "<name: \""+ str(self.name) + "\", email: \"" + self.email + "\", arm_permision: " + str(self.arm_permision) + ", disarm_permision: " + str(self.disarm_permision) + ", disable_zone_permision: " + str(self.disable_zone_permision) + ", horn_permision: " + str(self.horn_permision) + ">"


class Zone():
    """Encapsula datos de la zona."""

    def __init__(self, id: int, name: str = "", enabled: bool = False, interior: bool = False, icon: int = 0, 
                 open: bool = False, alarmed: bool = False, bypassed: bool = False) -> None:
        self.id = id
        self.name = name
        self.enabled = enabled
        self.interior = interior
        self.icon = icon        # 0:puerta     1: ventana     2: puerta trasera    3: dormitorio
                                # 4:living     5: cocina      6: garage            7: jardin
                                # 8:balcon     9: incendio   10: oficina          11: sensor
        self.open = open
        self.alarmed = alarmed
        self.bypassed = bypassed

    def __str__(self):
        return "<id: "+ str(self.id) + ", name: \"" + self.name + "\", interior: " + str(self.interior) + ", icon: " + str(self.icon) + \
                ", open: " + str(self.open) + ", alarmed: " + str(self.alarmed) +  ", bypassed: " + str(self.bypassed) + ", enabled: " + str(self.enabled) + ">"


class Partition():
    """Encapsula datos de la particion."""

    def __init__(self, id: int, name: str = "", armed: bool = False, alarmed: bool = False, enabled: bool = False) -> None:
        self.id = id
        self.name = name
        self.enabled = enabled
        self.armed = armed
        self.alarmed = armed

    def __str__(self):
        return "<id: "+ str(self.id) + ", name: \"" + self.name + "\", armed: " + str(self.armed) + ", alarmed: " + str(self.alarmed) + ", enabled: " + str(self.enabled) + ">"

