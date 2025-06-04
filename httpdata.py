"""Clases que usa la API HTTP"""


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
        return f"<id: {str(self.id)}, name: \"{str(self.name)}\", guid: {str(self.guid)}, modelName: \"{self.modelName}\", model: {str(self.model)}, versionName: {str(self.versionName)}, version: {str(self.version) }>"


class GarnetHTTPUser():
    """Encapsula datos del usuario de la WEB de Garnet."""

    def __init__(self, email: str, password: str) -> None:
        self.email = email
        self.password = password
        self.name = None
        self.arm_permision = None
        self.disarm_permision = None
        self.disable_zone_permision = None
        self.horn_permision = None


    def __str__(self):
        return f"<name: \"{str(self.name)}\", email: \"{self.email}\", password: \"{self.password}\", arm_permision: {str(self.arm_permision)}, disarm_permision: {str(self.disarm_permision)}, disable_zone_permision: {str(self.disable_zone_permision)}, horn_permision: {str(self.horn_permision)}>"


class Zone():
    """Encapsula datos de la zona."""

    def __init__(self, id: int, name: str = "", enabled: bool = False, interior: bool = False, icon: int = 0, open: bool = False, alarmed: bool = False, bypassed: bool = False) -> None:
        self.id = id
        self.name = name
        self.enabled = enabled
        self.interior = interior
        self.icon = icon        
        self.open = open
        self.alarmed = alarmed
        self.bypassed = bypassed


    def __str__(self):
        return f"<id: {str(self.id)}, name: \"{self.name}\", interior: {str(self.interior)}, icon: {str(self.icon)}, open: {str(self.open)}, alarmed: {str(self.alarmed)}, bypassed: {str(self.bypassed)}, enabled: {str(self.enabled)}>"


    def translate_icon(icon: int | None) -> str:
        """Translate icon based on id"""
        # 0:puerta     1: ventana     2: puerta trasera    3: dormitorio
        # 4:living     5: cocina      6: garage            7: jardin
        # 8:balcon     9: incendio   10: oficina          11: sensor
        if icon is not None and int(icon) < 12:
            return ["mdi:door", "mdi:window-closed-variant", "mdi:door-closed", "mdi:bed", "mdi:sofa", "mdi:stove", 
                    "mdi:garage", "mdi:flower", "mdi:balcony", "mdi:fire", "mdi:briefcase", "mdi:leak"][int(icon)]
        return None


class Partition():
    """Encapsula datos de la particion."""


    def __init__(self, id: int, name: str = "", armed: str = "Unknown", alarmed: bool = False, enabled: bool = False) -> None:
        self.id = id
        self.name = name
        self.enabled = enabled
        self.armed = armed
        self.alarmed = armed


    def __str__(self):
        return f"<id: {str(self.id)}, name: \"{self.name}\", armed: {self.armed}, alarmed: {str(self.alarmed)}, enabled: {str(self.enabled)}>"

