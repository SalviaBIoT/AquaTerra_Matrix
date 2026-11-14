"""Pruebas de concurrencia SQLite multi-hilo (Fase 0 — v6.0).

Verifica que un mismo ``Contenedor`` (incluyendo bases ``:memory:`` y archivos WAL)
pueda ser consultado y mutado desde hilos secundarios sin arrojar
``SQLite objects created in a thread can only be used in that same thread``.
"""

from __future__ import annotations

import threading
from pathlib import Path

from aquaterra.application.contenedor import Contenedor, construir_contenedor
from aquaterra.config import Configuracion
from aquaterra.core.domain import TipoEstacion, TipoSuelo
from aquaterra.infrastructure.ia import ConfiguracionIA, OrquestadorIA


def test_concurrencia_multihilo_narrar_y_notificar(tmp_path: Path) -> None:
    cfg = Configuracion(ruta_db=tmp_path / "concurrente.db")
    contenedor: Contenedor = construir_contenedor(cfg, sembrar_legacy=True)
    try:
        contenedor.copiloto.orquestador = OrquestadorIA(ConfiguracionIA(proveedor_preferido="local_reglas"))
        estaciones = contenedor.sincronizacion.asegurar_estaciones_terrabit_base()
        est_id = estaciones[0].id
        res_gw = contenedor.sincronizacion.ingerir_linea_gateway_radio(
            "NRF24|terrabit-nodointi|suelo_a=42.5,temp_aire=24.1,vpd=1.1,voltaje=3.92"
        )
        assert res_gw is not None and res_gw.lecturas_insertadas >= 4

        errores: list[Exception] = []
        resultados_narrar: list[tuple[str, str]] = []
        lock_res = threading.Lock()

        def _worker_narrar() -> None:
            try:
                res = contenedor.copiloto.narrar_pulso_24h(est_id)
                with lock_res:
                    resultados_narrar.append(res)
            except Exception as exc:
                with lock_res:
                    errores.append(exc)

        def _worker_notificar() -> None:
            try:
                contenedor.sincronizacion.notificar_pulso_24h_estacion(est_id)
            except Exception as exc:
                with lock_res:
                    errores.append(exc)

        def _worker_radar() -> None:
            try:
                radar = contenedor.radar.listar_radar_priorizado()
                assert len(radar) >= 2
            except Exception as exc:
                with lock_res:
                    errores.append(exc)

        hilos = [
            threading.Thread(target=_worker_narrar),
            threading.Thread(target=_worker_notificar),
            threading.Thread(target=_worker_radar),
            threading.Thread(target=_worker_narrar),
        ]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join(timeout=10.0)

        assert not errores, f"Fallos de concurrencia SQLite: {errores}"
        assert len(resultados_narrar) == 2
        assert all(msg and prov for msg, prov in resultados_narrar)
    finally:
        contenedor.cerrar()


def test_concurrencia_multihilo_en_memoria_escrituras_simultaneas(db, admin) -> None:
    """Incluso con ``:memory:``, múltiples hilos pueden escribir y leer sin corrupción transaccional."""
    contenedor = Contenedor(config=Configuracion(ruta_db=Path(":memory:")), conexion=db)
    est = contenedor.sincronizacion.registrar_estacion(
        admin,
        codigo="nodo-concurrente",
        nombre="Nodo Concurrente",
        tipo=TipoEstacion.TERRABIT_INTI,
    )

    errores: list[Exception] = []

    def _crear_parcela(idx: int) -> None:
        try:
            contenedor.parcelas.crear(
                admin,
                nombre=f"Parcela Hilo {idx}",
                cultivo="Maiz",
                area=100.0 + idx,
                humedad=50.0,
                suelo=TipoSuelo.FRANCO,
                riego_auto=True,
                estacion_id=est.id,
            )
        except Exception as exc:
            errores.append(exc)

    hilos = [threading.Thread(target=_crear_parcela, args=(i,)) for i in range(8)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(timeout=10.0)

    assert not errores, f"Errores en escrituras concurrentes: {errores}"
    nombres = {p.nombre for p in contenedor.parcelas.listar()}
    for i in range(8):
        assert f"Parcela Hilo {i}" in nombres
