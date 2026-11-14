"""Router de Sistema, Conectividad, Sync Híbrida, Buscador Ctrl+K y Exportación."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from aquaterra import __version__
from aquaterra.api.deps import exigir_admin, get_contenedor, get_usuario_actual
from aquaterra.api.schemas import (
    Notificar24hRequest,
    ReconfigurarConectoresRequest,
    SyncHibridaRequest,
    WorkerControlRequest,
    serializar_objeto,
)
from aquaterra.application.contenedor import Contenedor
from aquaterra.core.domain import Usuario

router = APIRouter(prefix="/api", tags=["sistema"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


def _estado_publico_seguro(contenedor: Contenedor, *, verificar_ollama: bool = False) -> dict[str, object]:
    estado = contenedor.sincronizacion.resumen_estado_conectividad(verificar_ollama=verificar_ollama)
    puertos = [{"device": dev, "descripcion": desc} for dev, desc in estado.get("puertos_serial", [])]
    try:
        fila_wal = contenedor.conexion.execute("PRAGMA journal_mode;").fetchone()
        sqlite_wal = bool(fila_wal and str(fila_wal[0]).lower() == "wal")
    except Exception:
        sqlite_wal = False
    return {
        **estado,
        "sqlite_wal": sqlite_wal,
        "ollama_disponible": estado.get("ia_ollama_disponible"),
        "puertos_serial": puertos,
        "webhook_configurado": bool(contenedor.sincronizacion.notificador._webhook_url),
        "telegram_configurado": bool(
            contenedor.sincronizacion.notificador._tg_token
            and contenedor.sincronizacion.notificador._tg_chat_id
        ),
        "version_app": __version__,
    }


@router.get("/sistema/estado")
def estado_sistema(
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
    verificar_ollama: bool = False,
) -> dict[str, object]:
    return _estado_publico_seguro(contenedor, verificar_ollama=verificar_ollama)


@router.post("/sistema/sync")
def sincronizar_ahora(
    body: SyncHibridaRequest,
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, object]:
    res = contenedor.sincronizacion.sincronizar_todo_hibrido(dias_clima=body.dias_clima)
    return {"resultado": serializar_objeto(res)}


@router.post("/sistema/notificar-24h")
def notificar_24h(
    body: Notificar24hRequest,
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, object]:
    mensaje, envios = contenedor.sincronizacion.notificar_pulso_24h_estacion(body.estacion_id)
    return {"mensaje": mensaje, "envios": serializar_objeto(envios)}


@router.post("/sistema/conectores")
def reconfigurar_conectores(
    body: ReconfigurarConectoresRequest,
    actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, object]:
    contenedor.sincronizacion.reconfigurar_conectores(
        actor,
        ubidots_token=body.ubidots_token,
        ia_proveedor=body.ia_proveedor,
        ia_gemini_key=body.ia_gemini_key,
        ia_gemini_modelo=body.ia_gemini_modelo,
        ia_ollama_url=body.ia_ollama_url,
        ia_ollama_modelo=body.ia_ollama_modelo,
        webhook_n8n_url=body.webhook_n8n_url,
        telegram_bot_token=body.telegram_bot_token,
        telegram_chat_id=body.telegram_chat_id,
        guardar_en_env_local=body.guardar_en_env_local,
    )
    return _estado_publico_seguro(contenedor, verificar_ollama=False)


@router.post("/sistema/ollama/precalentar")
def precalentar_ollama(
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, bool]:
    contenedor.copiloto.orquestador.precalentar_ollama_async()
    return {"ok": True}


@router.post("/sistema/worker")
def controlar_worker(
    body: WorkerControlRequest,
    actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, object]:
    exigir_admin(actor, "controlar el worker en segundo plano")
    if body.activo:
        contenedor.sincronizacion.iniciar_worker_segundo_plano(
            intervalo_segundos=body.intervalo_segundos,
            precalentar_ollama=body.precalentar_ollama,
        )
    else:
        contenedor.sincronizacion.detener_worker_segundo_plano()
    return {"worker_activo": contenedor.sincronizacion.worker_activo}


@router.get("/sistema/buscar")
def buscar_bitacora(
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
    q: str = "",
    limite: int = Query(default=25, ge=1, le=100),
) -> dict[str, object]:
    resultado = contenedor.copiloto.buscar_inteligente_bitacora(q, limite=limite)
    return {"resultado": serializar_objeto(resultado)}


@router.get("/exportar/xlsx")
def exportar_xlsx(
    estacion_id: int,
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
    ventana: str = "1h",
) -> Response:
    est = contenedor.radar.obtener_estacion(estacion_id)
    with tempfile.TemporaryDirectory() as tmpdir:
        destino = Path(tmpdir) / f"reporte_{est.codigo}.xlsx"
        contenedor.exportacion.exportar_xlsx_estacion(estacion_id, destino, ventana=ventana)
        contenido = destino.read_bytes()
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="reporte_{est.codigo}.xlsx"'},
    )


@router.get("/exportar/csv")
def exportar_csv(
    estacion_id: int,
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
    ventana: str = "1h",
) -> Response:
    est = contenedor.radar.obtener_estacion(estacion_id)
    with tempfile.TemporaryDirectory() as tmpdir:
        destino = Path(tmpdir) / f"serie_{est.codigo}.csv"
        contenedor.exportacion.exportar_csv_estacion(estacion_id, destino, ventana=ventana)
        contenido = destino.read_bytes()
    return Response(
        content=contenido,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="serie_{est.codigo}.csv"'},
    )
