"""Router de Hardware de Campo: Gateway USB-Serial nRF24L01+/LoRa y Escáner MicroSD."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends

from aquaterra.api.deps import get_contenedor, get_usuario_actual
from aquaterra.api.schemas import (
    EscanearMicroSDRequest,
    ImportarMicroSDRequest,
    IngerirTramasRequest,
    LeerSerialRequest,
    serializar_objeto,
)
from aquaterra.application.contenedor import Contenedor
from aquaterra.core.domain import ErrorValidacion, Usuario

router = APIRouter(prefix="/api", tags=["hardware"])


@router.get("/hardware/puertos")
def listar_puertos_serial(
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, object]:
    puertos = [
        {"device": dev, "descripcion": desc}
        for dev, desc in contenedor.sincronizacion.puertos_serial_disponibles()
    ]
    return {"puertos": puertos}


@router.post("/hardware/serial/leer")
def leer_serial(
    body: LeerSerialRequest,
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, object]:
    resultados = contenedor.sincronizacion.leer_puerto_serial_lote(
        body.puerto,
        baudrate=body.baudrate,
        max_lineas=body.max_lineas,
    )
    return {
        "resultados": serializar_objeto(resultados),
        "total_tramas": len(resultados),
        "total_lecturas_insertadas": sum(r.lecturas_insertadas for r in resultados),
    }


@router.post("/hardware/tramas")
def ingerir_tramas_radio(
    body: IngerirTramasRequest,
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, object]:
    lineas = [ln.strip() for ln in body.lineas if ln.strip()]
    if not lineas:
        raise ErrorValidacion("Debe enviar al menos una trama de texto válida para decodificar.")
    resultados = contenedor.sincronizacion.ingerir_lote_lineas_gateway(
        lineas, ts_epoch_defecto=body.ts_epoch_defecto
    )
    return {
        "resultados": serializar_objeto(resultados),
        "total_tramas": len(resultados),
        "total_lecturas_recibidas": sum(r.lecturas_recibidas for r in resultados),
        "total_lecturas_insertadas": sum(r.lecturas_insertadas for r in resultados),
    }


@router.post("/hardware/microsd/escanear")
def escanear_microsd(
    body: EscanearMicroSDRequest,
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, object]:
    unidades = [f"{letra}:\\" for letra in "DEFGH" if Path(f"{letra}:\\").exists()]
    if body.directorios:
        rutas = [Path(d.strip()) for d in body.directorios if d.strip()]
    else:
        rutas = [Path(u) for u in unidades]
        if not rutas:
            rutas = [Path.cwd()]

    archivos = contenedor.radar.detectar_archivos_estacion(rutas)
    return {
        "unidades_disponibles": unidades,
        "rutas_escaneadas": [str(r) for r in rutas],
        "archivos": [
            {
                "ruta_archivo": str(a.ruta_archivo),
                "nombre": a.ruta_archivo.name,
                "tipo_estacion_inferido": a.tipo_estacion_inferido.value,
                "tamano_bytes": a.tamano_bytes,
            }
            for a in archivos
        ],
    }


@router.post("/hardware/microsd/importar")
def importar_microsd(
    body: ImportarMicroSDRequest,
    _actor: Annotated[Usuario, Depends(get_usuario_actual)],
    contenedor: Annotated[Contenedor, Depends(get_contenedor)],
) -> dict[str, object]:
    ruta = Path(body.ruta_archivo)
    if not ruta.exists() or not ruta.is_file():
        raise ErrorValidacion(f"El archivo '{body.ruta_archivo}' no existe en disco.")
    res = contenedor.radar.importar_archivo_estacion(body.estacion_id, ruta)
    return {"resultado": serializar_objeto(res)}
