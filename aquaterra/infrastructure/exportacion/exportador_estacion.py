"""Construcción de reportes ejecutivos multi-hoja (``.xlsx``) y series (``.csv``) para estaciones.

Estructura las 3 hojas definidas en la Brújula Maestra:
1. ``1_Ficha_y_Resumen``: Metadatos de la estación, diagnóstico del periodo y estadísticas por variable.
2. ``2_Series_Temporales``: Matriz temporal en formato ancho con valores crudos y medias móviles.
3. ``3_Eventos_y_Riegos``: Historial consolidado de riegos (con incidencia en suelo) y eventos discretos.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from aquaterra.core import tiempo
from aquaterra.core.analitica import PuntoVentanaMovil, ResumenPulso24h
from aquaterra.core.domain import Estacion, EventoEstacion, EventoRiego, IncidenciaRiego
from aquaterra.infrastructure.exportacion.xlsx_writer import HojaCalculo, escribir_libro_xlsx


def construir_hojas_reporte_estacion(
    *,
    estacion: Estacion,
    resumen_pulso: ResumenPulso24h,
    ventanas_por_variable: Mapping[str, Sequence[PuntoVentanaMovil]],
    eventos_estacion: Sequence[EventoEstacion] = (),
    eventos_riego: Sequence[EventoRiego] = (),
    incidencias_por_riego: Mapping[int, IncidenciaRiego] | None = None,
    etiqueta_ventana_movil: str = "1h",
) -> tuple[HojaCalculo, HojaCalculo, HojaCalculo]:
    """Construye las 3 hojas ejecutivas (``1_Ficha_y_Resumen``, ``2_Series_Temporales``, ``3_Eventos_y_Riegos``)."""
    incidencias = incidencias_por_riego or {}

    # ── Hoja 1: Ficha técnica y resumen estadístico del periodo ──
    filas_ficha: list[list[Any]] = [
        ["Codigo_Estacion", estacion.codigo],
        ["Nombre_Estacion", estacion.nombre],
        ["Tipo_Ecosistema", estacion.tipo.value],
        ["Latitud", estacion.latitud if estacion.latitud is not None else "N/D"],
        ["Longitud", estacion.longitud if estacion.longitud is not None else "N/D"],
        ["Altitud_m", estacion.altitud_m if estacion.altitud_m is not None else "N/D"],
        ["Desde_ISO", tiempo.a_iso(tiempo.desde_epoch(resumen_pulso.desde_epoch))],
        ["Hasta_ISO", tiempo.a_iso(tiempo.desde_epoch(resumen_pulso.hasta_epoch))],
        ["Severidad_Periodo", resumen_pulso.severidad.value],
        ["Completitud_Global_Pct", resumen_pulso.completitud_global_pct],
        ["Diagnostico_Ejecutivo", resumen_pulso.diagnostico_determinista],
        [],
        [
            "Variable",
            "Unidad",
            "Ultimo_Valor",
            "Media_Periodo",
            "Minimo_Periodo",
            "Maximo_Periodo",
            "Tendencia",
            "Tasa_Por_Hora",
            "Muestras",
            "Completitud_Pct",
        ],
    ]
    for var_nombre, rv in sorted(resumen_pulso.variables.items()):
        filas_ficha.append(
            [
                var_nombre,
                rv.unidad or "",
                rv.ultimo_valor,
                rv.media_24h,
                rv.min_24h,
                rv.max_24h,
                rv.tendencia.simbolo,
                rv.tasa_hora if rv.tasa_hora is not None else "",
                rv.muestras,
                rv.completitud_pct,
            ]
        )

    hoja_1 = HojaCalculo(
        nombre="1_Ficha_y_Resumen",
        encabezados=("Campo_o_Variable", "Valor_o_Detalle"),
        filas=filas_ficha,
    )

    # ── Hoja 2: Series temporales en formato ancho + media móvil ──
    variables_ordenadas = sorted(ventanas_por_variable.keys())
    encabezados_s2: list[str] = ["Timestamp_Epoch", "Fecha_Hora_ISO"]
    for var in variables_ordenadas:
        encabezados_s2.append(var)
        encabezados_s2.append(f"{var}_media_movil_{etiqueta_ventana_movil}")

    # Indexar por timestamp para construir la matriz ancha
    por_timestamp: dict[int, dict[str, PuntoVentanaMovil]] = {}
    for var, puntos in ventanas_por_variable.items():
        for p in puntos:
            por_timestamp.setdefault(p.ts_epoch, {})[var] = p

    filas_series: list[list[Any]] = []
    for ts in sorted(por_timestamp.keys()):
        mapa_ts = por_timestamp[ts]
        iso_str = next(iter(mapa_ts.values())).ts_iso
        fila: list[Any] = [ts, iso_str]
        for var in variables_ordenadas:
            punto = mapa_ts.get(var)
            if punto is not None:
                fila.append(punto.valor)
                fila.append(punto.media_movil)
            else:
                fila.append("")
                fila.append("")
        filas_series.append(fila)

    hoja_2 = HojaCalculo(
        nombre="2_Series_Temporales",
        encabezados=encabezados_s2,
        filas=filas_series,
    )

    # ── Hoja 3: Eventos de estación y riegos con incidencia ──
    encabezados_s3 = (
        "Categoria",
        "Timestamp_Epoch",
        "Fecha_Hora_ISO",
        "Tipo_o_Origen",
        "Detalle_Principal",
        "Efectividad_o_Archivo",
        "Observaciones",
    )
    filas_eventos: list[list[Any]] = []

    for riego in eventos_riego:
        inc = incidencias.get(riego.id)
        efectividad_txt = inc.efectividad.value if inc else "sin_evaluar"
        obs_txt = (
            f"Δθ_A={inc.delta_a_pct:+.1f}% ({inc.observaciones or ''})"
            if inc
            else f"Humedad {riego.humedad_inicial_pct:.1f}% -> {riego.humedad_final_pct:.1f}%"
        )
        filas_eventos.append(
            [
                "RIEGO",
                riego.ts_epoch,
                riego.ts_iso,
                riego.origen.value,
                f"Parcela #{riego.parcela_id} · {riego.agua_litros:.1f} L",
                efectividad_txt,
                obs_txt,
            ]
        )

    for ev in eventos_estacion:
        filas_eventos.append(
            [
                "EVENTO_ESTACION",
                ev.ts_epoch,
                ev.ts_iso,
                ev.tipo_evento,
                ev.valor_texto or "",
                ev.archivo_ruta or "",
                str(ev.metadatos) if ev.metadatos else "",
            ]
        )

    filas_eventos.sort(key=lambda r: int(r[1]))
    hoja_3 = HojaCalculo(
        nombre="3_Eventos_y_Riegos",
        encabezados=encabezados_s3,
        filas=filas_eventos,
    )

    return hoja_1, hoja_2, hoja_3


def exportar_reporte_estacion_xlsx(
    ruta_destino: str | Path,
    *,
    estacion: Estacion,
    resumen_pulso: ResumenPulso24h,
    ventanas_por_variable: Mapping[str, Sequence[PuntoVentanaMovil]],
    eventos_estacion: Sequence[EventoEstacion] = (),
    eventos_riego: Sequence[EventoRiego] = (),
    incidencias_por_riego: Mapping[int, IncidenciaRiego] | None = None,
    etiqueta_ventana_movil: str = "1h",
) -> Path:
    """Genera el libro ejecutivo ``.xlsx`` de 3 hojas en ``ruta_destino``."""
    hojas = construir_hojas_reporte_estacion(
        estacion=estacion,
        resumen_pulso=resumen_pulso,
        ventanas_por_variable=ventanas_por_variable,
        eventos_estacion=eventos_estacion,
        eventos_riego=eventos_riego,
        incidencias_por_riego=incidencias_por_riego,
        etiqueta_ventana_movil=etiqueta_ventana_movil,
    )
    return escribir_libro_xlsx(ruta_destino, hojas)


def exportar_series_csv(
    ruta_destino: str | Path,
    *,
    ventanas_por_variable: Mapping[str, Sequence[PuntoVentanaMovil]],
    etiqueta_ventana_movil: str = "1h",
) -> Path:
    """Exporta la matriz temporal en formato ancho (con columnas de media móvil) a un archivo ``.csv`` UTF-8."""
    destino = Path(ruta_destino)
    destino.parent.mkdir(parents=True, exist_ok=True)

    variables_ordenadas = sorted(ventanas_por_variable.keys())
    encabezados = ["Timestamp_Epoch", "Fecha_Hora_ISO"]
    for var in variables_ordenadas:
        encabezados.append(var)
        encabezados.append(f"{var}_media_movil_{etiqueta_ventana_movil}")

    por_timestamp: dict[int, dict[str, PuntoVentanaMovil]] = {}
    for var, puntos in ventanas_por_variable.items():
        for p in puntos:
            por_timestamp.setdefault(p.ts_epoch, {})[var] = p

    with destino.open("w", encoding="utf-8", newline="") as f:
        escritor = csv.writer(f)
        escritor.writerow(encabezados)
        for ts in sorted(por_timestamp.keys()):
            mapa_ts = por_timestamp[ts]
            iso_str = next(iter(mapa_ts.values())).ts_iso
            fila: list[Any] = [ts, iso_str]
            for var in variables_ordenadas:
                punto = mapa_ts.get(var)
                if punto is not None:
                    fila.extend([punto.valor, punto.media_movil])
                else:
                    fila.extend(["", ""])
            escritor.writerow(fila)

    return destino
