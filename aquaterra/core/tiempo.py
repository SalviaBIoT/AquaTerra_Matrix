"""Estandarización temporal ISO-8601 para todo el ecosistema.

Decisión (ADR-004):
- Colombia no aplica horario de verano, por lo que se usa un desfase fijo UTC-05:00.
  Esto evita depender de la base IANA (``tzdata``) en Windows y en estaciones base
  con Python mínimo.
- Cada marca temporal persistida guarda DOS representaciones:
    * ``ts_iso``   -> texto legible ISO-8601 con desfase, p. ej. ``2026-11-13T06:00:00-05:00``.
    * ``ts_epoch`` -> entero Unix (segundos UTC) para ordenar, indexar y deduplicar.
  Los firmwares ESP32 (Nodo INTI, InBeersa) ya trabajan con epoch del RTC DS3231,
  así que el epoch es la llave natural de deduplicación de series temporales.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone

ZONA_COLOMBIA = timezone(timedelta(hours=-5), name="COT")

_PATRON_HORA = re.compile(r"^(?P<h>\d{1,2}):(?P<m>\d{2})(?::(?P<s>\d{2}))?$")


def ahora() -> datetime:
    """Instante actual consciente de zona (UTC-05:00), sin microsegundos."""
    return datetime.now(ZONA_COLOMBIA).replace(microsecond=0)


def a_iso(momento: datetime) -> str:
    """Serializa a ISO-8601 con desfase. Fechas ingenuas se asumen hora Colombia."""
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=ZONA_COLOMBIA)
    return momento.astimezone(ZONA_COLOMBIA).replace(microsecond=0).isoformat()


def ahora_iso() -> str:
    return a_iso(ahora())


def a_epoch(momento: datetime) -> int:
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=ZONA_COLOMBIA)
    return int(momento.timestamp())


def desde_epoch(epoch: int) -> datetime:
    return datetime.fromtimestamp(epoch, tz=ZONA_COLOMBIA)


def desde_iso(texto: str) -> datetime:
    momento = datetime.fromisoformat(texto)
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=ZONA_COLOMBIA)
    return momento


def parsear_hora(texto: str) -> time:
    """Interpreta ``HH:MM`` o ``H:MM`` (formato heredado de v3.2) con validación de rango.

    Raises:
        ValueError: si el texto no representa una hora válida de 24 h.
    """
    coincidencia = _PATRON_HORA.match(texto.strip())
    if not coincidencia:
        raise ValueError(f"Hora inválida '{texto}'. Use HH:MM (24 h).")
    h = int(coincidencia["h"])
    m = int(coincidencia["m"])
    s = int(coincidencia["s"] or 0)
    if not (0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59):
        raise ValueError(f"Hora fuera de rango '{texto}'.")
    return time(h, m, s)


def combinar(fecha: date, hora: time) -> datetime:
    return datetime.combine(fecha, hora, tzinfo=ZONA_COLOMBIA)


def parsear_fecha_legacy_v32(fecha_mdy: str, hora_hm: str) -> datetime:
    """Convierte el par (``MM/DD/YY``, ``H:MM``) de ``riegos.json`` v3.2 a datetime.

    v3.2 guardaba lo que devolvía ``DateEntry`` con el locale del sistema (formato
    estadounidense ambiguo, p. ej. ``11/27/25``). Aquí se normaliza de una vez.
    """
    fecha = datetime.strptime(fecha_mdy.strip(), "%m/%d/%y").date()
    return combinar(fecha, parsear_hora(hora_hm))
