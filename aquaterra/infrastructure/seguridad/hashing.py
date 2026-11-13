"""Derivación de claves PBKDF2-HMAC-SHA256 (resuelve DT-05b: claves en texto plano).

Formato autodescriptivo almacenado en ``usuarios.hash_clave``::

    pbkdf2_sha256$<iteraciones>$<salt_b64>$<hash_b64>

- Solo librería estándar (``hashlib``): sin dependencias nativas que compilar en
  Windows ni en Raspberry Pi.
- 600 000 iteraciones: recomendación OWASP vigente para PBKDF2-HMAC-SHA256.
- Salt aleatorio de 16 bytes por usuario (``secrets``) -> claves iguales producen
  hashes distintos.
- Comparación en tiempo constante (``hmac.compare_digest``) contra ataques de tiempo.
- ``requiere_rehash`` permite subir el costo en el futuro: al siguiente login
  exitoso el hash se regenera de forma transparente.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

ALGORITMO = "pbkdf2_sha256"
ITERACIONES_POR_DEFECTO = 600_000
_BYTES_SALT = 16


def _b64(datos: bytes) -> str:
    return base64.b64encode(datos).decode("ascii")


def generar_hash(clave: str, *, iteraciones: int = ITERACIONES_POR_DEFECTO) -> str:
    if not clave:
        raise ValueError("La contraseña no puede estar vacía.")
    salt = secrets.token_bytes(_BYTES_SALT)
    derivada = hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), salt, iteraciones)
    return f"{ALGORITMO}${iteraciones}${_b64(salt)}${_b64(derivada)}"


def verificar_clave(clave: str, hash_almacenado: str) -> bool:
    try:
        algoritmo, iter_txt, salt_b64, hash_b64 = hash_almacenado.split("$")
        if algoritmo != ALGORITMO:
            return False
        salt = base64.b64decode(salt_b64)
        esperado = base64.b64decode(hash_b64)
        iteraciones = int(iter_txt)
    except (ValueError, TypeError):
        return False
    calculado = hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), salt, iteraciones)
    return hmac.compare_digest(calculado, esperado)


def requiere_rehash(hash_almacenado: str, *, iteraciones: int = ITERACIONES_POR_DEFECTO) -> bool:
    try:
        algoritmo, iter_txt, *_ = hash_almacenado.split("$")
        return algoritmo != ALGORITMO or int(iter_txt) < iteraciones
    except ValueError:
        return True
