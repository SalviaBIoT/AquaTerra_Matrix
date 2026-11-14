"""Servicio de aplicación para el Pulso 24h del Nodo y el Laboratorio Analítico.

Orquesta ``RepositorioEstaciones``, ``RepositorioLecturas`` y ``RepositorioEventosEstacion``
con el motor determinista ``aquaterra.core.analitica`` (Fase B2).
"""

from __future__ import annotations

import sqlite3

from aquaterra.core import tiempo
from aquaterra.core.analitica import (
    MUESTRAS_ESPERADAS_24H,
    PuntoVentanaMovil,
    ResultadoCorrelacionBivariada,
    ResumenPulso24h,
    construir_resumen_pulso_24h,
    correlacion_bivariada,
)
from aquaterra.infrastructure.db.repositorios import (
    RepositorioEstaciones,
    RepositorioEventosEstacion,
    RepositorioLecturas,
)


class NodePulseService:
    """Genera el Pulso 24h por tipo de estación y ejecuta consultas de ventana móvil y correlación."""

    def __init__(self, conexion: sqlite3.Connection):
        self._db = conexion
        self._estaciones = RepositorioEstaciones(conexion)
        self._lecturas = RepositorioLecturas(conexion)
        self._eventos = RepositorioEventosEstacion(conexion)

    def obtener_pulso_24h(
        self,
        estacion_id: int,
        *,
        hasta_epoch: int | None = None,
        ventana_horas: int = 24,
    ) -> ResumenPulso24h:
        """Calcula el pulso determinista de las últimas ``ventana_horas`` (por defecto 24h).

        Si ``hasta_epoch`` es ``None``, se ancla al último timestamp válido registrado en la estación
        (o al reloj actual si la estación aún no posee lecturas), permitiendo analizar de inmediato
        lotes recién importados desde MicroSD.
        """
        if ventana_horas <= 0:
            raise ValueError(f"ventana_horas debe ser > 0 (recibido: {ventana_horas}).")

        estacion = self._estaciones.obtener(estacion_id)
        techo = hasta_epoch if hasta_epoch is not None else self._lecturas.ultimo_epoch(estacion_id)
        if techo is None:
            techo = tiempo.a_epoch(tiempo.ahora())
        piso = techo - (ventana_horas * 3600)

        series, unidades = self._lecturas.series_estacion_rango(
            estacion_id,
            desde_epoch=piso,
            hasta_epoch=techo,
        )
        eventos = self._eventos.listar(estacion_id, desde_epoch=piso, hasta_epoch=techo)
        muestras_esp = max(1, int(round((ventana_horas / 24.0) * MUESTRAS_ESPERADAS_24H)))

        return construir_resumen_pulso_24h(
            estacion,
            series,
            desde_epoch=piso,
            hasta_epoch=techo,
            unidades_por_variable=unidades,
            eventos=eventos,
            muestras_esperadas=muestras_esp,
        )

    def consultar_ventana_movil(
        self,
        estacion_id: int,
        variable: str,
        *,
        desde_epoch: int,
        hasta_epoch: int,
        ventana: str | int = "1h",
    ) -> list[PuntoVentanaMovil]:
        """Devuelve la serie con ``media_movil``, ``min_movil`` y ``max_movil`` vía SQLite Window Function."""
        self._estaciones.obtener(estacion_id)
        return self._lecturas.serie_ventana_movil(
            estacion_id,
            variable,
            desde_epoch=desde_epoch,
            hasta_epoch=hasta_epoch,
            ventana=ventana,
        )

    def comparar_variables(
        self,
        estacion_id: int,
        variable_x: str,
        variable_y: str,
        *,
        desde_epoch: int,
        hasta_epoch: int,
        tolerancia_seg: int = 300,
    ) -> ResultadoCorrelacionBivariada:
        """Calcula la correlación bivariada de Pearson $r$ entre dos variables de la estación."""
        self._estaciones.obtener(estacion_id)
        serie_x = self._lecturas.serie_rango(
            estacion_id,
            variable_x,
            desde_epoch=desde_epoch,
            hasta_epoch=hasta_epoch,
        )
        serie_y = self._lecturas.serie_rango(
            estacion_id,
            variable_y,
            desde_epoch=desde_epoch,
            hasta_epoch=hasta_epoch,
        )
        return correlacion_bivariada(
            serie_x,
            serie_y,
            variable_x=variable_x,
            variable_y=variable_y,
            tolerancia_seg=tolerancia_seg,
        )

    def obtener_series_ventana(
        self,
        estacion_id: int,
        *,
        horas: int = 24,
    ) -> tuple[object, int, int, dict[str, list[tuple[int, float]]], dict[str, str | None]]:
        """Devuelve ``(estacion, desde_epoch, hasta_epoch, series, unidades)`` para la UI Multi-Nodo."""
        estacion = self._estaciones.obtener(estacion_id)
        techo = self._lecturas.ultimo_epoch(estacion_id) or tiempo.a_epoch(tiempo.ahora())
        piso = 0 if horas <= 0 else max(0, techo - (horas * 3600))
        series, unidades = self._lecturas.series_estacion_rango(
            estacion_id, desde_epoch=piso, hasta_epoch=techo
        )
        return estacion, piso, techo, series, unidades
