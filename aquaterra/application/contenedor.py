"""Contenedor de dependencias (composition root).

Único lugar donde se "cablea" la aplicación: abre la base, aplica migraciones,
siembra datos legacy la primera vez y construye los servicios. Las pruebas y un
futuro daemon de ingesta (v5.0) reutilizan este mismo arranque sin la UI.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field

from aquaterra.application.control_servicio import DecisionAndControlService
from aquaterra.application.copiloto_servicio import CalibrationCopilotService
from aquaterra.application.exportacion_servicio import AnalyticsAndExportService
from aquaterra.application.pulso_servicio import NodePulseService
from aquaterra.application.radar_servicio import StationDiscoveryService
from aquaterra.application.servicios import (
    ServicioAutenticacion,
    ServicioMonitor,
    ServicioParcelas,
    ServicioRiego,
)
from aquaterra.application.sincronizacion_servicio import ActiveSyncAndGatewayService
from aquaterra.config import Configuracion, configuracion_por_defecto
from aquaterra.infrastructure.db import abrir_conexion, aplicar_migraciones
from aquaterra.infrastructure.db.repositorios import RepositorioUsuarios
from aquaterra.infrastructure.legacy.migrador_v32 import migrar_semilla_v32

log = logging.getLogger(__name__)


@dataclass
class Contenedor:
    config: Configuracion
    conexion: sqlite3.Connection
    auth: ServicioAutenticacion = field(init=False)
    parcelas: ServicioParcelas = field(init=False)
    riego: ServicioRiego = field(init=False)
    monitor: ServicioMonitor = field(init=False)
    pulso: NodePulseService = field(init=False)
    control: DecisionAndControlService = field(init=False)
    radar: StationDiscoveryService = field(init=False)
    exportacion: AnalyticsAndExportService = field(init=False)
    copiloto: CalibrationCopilotService = field(init=False)
    sincronizacion: ActiveSyncAndGatewayService = field(init=False)

    def __post_init__(self) -> None:
        self.auth = ServicioAutenticacion(self.conexion)
        self.parcelas = ServicioParcelas(self.conexion)
        self.riego = ServicioRiego(self.conexion)
        self.monitor = ServicioMonitor(self.conexion)
        self.pulso = NodePulseService(self.conexion)
        self.control = DecisionAndControlService(self.conexion)
        self.radar = StationDiscoveryService(self.conexion)
        self.exportacion = AnalyticsAndExportService(self.conexion)
        self.copiloto = CalibrationCopilotService(self.conexion)
        self.sincronizacion = ActiveSyncAndGatewayService(
            self.conexion, ruta_db=self.config.ruta_db, copiloto=self.copiloto
        )

    def cerrar(self) -> None:
        try:
            self.sincronizacion.detener_worker_segundo_plano()
            # Consolida el WAL en el archivo principal al salir (copias de seguridad limpias).
            self.conexion.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        finally:
            self.conexion.close()


def construir_contenedor(config: Configuracion | None = None, *, sembrar_legacy: bool = True) -> Contenedor:
    config = config or configuracion_por_defecto()
    conexion = abrir_conexion(config.ruta_db)
    version = aplicar_migraciones(conexion)
    log.info("Base de datos %s en esquema v%d", config.ruta_db, version)

    if sembrar_legacy and RepositorioUsuarios(conexion).contar() == 0:
        log.warning("Base vacía: importando semilla AquaUTP v3.2 desde %s", config.ruta_semilla_legacy)
        resumen = migrar_semilla_v32(conexion, config.ruta_semilla_legacy)
        log.info("Migración v3.2 completada:\n%s", resumen.como_texto())

    return Contenedor(config=config, conexion=conexion)
