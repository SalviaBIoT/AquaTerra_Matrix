"""Servicio de Sincronización Activa (Ubidots REST, Open-Meteo, Gateway nRF24L01+/LoRa y Notificaciones).

Orquesta en el Sprint `v4.2.0`:
1. Registro automático de las estaciones reales del Ecosistema TerraBit en Ubidots
   (`terrabit-nodointi` e `inbeersa-nodo01` en UTP Pereira `4.7905° N, -75.6904° O`).
2. Descarga incremental desde Ubidots REST API usando `ultimo_epoch(estacion_id)`
   como marca de agua y actualización automática de `parcelas.humedad_pct`.
3. Actualización del caché meteorológico horario desde Open-Meteo (`pronostico_clima_cache`).
4. Ingesta de tramas recibidas por antena (`nRF24L01+ PA+LNA` 2.4 GHz o `LoRa` 915 MHz)
   desde un ESP32 Gateway conectado por USB-Serial.
5. Despacho de reportes ejecutivos 24h hacia Webhook `n8n` (WhatsApp/Notion) o
   Telegram Bot directo.
6. Worker asíncrono en segundo plano (`daemon`) con conexión SQLite WAL propia.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from aquaterra.application.copiloto_servicio import CalibrationCopilotService
from aquaterra.application.radar_servicio import StationDiscoveryService
from aquaterra.core.domain import Estacion, TipoEstacion
from aquaterra.infrastructure.clima import (
    ALTITUD_UTP_PEREIRA_M,
    LATITUD_UTP_PEREIRA,
    LONGITUD_UTP_PEREIRA,
    ClienteOpenMeteo,
    ResultadoSyncClima,
)
from aquaterra.infrastructure.db import abrir_conexion
from aquaterra.infrastructure.db.repositorios import (
    RepositorioEstaciones,
    RepositorioLecturas,
    RepositorioPronosticoClima,
)
from aquaterra.infrastructure.iot_ingest.serial_gateway import (
    TramaGatewayDecodificada,
    convertir_trama_a_lecturas,
    decodificar_linea_gateway,
)
from aquaterra.infrastructure.iot_ingest.ubidots_client import (
    ClienteUbidotsREST,
    ResultadoSyncUbidots,
)
from aquaterra.infrastructure.notificaciones import (
    DespachadorNotificaciones,
    ResultadoEnvioNotificacion,
)

log = logging.getLogger(__name__)

ESTACIONES_OFICIALES_TERRABIT: tuple[tuple[str, str, TipoEstacion], ...] = (
    ("terrabit-nodointi", "TerraBit-NodoINTI", TipoEstacion.TERRABIT_INTI),
    ("inbeersa-nodo01", "inbeersa-nodo01", TipoEstacion.INBEERSA),
)


@dataclass(frozen=True, slots=True)
class ResultadoIngestaGatewayRadio:
    """Resumen de ingesta de una trama recibida por radio (`nRF24L01+` / `LoRa`)."""

    estacion_id: int
    device_label: str
    protocolo: str
    lecturas_recibidas: int
    lecturas_insertadas: int


class ActiveSyncAndGatewayService:
    """Caso de uso maestro para conectores de red, antena serial y notificaciones."""

    def __init__(
        self,
        conexion: sqlite3.Connection,
        *,
        ruta_db: Path | None = None,
        cliente_ubidots: ClienteUbidotsREST | None = None,
        cliente_clima: ClienteOpenMeteo | None = None,
        despachador_notificaciones: DespachadorNotificaciones | None = None,
    ) -> None:
        self._db = conexion
        self._ruta_db = ruta_db
        self._estaciones = RepositorioEstaciones(conexion)
        self._lecturas = RepositorioLecturas(conexion)
        self._clima_repo = RepositorioPronosticoClima(conexion)
        self._radar = StationDiscoveryService(conexion)
        self._copiloto = CalibrationCopilotService(conexion)
        self.ubidots = cliente_ubidots or ClienteUbidotsREST()
        self.clima = cliente_clima or ClienteOpenMeteo()
        self.notificador = despachador_notificaciones or DespachadorNotificaciones()

        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None

    def asegurar_estaciones_terrabit_base(self) -> list[Estacion]:
        """Garantiza que `terrabit-nodointi` e `inbeersa-nodo01` existan con coordenadas UTP Pereira."""
        registradas: list[Estacion] = []
        with self._db:
            for codigo, nombre, tipo in ESTACIONES_OFICIALES_TERRABIT:
                existente = self._estaciones.por_codigo(codigo)
                if existente is None:
                    existente = self._estaciones.crear(
                        codigo,
                        nombre,
                        tipo,
                        latitud=LATITUD_UTP_PEREIRA,
                        longitud=LONGITUD_UTP_PEREIRA,
                        altitud_m=ALTITUD_UTP_PEREIRA_M,
                    )
                registradas.append(existente)
        return registradas

    def sincronizar_ubidots_estacion(
        self,
        estacion_id: int,
        *,
        page_size: int = 100,
        forzar_historico: bool = False,
    ) -> ResultadoSyncUbidots:
        """Descarga incrementalmente desde Ubidots solo los puntos posteriores a `ultimo_epoch`."""
        estacion = self._estaciones.obtener(estacion_id)
        marca_agua = None if forzar_historico else self._lecturas.ultimo_epoch(estacion.id)

        lecturas, errores = self.ubidots.descargar_lecturas_estacion(
            estacion,
            desde_epoch=marca_agua,
            page_size=page_size,
        )
        with self._db:
            insertadas = self._lecturas.insertar_lote(lecturas)

        if insertadas > 0:
            self._radar.sincronizar_humedad_parcelas(estacion.id)

        return ResultadoSyncUbidots(
            estacion_id=estacion.id,
            device_label=estacion.codigo,
            variables_consultadas=len({lec.variable for lec in lecturas}),
            lecturas_descargadas=len(lecturas),
            lecturas_nuevas_insertadas=insertadas,
            desde_epoch=marca_agua,
            errores_variables=errores,
        )

    def sincronizar_todas_ubidots(self, *, page_size: int = 100) -> list[ResultadoSyncUbidots]:
        """Sincroniza incrementalmente todas las estaciones activas desde Ubidots."""
        resultados: list[ResultadoSyncUbidots] = []
        for est in self._estaciones.listar():
            if not est.activa:
                continue
            resultados.append(self.sincronizar_ubidots_estacion(est.id, page_size=page_size))
        return resultados

    def sincronizar_clima_estacion(
        self,
        estacion_id: int,
        *,
        dias: int = 3,
    ) -> ResultadoSyncClima:
        """Descarga el pronóstico horario de Open-Meteo y actualiza `pronostico_clima_cache`."""
        estacion = self._estaciones.obtener(estacion_id)
        lat, lon, puntos = self.clima.descargar_pronostico_estacion(estacion, dias=dias)
        with self._db:
            guardados = self._clima_repo.guardar_lote(puntos)
        return ResultadoSyncClima(
            estacion_id=estacion.id,
            latitud=lat,
            longitud=lon,
            puntos_descargados=len(puntos),
            puntos_guardados=guardados,
        )

    def sincronizar_todas_clima(self, *, dias: int = 3) -> list[ResultadoSyncClima]:
        resultados: list[ResultadoSyncClima] = []
        for est in self._estaciones.listar():
            if not est.activa:
                continue
            resultados.append(self.sincronizar_clima_estacion(est.id, dias=dias))
        return resultados

    def ingerir_linea_gateway_radio(
        self,
        linea: str,
        *,
        ts_epoch_defecto: int | None = None,
        tipo_por_defecto: TipoEstacion = TipoEstacion.TERRABIT_INTI,
    ) -> ResultadoIngestaGatewayRadio | None:
        """Procesa una línea recibida del Gateway USB-Serial (`nRF24L01+ PA+LNA` o `LoRa`)."""
        trama: TramaGatewayDecodificada | None = decodificar_linea_gateway(
            linea, ts_epoch_defecto=ts_epoch_defecto
        )
        if trama is None:
            return None

        estacion = self._estaciones.por_codigo(trama.device_label)
        if estacion is None:
            tipo_inferido = (
                TipoEstacion.INBEERSA
                if "inbeersa" in trama.device_label.lower()
                or "temperatura_interna" in trama.metricas
                else tipo_por_defecto
            )
            with self._db:
                estacion = self._estaciones.crear(
                    trama.device_label,
                    trama.device_label,
                    tipo_inferido,
                    latitud=LATITUD_UTP_PEREIRA,
                    longitud=LONGITUD_UTP_PEREIRA,
                    altitud_m=ALTITUD_UTP_PEREIRA_M,
                )

        lecturas = convertir_trama_a_lecturas(trama, estacion_id=estacion.id)
        with self._db:
            insertadas = self._lecturas.insertar_lote(lecturas)

        if insertadas > 0:
            self._radar.sincronizar_humedad_parcelas(estacion.id)

        return ResultadoIngestaGatewayRadio(
            estacion_id=estacion.id,
            device_label=estacion.codigo,
            protocolo=trama.protocolo,
            lecturas_recibidas=len(lecturas),
            lecturas_insertadas=insertadas,
        )

    def ingerir_lote_lineas_gateway(
        self,
        lineas: Sequence[str],
        *,
        ts_epoch_defecto: int | None = None,
    ) -> list[ResultadoIngestaGatewayRadio]:
        resultados: list[ResultadoIngestaGatewayRadio] = []
        for ln in lineas:
            res = self.ingerir_linea_gateway_radio(ln, ts_epoch_defecto=ts_epoch_defecto)
            if res is not None:
                resultados.append(res)
        return resultados

    def notificar_pulso_24h_estacion(
        self,
        estacion_id: int,
        *,
        hasta_epoch: int | None = None,
    ) -> tuple[str, list[ResultadoEnvioNotificacion]]:
        """Genera la narrativa ejecutiva 24h y la envía a Webhook `n8n` / Telegram si están activos."""
        estacion = self._estaciones.obtener(estacion_id)
        mensaje, proveedor_ia = self._copiloto.narrar_pulso_24h(
            estacion.id, hasta_epoch=hasta_epoch
        )
        envios = self.notificador.despachar_todos(
            evento="pulso_24h",
            mensaje_ejecutivo=mensaje,
            metadatos={
                "estacion_id": estacion.id,
                "codigo_estacion": estacion.codigo,
                "nombre_estacion": estacion.nombre,
                "tipo_estacion": estacion.tipo.value,
                "proveedor_ia": proveedor_ia,
            },
        )
        return mensaje, envios

    def iniciar_worker_segundo_plano(
        self,
        *,
        intervalo_segundos: float = 900.0,
        precalentar_ollama: bool = True,
    ) -> threading.Thread:
        """Inicia el hilo daemon de sincronización periódica y precalentamiento de Ollama."""
        if precalentar_ollama:
            self._copiloto.orquestador.precalentar_ollama_async()

        if self._worker_thread is not None and self._worker_thread.is_alive():
            return self._worker_thread

        self._stop_event.clear()

        def _bucle() -> None:
            while not self._stop_event.is_set():
                if self._ruta_db is not None:
                    try:
                        conn_bg = abrir_conexion(self._ruta_db)
                        try:
                            srv_bg = ActiveSyncAndGatewayService(
                                conn_bg,
                                cliente_ubidots=self.ubidots,
                                cliente_clima=self.clima,
                                despachador_notificaciones=self.notificador,
                            )
                            if self.ubidots.tiene_token:
                                srv_bg.sincronizar_todas_ubidots(page_size=50)
                            srv_bg.sincronizar_todas_clima(dias=2)
                        finally:
                            conn_bg.close()
                    except Exception as exc:
                        log.warning("Ciclo de worker de sincronización con aviso: %s", exc)
                self._stop_event.wait(intervalo_segundos)

        self._worker_thread = threading.Thread(
            target=_bucle,
            name="AquaTerra-BackgroundSyncWorker",
            daemon=True,
        )
        self._worker_thread.start()
        return self._worker_thread

    def detener_worker_segundo_plano(self) -> None:
        self._stop_event.set()
