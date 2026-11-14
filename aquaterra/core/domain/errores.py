"""Jerarquía de excepciones de dominio.

La UI captura ``ErrorDominio`` y muestra ``str(error)`` al usuario; cualquier otra
excepción se considera un defecto de software y se registra en el log.
"""

from __future__ import annotations


class ErrorDominio(Exception):
    """Raíz de todos los errores esperables del negocio."""


class ErrorValidacion(ErrorDominio):
    """Datos de entrada inválidos. Acumula todos los problemas detectados."""

    def __init__(self, problemas: list[str] | str):
        self.problemas = [problemas] if isinstance(problemas, str) else list(problemas)
        super().__init__("\n".join(f"• {p}" for p in self.problemas))


class EntidadNoEncontrada(ErrorDominio):
    def __init__(self, entidad: str, identificador: object):
        self.entidad = entidad
        self.identificador = identificador
        super().__init__(f"{entidad} con id={identificador} no existe o fue archivada.")


class ErrorAutenticacion(ErrorDominio):
    def __init__(self) -> None:
        # Mensaje genérico a propósito: no revela si falló el usuario o la clave.
        super().__init__("Usuario o contraseña incorrectos.")


class ErrorSesionExpirada(ErrorDominio):
    """Token de sesión ausente, revocado o expirado (HTTP 401 sin confundir con clave errónea)."""

    def __init__(self, detalle: str | None = None) -> None:
        super().__init__(
            detalle or "Tu sesión ha expirado o no ha sido iniciada. Inicia sesión nuevamente."
        )


class ErrorPermiso(ErrorDominio):
    def __init__(self, accion: str):
        super().__init__(f"No tiene permisos para: {accion}.")
