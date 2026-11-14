"""Router de Riego, Recomendación Proactiva, 5 Candados, Salud de Bomba e Incidencia."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from aquaterra.api.deps import get_contenedor, get_usuario_actual
from aquaterra.api.schemas import (
    AplicarRiegoRequest,
    ProgramarRiegoRequest,
    RegistrarIncidenciaRequest,
    serializar_objeto,
)
from aquaterra.application.contenedor import Contenedor
from aquaterra.core import tiempo
from aquaterra.core.domain import ErrorValidacion, ModoVerificacionRiego, Usuario

router = APIRouter(prefix="/api", tags=["riego"])


@router.get("/parcelas/{parcela_id}/riego/contexto")
def contexto_riego_parcela(
    parcela_id: int,
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
    umbral_pct: float | None = Query(default=None, ge=0.0, le=100.0),
) -> dict[str, object]:
    parcela = contenedor.parcelas.obtener(parcela_id)
    recomendacion = contenedor.control.recomendar_riego_parcela(
        parcela_id, umbral_disparo_pct=umbral_pct
    )
    salud = contenedor.control.ultimo_salud_actuador(parcela_id)
    historial = contenedor.control.listar_riegos_parcela(parcela_id)
    programados = contenedor.control.listar_riegos_programados(parcela_id)
    incidencias = contenedor.control.listar_incidencias_parcela(parcela_id)
    return {
        "parcela": serializar_objeto(parcela),
        "recomendacion": serializar_objeto(recomendacion),
        "salud_bomba": serializar_objeto(salud),
        "historial": serializar_objeto(list(reversed(historial))),
        "programados": serializar_objeto(programados),
        "incidencias": serializar_objeto(list(reversed(incidencias))),
        "modos_verificacion": [m.value for m in ModoVerificacionRiego],
    }


@router.post("/parcelas/{parcela_id}/riego/aplicar")
def aplicar_riego(
    parcela_id: int,
    body: AplicarRiegoRequest,
    actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, object]:
    try:
        fecha = date.fromisoformat(body.fecha_iso.strip())
    except ValueError as exc:
        raise ErrorValidacion("La fecha debe tener formato ISO YYYY-MM-DD.") from exc

    resultado = contenedor.riego.aplicar_riego(
        actor,
        parcela_id=parcela_id,
        umbral_pct=body.umbral_pct,
        litros=body.litros,
        fecha=fecha,
        hora=body.hora,
    )
    return {"resultado": serializar_objeto(resultado)}


@router.post("/parcelas/{parcela_id}/riego/programar")
def programar_riego(
    parcela_id: int,
    body: ProgramarRiegoRequest,
    actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, object]:
    try:
        modo = ModoVerificacionRiego(body.modo_verificacion)
    except ValueError as exc:
        raise ErrorValidacion(f"Modo de verificación inválido: '{body.modo_verificacion}'.") from exc

    if body.ts_programado_epoch is not None:
        ts_epoch = int(body.ts_programado_epoch)
    elif body.fecha_iso:
        try:
            fecha = date.fromisoformat(body.fecha_iso.strip())
            momento = tiempo.combinar(fecha, tiempo.parsear_hora(body.hora))
            ts_epoch = tiempo.a_epoch(momento)
        except ValueError as exc:
            raise ErrorValidacion(str(exc)) from exc
    else:
        ts_epoch = tiempo.a_epoch(tiempo.ahora())

    programado, veredicto = contenedor.control.programar_riego_validado(
        actor,
        parcela_id=parcela_id,
        ts_programado_epoch=ts_epoch,
        litros_solicitados=body.litros_solicitados,
        apertura_solicitada_pct=body.apertura_solicitada_pct,
        origen=body.origen,
        modo_verificacion=modo,
        mantenimiento_confirmado=body.mantenimiento_confirmado,
    )
    return {
        "programado": serializar_objeto(programado),
        "veredicto": serializar_objeto(veredicto),
    }


@router.post("/riego/incidencia")
def registrar_incidencia(
    body: RegistrarIncidenciaRequest,
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, object]:
    try:
        modo = ModoVerificacionRiego(body.modo_verificacion)
    except ValueError as exc:
        raise ErrorValidacion(f"Modo de verificación inválido: '{body.modo_verificacion}'.") from exc

    salud, incidencia = contenedor.control.registrar_verificacion_e_incidencia(
        evento_riego_id=body.evento_riego_id,
        humedad_a_antes=body.humedad_a_antes,
        humedad_a_despues=body.humedad_a_despues,
        humedad_b_antes=body.humedad_b_antes,
        humedad_b_despues=body.humedad_b_despues,
        modo_verificacion=modo,
        apertura_max_pct=body.apertura_max_pct,
        vibracion_rms_g=body.vibracion_rms_g,
        vibracion_freq_hz=body.vibracion_freq_hz,
        corriente_a=body.corriente_a,
        caudal_lpm=body.caudal_lpm,
    )
    return {
        "salud_actuador": serializar_objeto(salud),
        "incidencia": serializar_objeto(incidencia),
    }
