"""General exceptions."""

class GarnetPermissionError(Exception):
    """Excepcion para reportar un permiso no permitido."""

class GeneralGarnetError(Exception):
    """Excepcion para reportar un error cualquiera."""

class UnresponsiveGarnetAPI(Exception):
    """Excepcion para API Garnet sin respuesta."""

class InvokeGarnetAPIException(Exception):
    """Excepcion ante error en API Garnet."""

class SystemDoesNotExistException(Exception):
    """ID de panel no existe en Garnet Control."""
