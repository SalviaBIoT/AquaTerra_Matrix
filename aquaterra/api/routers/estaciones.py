"""Router de estaciones IoT, Radar priorizado, Pulso 24h, Series y Pronóstico."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from aquaterra.api.deps import get_contenedor, get_usuario_actual
from aquaterra.api.schemas import RegistrarEstacionRequest, serializar_objeto
from aquaterra.application.contenedor import Contenedor
from aquaterra.core.analitica import NivelSeveridadPulso
from aquaterra.core.domain import ErrorValidacion, TipoEstacion, Usuario

router = APIRouter(prefix="/api", tags=["estaciones"])


@router.get("/radar")
def obtener_radar(
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
    q: str = "",
    tipo: str | None = None,
    solo_con_alertas: bool = False,
) -> dict[str, object]:
    tipo_enum: TipoEstacion | None = None
    if tipo:
        try:
            tipo_enum = TipoEstacion(tipo)
        except ValueError as exc:
            raise ErrorValidacion(f"Tipo de estación inválido: '{tipo}'.") from exc

    entradas = contenedor.radar.buscar_estaciones(
        q,
        tipo_estacion=tipo_enum,
        solo_con_alertas=solo_con_alertas,
    )
    todas = contenedor.radar.listar_radar_priorizado()
    parcelas_activas = len(contenedor.parcelas.listar())
    conteos = {
        "total_estaciones": len(todas),
        "criticas": sum(1 for e in todas if e.severidad is NivelSeveridadPulso.CRITICO),
        "atenciones": sum(1 for e in todas if e.severidad is NivelSeveridadPulso.ATENCION),
        "optimas": sum(1 for e in todas if e.severidad is NivelSeveridadPulso.OPTIMO),
        "sin_datos": sum(1 for e in todas if e.severidad is NivelSeveridadPulso.SIN_DATOS),
        "parcelas_activas": parcelas_activas,
    }
    return {
        "resumen": conteos,
        "entradas": serializar_objeto(entradas),
    }


@router.get("/estaciones")
def listar_estaciones(
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, object]:
    return {"estaciones": serializar_objeto(contenedor.radar.listar_estaciones())}


@router.post("/estaciones", status_code=201)
def registrar_estacion(
    body: RegistrarEstacionRequest,
    actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, object]:
    try:
        tipo = TipoEstacion(body.tipo)
    except ValueError as exc:
        raise ErrorValidacion(f"Tipo de estación inválido: '{body.tipo}'.") from exc
    estacion = contenedor.sincronizacion.registrar_estacion(
        actor,
        codigo=body.codigo,
        nombre=body.nombre,
        tipo=tipo,
        latitud=body.latitud,
        longitud=body.longitud,
        altitud_m=body.altitud_m,
    )
    return {"estacion": serializar_objeto(estacion)}


@router.post("/estaciones/sembrar-base")
def sembrar_estaciones_base(
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, object]:
    estaciones = contenedor.sincronizacion.asegurar_estaciones_terrabit_base()
    return {"estaciones": serializar_objeto(estaciones)}


@router.get("/estaciones/{estacion_id}/pulso")
def obtener_pulso(
    estacion_id: int,
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
    ventana_horas: int = Query(default=24, ge=1, le=720),
) -> dict[str, object]:
    pulso = contenedor.pulso.obtener_pulso_24h(estacion_id, ventana_horas=ventana_horas)
    return {"pulso": serializar_objeto(pulso)}


@router.get("/estaciones/{estacion_id}/series")
def obtener_series(
    estacion_id: int,
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
    horas: int = Query(default=24, ge=0, le=8760),
) -> dict[str, object]:
    estacion, desde_ep, hasta_ep, series, unidades = contenedor.pulso.obtener_series_ventana(
        estacion_id, horas=horas
    )
    series_serializadas = {
        var: [[ts, val] for ts, val in sorted(puntos, key=lambda p: p[0])]
        for var, puntos in sorted(series.items())
    }
    return {
        "estacion": serializar_objeto(estacion),
        "desde_epoch": desde_ep,
        "hasta_epoch": hasta_ep,
        "unidades": unidades,
        "series": series_serializadas,
    }


@router.get("/estaciones/{estacion_id}/ventana-movil")
def obtener_ventana_movil(
    estacion_id: int,
    variable: str,
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
    horas: int = Query(default=24, ge=0, le=8760),
    ventana: str = "1h",
) -> dict[str, object]:
    _est, desde_ep, hasta_ep, _series, _unidades = contenedor.pulso.obtener_series_ventana(
        estacion_id, horas=horas
    )
    puntos = contenedor.pulso.consultar_ventana_movil(
        estacion_id,
        variable,
        desde_epoch=desde_ep,
        hasta_epoch=hasta_ep,
        ventana=ventana,
    )
    return {
        "variable": variable,
        "ventana": ventana,
        "desde_epoch": desde_ep,
        "hasta_epoch": hasta_ep,
        "puntos": serializar_objeto(puntos),
    }


@router.get("/estaciones/{estacion_id}/correlacion")
def calcular_correlacion(
    estacion_id: int,
    var_x: str,
    var_y: str,
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
    horas: int = Query(default=24, ge=0, le=8760),
) -> dict[str, object]:
    _est, desde_ep, hasta_ep, series, _unidades = contenedor.pulso.obtener_series_ventana(
        estacion_id, horas=horas
    )
    resultado = contenedor.pulso.comparar_variables(
        estacion_id, var_x, var_y, desde_epoch=desde_ep, hasta_epoch=hasta_ep
    )

    sx = sorted(series.get(var_x, []), key=lambda p: p[0])
    sy = sorted(series.get(var_y, []), key=lambda p: p[0])
    pares: list[list[float]] = []
    if sx and sy:
        idx_y = 0
        for tx, vx in sx:
            while idx_y + 1 < len(sy) and abs(sy[idx_y + 1][0] - tx) <= abs(sy[idx_y][0] - tx):
                idx_y += 1
            if abs(sy[idx_y][0] - tx) <= 300:
                pares.append([float(vx), float(sy[idx_y][1])])

    recta_ols: list[list[float]] | None = None
    if pares and resultado.pendiente_y_sobre_x is not None:
        xs = [p[0] for p in pares]
        ys = [p[1] for p in pares]
        mx = sum(xs) / len(xs)
        my = sum(ys) / len(ys)
        m = resultado.pendiente_y_sobre_x
        b = my - m * mx
        x_min, x_max = min(xs), max(xs)
        if x_max > x_min:
            recta_ols = [[x_min, round(m * x_min + b, 4)], [x_max, round(m * x_max + b, 4)]]

    return {
        "resultado": serializar_objeto(resultado),
        "pares": pares,
        "recta_ols": recta_ols,
    }


@router.get("/estaciones/{estacion_id}/pronostico")
def obtener_pronostico(
    estacion_id: int,
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
    horas: int = Query(default=48, ge=1, le=168),
) -> dict[str, object]:
    contenedor.radar.obtener_estacion(estacion_id)
    puntos = contenedor.sincronizacion.listar_pronostico_estacion(
        estacion_id, horas=horas, auto_descargar=True
    )
    return {"puntos": serializar_objeto(puntos)}


@router.get("/estaciones/{estacion_id}/eventos")
def obtener_eventos(
    estacion_id: int,
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
    limite: int = Query(default=50, ge=1, le=500),
) -> dict[str, object]:
    contenedor.radar.obtener_estacion(estacion_id)
    eventos = contenedor.radar.listar_eventos_estacion(estacion_id, limite=limite)
    return {"eventos": serializar_objeto(eventos)}


@router.post("/estaciones/{estacion_id}/reparar-rtc")
def reparar_rtc(
    estacion_id: int,
    actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, object]:
    reparadas = contenedor.sincronizacion.reparar_rtc_estacion(actor, estacion_id)
    return {"estacion_id": estacion_id, "reparadas": reparadas}


@router.post("/estaciones/{estacion_id}/narrar-24h")
def narrar_24h(
    estacion_id: int,
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, object]:
    res = contenedor.copiloto.generar_reporte_pulso_24h(estacion_id)
    return {
        "estacion_id": estacion_id,
        "mensaje": res["mensaje"],
        "proveedor_ia": res["proveedor_ia"],
        "reporte": res["reporte"],
    }
