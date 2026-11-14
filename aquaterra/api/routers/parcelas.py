"""Router de Parcelas, Cultivos y Comparativo de Monitor."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from aquaterra.api.deps import get_contenedor, get_usuario_actual
from aquaterra.api.schemas import (
    ActualizarParcelaRequest,
    CrearParcelaRequest,
    serializar_objeto,
)
from aquaterra.application.contenedor import Contenedor
from aquaterra.core.domain import CULTIVOS_SOPORTADOS, TipoSuelo, Usuario

router = APIRouter(prefix="/api", tags=["parcelas"])


@router.get("/parcelas")
def listar_parcelas(
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
    solo_riego_auto: bool = False,
) -> dict[str, object]:
    parcelas = contenedor.parcelas.listar(solo_riego_auto=solo_riego_auto)
    return {
        "parcelas": serializar_objeto(parcelas),
        "cultivos_soportados": list(CULTIVOS_SOPORTADOS),
        "tipos_suelo": [s.value for s in TipoSuelo],
    }


@router.get("/parcelas/{parcela_id}")
def obtener_parcela(
    parcela_id: int,
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, object]:
    return {"parcela": serializar_objeto(contenedor.parcelas.obtener(parcela_id))}


@router.post("/parcelas", status_code=201)
def crear_parcela(
    body: CrearParcelaRequest,
    actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, object]:
    parcela = contenedor.parcelas.crear(
        actor,
        nombre=body.nombre,
        cultivo=body.cultivo,
        area=body.area_m2,
        humedad=body.humedad_pct,
        suelo=body.tipo_suelo,
        riego_auto=body.riego_auto,
        estacion_id=body.estacion_id,
    )
    return {"parcela": serializar_objeto(parcela)}


@router.patch("/parcelas/{parcela_id}")
def actualizar_parcela(
    parcela_id: int,
    body: ActualizarParcelaRequest,
    actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, object]:
    actual = contenedor.parcelas.obtener(parcela_id)
    estacion_final = (
        None
        if body.desvincular_estacion
        else (body.estacion_id if body.estacion_id is not None else actual.estacion_id)
    )
    parcela = contenedor.parcelas.actualizar(
        actor,
        parcela_id,
        nombre=body.nombre if body.nombre is not None else actual.nombre,
        cultivo=body.cultivo if body.cultivo is not None else actual.cultivo,
        area=body.area_m2 if body.area_m2 is not None else actual.area_m2,
        humedad=body.humedad_pct if body.humedad_pct is not None else actual.humedad_pct,
        suelo=body.tipo_suelo if body.tipo_suelo is not None else actual.tipo_suelo.value,
        riego_auto=body.riego_auto if body.riego_auto is not None else actual.riego_auto,
        estacion_id=estacion_final,
    )
    return {"parcela": serializar_objeto(parcela)}


@router.delete("/parcelas/{parcela_id}")
def archivar_parcela(
    parcela_id: int,
    actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, object]:
    archivada = contenedor.parcelas.archivar(actor, parcela_id)
    return {"parcela": serializar_objeto(archivada)}


@router.get("/monitor/comparativo")
def comparativo_parcelas(
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, object]:
    humedad = [
        {"nombre": nom, "humedad_pct": hum}
        for nom, hum in contenedor.monitor.humedad_por_parcela()
    ]
    consumo = [
        {"nombre": nom, "litros": lit}
        for nom, lit in contenedor.monitor.consumo_por_parcela()
    ]
    return {
        "humedad_por_parcela": humedad,
        "consumo_por_parcela": consumo,
    }
