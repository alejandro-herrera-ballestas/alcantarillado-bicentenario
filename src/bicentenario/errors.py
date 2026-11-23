"""Excepciones propias del proyecto.

Todas heredan de ``BicentenarioError`` para poder capturarlas juntas en la
interfaz y mostrar el mensaje al usuario sin que la aplicación se cierre con
un traceback. Los mensajes están escritos para leerse tal cual en pantalla.


"""

from __future__ import annotations


class BicentenarioError(Exception):
    """Clase base de todos los errores controlados de la aplicación."""


class DataLoadError(BicentenarioError):
    """No se pudo leer el origen de datos.

    Casos: el archivo no existe, no es un Excel válido, falta una hoja o
    una columna obligatoria. Son errores que impiden seguir leyendo.
    """

    def __init__(self, message: str, *, path=None, sheet: str | None = None):
        super().__init__(message)
        self.path = path
        self.sheet = sheet


class DataValidationError(BicentenarioError):
    """Los datos se leyeron, pero tienen errores que impiden usarlos."""

    def __init__(self, message: str, report=None):
        super().__init__(message)
        self.report = report


class InputValidationError(BicentenarioError):
    """Un dato escrito por el usuario en la interfaz no es válido."""


class InvalidStateError(BicentenarioError):
    """La operación no está permitida en el estado actual.

    Ejemplo: pausar cuando no hay una simulación corriendo.
    """
