"""Servicios de aplicación.

Responsabilidades de esta capa:
1. Autorización (¿el actor puede hacer esto?).
2. Validación de entrada vía ``core.domain.validadores``.
3. Unidad de trabajo: cada caso de uso es UNA transacción (``with self._db:``).
4. Auditoría: toda mutación deja rastro en la tabla ``auditoria``.

La UI nunca toca SQL ni archivos: solo llama a estos métodos y captura ``ErrorDominio``.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Any

from aquaterra.core import tiempo
from aquaterra.core.agronomia.hidrico import HUMEDAD_POST_RIEGO_SIMULADA_PCT, decidir_riego
from aquaterra.core.domain import (
    ErrorAutenticacion,
    ErrorPermiso,
    ErrorValidacion,
    EventoRiego,
    OrigenRiego,
    Parcela,
    Usuario,
)
from aquaterra.core.domain.validadores import (
    validar_datos_parcela,
    validar_litros,
    validar_umbral_humedad,
)
from aquaterra.infrastructure.db.repositorios import (
    RepositorioAuditoria,
    RepositorioParcelas,
    RepositorioRiegos,
    RepositorioUsuarios,
)
from aquaterra.infrastructure.seguridad import generar_hash, requiere_rehash, verificar_clave

log = logging.getLogger(__name__)


def _exigir_admin(actor: Usuario, accion: str) -> None:
    if not actor.es_admin:
        raise ErrorPermiso(accion)


# ──────────────────────────────────────────────────────────────────────────────
class ServicioAutenticacion:
    def __init__(self, conexion: sqlite3.Connection):
        self._db = conexion
        self._usuarios = RepositorioUsuarios(conexion)
        self._auditoria = RepositorioAuditoria(conexion)

    def iniciar_sesion(self, usuario: str, clave: str) -> Usuario:
        registro = self._usuarios.credenciales(usuario or "")
        if registro is None or not verificar_clave(clave or "", registro[1]):
            with self._db:
                self._auditoria.registrar("login_fallido", "usuario", None, None, {"usuario": usuario})
            raise ErrorAutenticacion()

        cuenta, hash_actual = registro
        with self._db:
            if requiere_rehash(hash_actual):
                self._usuarios.actualizar_hash(cuenta.id, generar_hash(clave))
            self._auditoria.registrar("login", "usuario", cuenta.id, cuenta.id)
        log.info("Sesión iniciada: %s (%s)", cuenta.usuario, cuenta.rol)
        return cuenta


# ──────────────────────────────────────────────────────────────────────────────
class ServicioParcelas:
    def __init__(self, conexion: sqlite3.Connection):
        self._db = conexion
        self._parcelas = RepositorioParcelas(conexion)
        self._auditoria = RepositorioAuditoria(conexion)

    def listar(self, *, solo_riego_auto: bool = False) -> list[Parcela]:
        return self._parcelas.listar(solo_riego_auto=solo_riego_auto)

    def obtener(self, parcela_id: int) -> Parcela:
        return self._parcelas.obtener(parcela_id)

    def crear(self, actor: Usuario, **campos: Any) -> Parcela:
        _exigir_admin(actor, "crear parcelas")
        datos = validar_datos_parcela(**campos)
        if self._parcelas.existe_nombre_activo(datos.nombre):
            raise ErrorValidacion(f"Ya existe una parcela activa llamada '{datos.nombre}'.")
        with self._db:
            parcela = self._parcelas.crear(datos)
            self._auditoria.registrar("crear", "parcela", parcela.id, actor.id, {"nombre": parcela.nombre})
        return parcela

    def actualizar(self, actor: Usuario, parcela_id: int, **campos: Any) -> Parcela:
        _exigir_admin(actor, "actualizar parcelas")
        datos = validar_datos_parcela(**campos)  # MISMA validación que crear (fix DT-03)
        if self._parcelas.existe_nombre_activo(datos.nombre, excluir_id=parcela_id):
            raise ErrorValidacion(f"Ya existe otra parcela activa llamada '{datos.nombre}'.")
        with self._db:
            anterior = self._parcelas.obtener(parcela_id)
            parcela = self._parcelas.actualizar(parcela_id, datos)
            cambios = {
                k: [getattr(anterior, k), getattr(parcela, k)]
                for k in ("nombre", "cultivo", "area_m2", "humedad_pct", "tipo_suelo", "riego_auto")
                if getattr(anterior, k) != getattr(parcela, k)
            }
            self._auditoria.registrar("actualizar", "parcela", parcela_id, actor.id, cambios)
        return parcela

    def archivar(self, actor: Usuario, parcela_id: int) -> Parcela:
        """Eliminación lógica: el id NO se reutiliza y los riegos conservan su vínculo (fix DT-01).

        Devuelve la parcela tal como quedó archivada.
        """
        _exigir_admin(actor, "eliminar parcelas")
        with self._db:
            parcela = self._parcelas.obtener(parcela_id)
            self._parcelas.archivar(parcela_id)
            self._auditoria.registrar("archivar", "parcela", parcela_id, actor.id, {"nombre": parcela.nombre})
        return self._parcelas.obtener(parcela_id, incluir_archivadas=True)


# ──────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class ResultadoRiego:
    aplicado: bool
    mensaje: str
    parcela: Parcela
    evento: EventoRiego | None = None


class ServicioRiego:
    def __init__(self, conexion: sqlite3.Connection):
        self._db = conexion
        self._parcelas = RepositorioParcelas(conexion)
        self._riegos = RepositorioRiegos(conexion)
        self._auditoria = RepositorioAuditoria(conexion)

    def aplicar_riego(
        self,
        actor: Usuario,
        *,
        parcela_id: int,
        umbral_pct: Any,
        litros: Any,
        fecha: date,
        hora: str,
    ) -> ResultadoRiego:
        _exigir_admin(actor, "ejecutar riegos")
        umbral = validar_umbral_humedad(umbral_pct)
        agua = validar_litros(litros)
        try:
            momento = tiempo.combinar(fecha, tiempo.parsear_hora(hora))
        except ValueError as exc:
            raise ErrorValidacion(str(exc)) from exc

        # Se relee la parcela desde la base (nunca desde un caché de la UI).
        parcela = self._parcelas.obtener(parcela_id)
        decision = decidir_riego(parcela.humedad_pct, umbral)
        if not decision.regar:
            return ResultadoRiego(False, decision.motivo, parcela)

        # Transacción atómica: humedad + evento + auditoría, todo o nada.
        with self._db:
            self._parcelas.actualizar_humedad(parcela_id, HUMEDAD_POST_RIEGO_SIMULADA_PCT)
            evento = self._riegos.registrar(
                parcela_id=parcela_id, momento_iso=tiempo.a_iso(momento),
                momento_epoch=tiempo.a_epoch(momento), agua_litros=agua,
                humedad_inicial_pct=parcela.humedad_pct,
                humedad_final_pct=HUMEDAD_POST_RIEGO_SIMULADA_PCT,
                origen=OrigenRiego.MANUAL, usuario_id=actor.id,
            )
            self._auditoria.registrar("riego", "parcela", parcela_id, actor.id,
                                      {"evento_id": evento.id, "litros": agua, "umbral": umbral})
        actualizada = self._parcelas.obtener(parcela_id)
        return ResultadoRiego(
            True,
            f"{decision.motivo}\nRiego aplicado: {agua:.0f} L · humedad → {actualizada.humedad_pct:.0f} %.",
            actualizada, evento,
        )


# ──────────────────────────────────────────────────────────────────────────────
class ServicioMonitor:
    def __init__(self, conexion: sqlite3.Connection):
        self._parcelas = RepositorioParcelas(conexion)
        self._riegos = RepositorioRiegos(conexion)

    def humedad_por_parcela(self) -> list[tuple[str, float]]:
        return [(p.nombre, p.humedad_pct) for p in self._parcelas.listar()]

    def consumo_por_parcela(self) -> list[tuple[str, float]]:
        return [(nombre, litros) for _, nombre, litros in self._riegos.consumo_por_parcela()]
