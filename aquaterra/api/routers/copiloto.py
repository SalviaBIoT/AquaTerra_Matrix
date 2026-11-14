"""Router del Copiloto IA, Auditoría de Calibración, Rollback y Dataset SFT."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from aquaterra.api.deps import exigir_admin, get_contenedor, get_usuario_actual
from aquaterra.api.schemas import (
    AplicarCalibracionRequest,
    ConsultarCopilotoRequest,
    RollbackCalibracionRequest,
    serializar_objeto,
)
from aquaterra.application.contenedor import Contenedor
from aquaterra.core.copiloto import CATALOGO_COTAS_CALIBRACION
from aquaterra.core.domain import Usuario
from aquaterra.infrastructure.db.repositorios import RepositorioCalibraciones

router = APIRouter(prefix="/api", tags=["copiloto"])


@router.get("/copiloto/estado")
def estado_copiloto(
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
    estacion_id: int | None = None,
    parcela_id: int | None = None,
    solo_sin_estacion: bool = False,
) -> dict[str, object]:
    version, params = contenedor.copiloto.obtener_calibracion_efectiva(
        estacion_id=estacion_id, parcela_id=parcela_id
    )
    historial = contenedor.copiloto.listar_historial_conversaciones(
        estacion_id=estacion_id,
        parcela_id=parcela_id,
        solo_sin_estacion=solo_sin_estacion,
    )
    historial_global = contenedor.copiloto.listar_historial_conversaciones()
    repo_cal = RepositorioCalibraciones(contenedor.conexion)
    versiones = repo_cal.listar_versiones(
        estacion_id=estacion_id, parcela_id=parcela_id
    )
    versiones_globales = repo_cal.listar_recientes_globales(limite=12)
    return {
        "version_actual": version,
        "parametros_actuales": params,
        "catalogo_cotas": serializar_objeto(CATALOGO_COTAS_CALIBRACION),
        "historial": serializar_objeto(list(reversed(historial))),
        "historial_reciente_global": serializar_objeto(list(reversed(historial_global[-15:]))),
        "versiones": serializar_objeto(list(reversed(versiones))),
        "versiones_globales": serializar_objeto(versiones_globales),
    }


@router.post("/copiloto/consultar")
def consultar_copiloto(
    body: ConsultarCopilotoRequest,
    actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, object]:
    if body.aplicar_ajustes:
        exigir_admin(actor, "aplicar ajustes de calibración")
    res = contenedor.copiloto.consultar_copiloto(
        body.mensaje,
        estacion_id=body.estacion_id,
        parcela_id=body.parcela_id,
        usuario_id=actor.id,
        aplicar_ajustes=body.aplicar_ajustes,
    )
    return {"respuesta": serializar_objeto(res)}


@router.post("/copiloto/aplicar")
def aplicar_calibracion(
    body: AplicarCalibracionRequest,
    actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, object]:
    exigir_admin(actor, "aplicar calibraciones del copiloto")
    version = contenedor.copiloto.aplicar_ajustes_interaccion(
        body.interaccion_id,
        autor_id=actor.id,
        motivo_adicional=body.motivo_adicional,
    )
    return {"version": serializar_objeto(version)}


@router.post("/copiloto/rollback")
def rollback_calibracion(
    body: RollbackCalibracionRequest,
    actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, object]:
    exigir_admin(actor, "revertir calibraciones")
    version = contenedor.copiloto.revertir_calibracion(
        estacion_id=body.estacion_id,
        parcela_id=body.parcela_id,
        version_id_destino=body.version_id_destino,
        autor_id=actor.id,
    )
    return {"version": serializar_objeto(version)}


@router.get("/copiloto/dataset.jsonl")
def exportar_dataset_jsonl(
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
    solo_con_ajustes: bool = False,
) -> Response:
    with tempfile.TemporaryDirectory() as tmpdir:
        destino = Path(tmpdir) / "aquaterra_copiloto_sft.jsonl"
        total = contenedor.copiloto.exportar_dataset_entrenamiento_jsonl(
            destino, solo_con_ajustes=solo_con_ajustes
        )
        contenido = destino.read_bytes()
    return Response(
        content=contenido,
        media_type="application/x-ndjson; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="aquaterra_copiloto_sft.jsonl"',
            "X-Ejemplos-Exportados": str(total),
        },
    )
