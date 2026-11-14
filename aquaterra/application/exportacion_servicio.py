"""Servicio de aplicación para Exportación Ejecutiva Multi-Hoja (``.xlsx``) y Series (``.csv``).

Orquesta ``NodePulseService``, ``RepositorioLecturas``, ``RepositorioEventosEstacion``,
``RepositorioRiegos`` y ``RepositorioIncidenciaRiego`` para construir entregables listos
para clientes e investigadores (Fase B4 — Módulo 2).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from aquaterra.application.pulso_servicio import NodePulseService
from aquaterra.core import tiempo
from aquaterra.core.analitica import PuntoVentanaMovil, construir_resumen_pulso_24h
from aquaterra.core.domain import EventoRiego, IncidenciaRiego
from aquaterra.infrastructure.db.repositorios import (
    RepositorioEstaciones,
    RepositorioEventosEstacion,
    RepositorioIncidenciaRiego,
    RepositorioLecturas,
    RepositorioParcelas,
    RepositorioRiegos,
)
from aquaterra.infrastructure.exportacion import (
    exportar_reporte_estacion_xlsx,
    exportar_series_csv,
)


class AnalyticsAndExportService:
    """Genera reportes ejecutivos ``.xlsx`` (3 hojas) y ``.csv`` con medias móviles para cualquier estación."""

    def __init__(self, conexion: sqlite3.Connection):
        self._db = conexion
        self._estaciones = RepositorioEstaciones(conexion)
        self._parcelas = RepositorioParcelas(conexion)
        self._lecturas = RepositorioLecturas(conexion)
        self._eventos = RepositorioEventosEstacion(conexion)
        self._riegos = RepositorioRiegos(conexion)
        self._incidencias = RepositorioIncidenciaRiego(conexion)
        self._pulso = NodePulseService(conexion)

    def _resolver_rango(
        self,
        estacion_id: int,
        desde_epoch: int | None,
        hasta_epoch: int | None,
    ) -> tuple[int, int]:
        techo = hasta_epoch if hasta_epoch is not None else self._lecturas.ultimo_epoch(estacion_id)
        if techo is None:
            techo = tiempo.a_epoch(tiempo.ahora())
        piso = desde_epoch if desde_epoch is not None else (techo - 86_400)
        return piso, techo

    def _ventanas_estacion(
        self,
        estacion_id: int,
        *,
        desde_epoch: int,
        hasta_epoch: int,
        ventana: str | int,
    ) -> dict[str, list[PuntoVentanaMovil]]:
        series, _ = self._lecturas.series_estacion_rango(
            estacion_id,
            desde_epoch=desde_epoch,
            hasta_epoch=hasta_epoch,
        )
        return {
            var: self._lecturas.serie_ventana_movil(
                estacion_id,
                var,
                desde_epoch=desde_epoch,
                hasta_epoch=hasta_epoch,
                ventana=ventana,
            )
            for var in sorted(series.keys())
        }

    def exportar_xlsx_estacion(
        self,
        estacion_id: int,
        ruta_destino: str | Path,
        *,
        desde_epoch: int | None = None,
        hasta_epoch: int | None = None,
        ventana: str | int = "1h",
    ) -> Path:
        """Exporta el reporte ejecutivo ``.xlsx`` con las 3 hojas reglamentarias."""
        estacion = self._estaciones.obtener(estacion_id)
        piso, techo = self._resolver_rango(estacion.id, desde_epoch, hasta_epoch)

        series, unidades = self._lecturas.series_estacion_rango(
            estacion.id,
            desde_epoch=piso,
            hasta_epoch=techo,
        )
        eventos_est = self._eventos.listar(estacion.id, desde_epoch=piso, hasta_epoch=techo)
        resumen = construir_resumen_pulso_24h(
            estacion,
            series,
            desde_epoch=piso,
            hasta_epoch=techo,
            unidades_por_variable=unidades,
            eventos=eventos_est,
        )
        ventanas = self._ventanas_estacion(
            estacion.id,
            desde_epoch=piso,
            hasta_epoch=techo,
            ventana=ventana,
        )

        riegos_estacion: list[EventoRiego] = []
        mapa_incidencias: dict[int, IncidenciaRiego] = {}
        for parcela in self._parcelas.listar():
            if parcela.estacion_id != estacion.id:
                continue
            for r in self._riegos.listar_por_parcela(parcela.id):
                if piso <= r.ts_epoch <= techo:
                    riegos_estacion.append(r)
            for inc in self._incidencias.listar_por_parcela(parcela.id):
                mapa_incidencias[inc.evento_riego_id] = inc

        etiqueta_v = f"{ventana}s" if isinstance(ventana, int) else str(ventana)
        return exportar_reporte_estacion_xlsx(
            ruta_destino,
            estacion=estacion,
            resumen_pulso=resumen,
            ventanas_por_variable=ventanas,
            eventos_estacion=eventos_est,
            eventos_riego=riegos_estacion,
            incidencias_por_riego=mapa_incidencias,
            etiqueta_ventana_movil=etiqueta_v,
        )

    def exportar_csv_estacion(
        self,
        estacion_id: int,
        ruta_destino: str | Path,
        *,
        desde_epoch: int | None = None,
        hasta_epoch: int | None = None,
        ventana: str | int = "1h",
    ) -> Path:
        """Exporta las series temporales en formato ancho + media móvil a ``.csv``."""
        estacion = self._estaciones.obtener(estacion_id)
        piso, techo = self._resolver_rango(estacion.id, desde_epoch, hasta_epoch)
        ventanas = self._ventanas_estacion(
            estacion.id,
            desde_epoch=piso,
            hasta_epoch=techo,
            ventana=ventana,
        )
        etiqueta_v = f"{ventana}s" if isinstance(ventana, int) else str(ventana)
        return exportar_series_csv(
            ruta_destino,
            ventanas_por_variable=ventanas,
            etiqueta_ventana_movil=etiqueta_v,
        )
