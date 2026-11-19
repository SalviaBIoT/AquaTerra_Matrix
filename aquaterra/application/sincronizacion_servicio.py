"""Servicio de Sincronización Activa (Ubidots REST, Open-Meteo, Gateway nRF24L01+/LoRa y Notificaciones).

Orquesta en el Sprint `v4.2.0`:
1. Registro automático de las estaciones base reales del Ecosistema SalviaBIoT en Ubidots
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
import os
import sqlite3
import threading
import urllib.error
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from aquaterra.application.copiloto_servicio import CalibrationCopilotService
from aquaterra.application.radar_servicio import StationDiscoveryService
from aquaterra.config import guardar_env_local
from aquaterra.core import tiempo
from aquaterra.core.domain import (
    ErrorPermiso,
    ErrorValidacion,
    Estacion,
    PuntoPronosticoClima,
    TipoEstacion,
    Usuario,
)
from aquaterra.infrastructure.clima import (
    ALTITUD_UTP_PEREIRA_M,
    LATITUD_UTP_PEREIRA,
    LONGITUD_UTP_PEREIRA,
    ClienteOpenMeteo,
    ResultadoSyncClima,
)
from aquaterra.infrastructure.db import abrir_conexion
from aquaterra.infrastructure.db.repositorios import (
    RepositorioAuditoria,
    RepositorioEstaciones,
    RepositorioLecturas,
    RepositorioPronosticoClima,
)
from aquaterra.infrastructure.ia import ClienteOllamaLocal, ConfiguracionIA, OrquestadorIA
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


@dataclass(frozen=True, slots=True)
class ResultadoSyncHibrida:
    """Resultado consolidado de un ciclo híbrido (Ubidots + Open-Meteo) tolerante a modo offline."""

    online: bool
    ubidots: tuple[ResultadoSyncUbidots, ...]
    clima: tuple[ResultadoSyncClima, ...]
    aviso: str | None = None
    ts_iso: str = ""


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
        copiloto: CalibrationCopilotService | None = None,
    ) -> None:
        self._db = conexion
        self._ruta_db = ruta_db
        self._estaciones = RepositorioEstaciones(conexion)
        self._lecturas = RepositorioLecturas(conexion)
        self._clima_repo = RepositorioPronosticoClima(conexion)
        self._auditoria = RepositorioAuditoria(conexion)
        self._radar = StationDiscoveryService(conexion)
        self._copiloto = copiloto or CalibrationCopilotService(conexion)
        self.ubidots = cliente_ubidots or ClienteUbidotsREST()
        self.clima = cliente_clima or ClienteOpenMeteo()
        self.notificador = despachador_notificaciones or DespachadorNotificaciones()

        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self.ultima_sync_iso: str | None = None
        self.ultimo_estado_online: bool | None = None

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

    @property
    def worker_activo(self) -> bool:
        return self._worker_thread is not None and self._worker_thread.is_alive()

    def sincronizar_todo_hibrido(self, *, dias_clima: int = 2) -> ResultadoSyncHibrida:
        """Ejecuta sincronización Ubidots + Open-Meteo degradando limpiamente si no hay red."""
        res_ubidots: list[ResultadoSyncUbidots] = []
        res_clima: list[ResultadoSyncClima] = []
        errores_red: list[str] = []

        if self.ubidots.tiene_token:
            try:
                res_ubidots = self.sincronizar_todas_ubidots(page_size=50)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                errores_red.append(f"Ubidots offline: {exc}")

        try:
            res_clima = self.sincronizar_todas_clima(dias=dias_clima)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            errores_red.append(f"Open-Meteo offline: {exc}")

        online = len(errores_red) == 0
        ahora_txt = tiempo.ahora_iso()
        self.ultimo_estado_online = online
        if online:
            self.ultima_sync_iso = ahora_txt

        return ResultadoSyncHibrida(
            online=online,
            ubidots=tuple(res_ubidots),
            clima=tuple(res_clima),
            aviso="; ".join(errores_red) if errores_red else None,
            ts_iso=ahora_txt,
        )

    def listar_pronostico_estacion(
        self, estacion_id: int, *, horas: int = 48, auto_descargar: bool = False
    ) -> list[PuntoPronosticoClima]:
        """Devuelve el pronóstico horario en caché local (`pronostico_clima_cache`)."""
        ahora_ep = tiempo.a_epoch(tiempo.ahora()) - 3600
        puntos = self._clima_repo.ventana(
            estacion_id,
            desde_epoch=ahora_ep,
            hasta_epoch=ahora_ep + max(1, horas) * 3600,
        )
        if not puntos and auto_descargar:
            try:
                estacion = self._estaciones.obtener(estacion_id)
                _, _, descargados = self.clima.descargar_pronostico_estacion(estacion, dias=3)
                if descargados:
                    with self._db:
                        self._clima_repo.guardar_lote(descargados)
                    puntos = self._clima_repo.ventana(
                        estacion_id,
                        desde_epoch=ahora_ep,
                        hasta_epoch=ahora_ep + max(1, horas) * 3600,
                    )
            except Exception:
                pass
        return puntos

    def registrar_estacion(
        self,
        actor: Usuario,
        *,
        codigo: str,
        nombre: str,
        tipo: TipoEstacion,
        latitud: float | None = None,
        longitud: float | None = None,
        altitud_m: float | None = None,
    ) -> Estacion:
        """Registra una nueva estación IoT física con coordenadas GPS opcionales."""
        if not actor.es_admin:
            raise ErrorPermiso("registrar estaciones IoT")
        cod = (codigo or "").strip().lower()
        nom = (nombre or "").strip()
        errores: list[str] = []
        if len(cod) < 3:
            errores.append("El código externo del nodo debe tener al menos 3 caracteres.")
        if len(nom) < 3:
            errores.append("El nombre de la estación debe tener al menos 3 caracteres.")
        if self._estaciones.por_codigo(cod) is not None:
            errores.append(f"Ya existe una estación con código '{cod}'.")
        if errores:
            raise ErrorValidacion(errores)

        with self._db:
            est = self._estaciones.crear(
                cod,
                nom,
                tipo,
                latitud=latitud if latitud is not None else LATITUD_UTP_PEREIRA,
                longitud=longitud if longitud is not None else LONGITUD_UTP_PEREIRA,
                altitud_m=altitud_m if altitud_m is not None else ALTITUD_UTP_PEREIRA_M,
            )
            self._auditoria.registrar(
                "registrar_estacion", "estacion", est.id, actor.id, {"codigo": est.codigo, "tipo": est.tipo.value}
            )
        return est

    def reparar_rtc_estacion(
        self,
        actor: Usuario,
        estacion_id: int,
        *,
        ts_fin_real_epoch: int | None = None,
    ) -> int:
        """Corrige timestamps RTC corruptos (ej. 1970/2020) de una estación en SQLite."""
        if not actor.es_admin:
            raise ErrorPermiso("reparar timestamps RTC")
        self._estaciones.obtener(estacion_id)
        fin = ts_fin_real_epoch or tiempo.a_epoch(tiempo.ahora())
        with self._db:
            reparadas = self._lecturas.reparar_timestamps_rtc(estacion_id, ts_fin_real_epoch=fin)
            self._auditoria.registrar(
                "reparar_rtc", "estacion", estacion_id, actor.id, {"reparadas": reparadas, "fin_epoch": fin}
            )
        return reparadas

    @staticmethod
    def puertos_serial_disponibles() -> list[tuple[str, str]]:
        """Descubre puertos COM/USB disponibles para el receptor `nRF24L01+ PA+LNA` / `LoRa`."""
        try:
            from serial.tools import list_ports
        except ImportError:
            return []
        return [
            (p.device, f"{p.device} · {p.description or 'Puerto Serial'}")
            for p in sorted(list_ports.comports(), key=lambda x: x.device)
        ]

    def leer_puerto_serial_lote(
        self,
        puerto: str,
        *,
        baudrate: int = 115200,
        max_lineas: int = 25,
        timeout_s: float = 1.5,
    ) -> list[ResultadoIngestaGatewayRadio]:
        """Lee un lote corto de tramas reales desde el puerto USB-Serial del gateway radio."""
        try:
            import serial
        except ImportError as exc:
            raise ErrorValidacion("La librería pyserial no está instalada en este entorno.") from exc

        if not (puerto or "").strip():
            raise ErrorValidacion("Seleccione un puerto serial válido (ej. COM5).")

        lineas: list[str] = []
        try:
            with serial.Serial(puerto.strip(), baudrate=baudrate, timeout=timeout_s) as ser:
                for _ in range(max_lineas):
                    cruda = ser.readline()
                    if not cruda:
                        break
                    texto = cruda.decode("utf-8", errors="ignore").strip()
                    if texto:
                        lineas.append(texto)
        except OSError as exc:
            raise ErrorValidacion(f"No fue posible abrir el puerto {puerto}: {exc}") from exc

        return self.ingerir_lote_lineas_gateway(lineas)

    def reconfigurar_conectores(
        self,
        actor: Usuario,
        *,
        ubidots_token: str | None = None,
        ia_proveedor: str | None = None,
        ia_gemini_key: str | None = None,
        ia_gemini_modelo: str | None = None,
        ia_ollama_url: str | None = None,
        ia_ollama_modelo: str | None = None,
        webhook_n8n_url: str | None = None,
        telegram_bot_token: str | None = None,
        telegram_chat_id: str | None = None,
        guardar_en_env_local: bool = False,
        ruta_env: Path | None = None,
    ) -> dict[str, object]:
        """Actualiza credenciales/conectores en caliente para clientes finales sin editar archivos."""
        if not actor.es_admin:
            raise ErrorPermiso("reconfigurar conectores externos")

        env_actualizados: dict[str, str] = {}

        if ubidots_token is not None:
            tok = ubidots_token.strip()
            self.ubidots = ClienteUbidotsREST(token=tok)
            if tok:
                os.environ["UBIDOTS_TOKEN"] = tok
                env_actualizados["UBIDOTS_TOKEN"] = tok

        cfg_actual = self._copiloto.orquestador.config
        nuevo_prov = (ia_proveedor or cfg_actual.proveedor_preferido).strip().lower()
        nueva_gemini_key = cfg_actual.gemini_api_key if ia_gemini_key is None else (ia_gemini_key.strip() or None)
        nuevo_gemini_mod = (ia_gemini_modelo or cfg_actual.gemini_modelo).strip()
        nueva_ollama_url = (ia_ollama_url or cfg_actual.ollama_base_url).strip().rstrip("/")
        nuevo_ollama_mod = (ia_ollama_modelo or cfg_actual.ollama_modelo).strip()

        nueva_cfg_ia = ConfiguracionIA(
            proveedor_preferido=nuevo_prov,
            gemini_api_key=nueva_gemini_key,
            gemini_modelo=nuevo_gemini_mod,
            ollama_base_url=nueva_ollama_url,
            ollama_modelo=nuevo_ollama_mod,
            timeout_segundos=cfg_actual.timeout_segundos,
            ollama_timeout_segundos=cfg_actual.ollama_timeout_segundos,
        )
        self._copiloto.orquestador = OrquestadorIA(nueva_cfg_ia)
        os.environ["AQUATERRA_IA_PROVEEDOR"] = nuevo_prov
        os.environ["AQUATERRA_OLLAMA_URL"] = nueva_ollama_url
        os.environ["AQUATERRA_OLLAMA_MODEL"] = nuevo_ollama_mod
        os.environ["AQUATERRA_GEMINI_MODEL"] = nuevo_gemini_mod
        env_actualizados["AQUATERRA_IA_PROVEEDOR"] = nuevo_prov
        env_actualizados["AQUATERRA_OLLAMA_URL"] = nueva_ollama_url
        env_actualizados["AQUATERRA_OLLAMA_MODEL"] = nuevo_ollama_mod
        env_actualizados["AQUATERRA_GEMINI_MODEL"] = nuevo_gemini_mod
        if nueva_gemini_key:
            os.environ["GEMINI_API_KEY"] = nueva_gemini_key
            env_actualizados["GEMINI_API_KEY"] = nueva_gemini_key

        wh = self.notificador._webhook_url if webhook_n8n_url is None else webhook_n8n_url.strip()
        tg_t = self.notificador._tg_token if telegram_bot_token is None else telegram_bot_token.strip()
        tg_c = self.notificador._tg_chat_id if telegram_chat_id is None else telegram_chat_id.strip()
        self.notificador = DespachadorNotificaciones(
            webhook_url=wh, telegram_bot_token=tg_t, telegram_chat_id=tg_c
        )
        if wh:
            os.environ["AQUATERRA_WEBHOOK_URL"] = wh
            env_actualizados["AQUATERRA_WEBHOOK_URL"] = wh
        if tg_t:
            os.environ["AQUATERRA_TELEGRAM_BOT_TOKEN"] = tg_t
            env_actualizados["AQUATERRA_TELEGRAM_BOT_TOKEN"] = tg_t
        if tg_c:
            os.environ["AQUATERRA_TELEGRAM_CHAT_ID"] = tg_c
            env_actualizados["AQUATERRA_TELEGRAM_CHAT_ID"] = tg_c

        if guardar_en_env_local:
            guardar_env_local(env_actualizados, ruta_env=ruta_env)

        with self._db:
            self._auditoria.registrar(
                "reconfigurar_conectores",
                "sistema",
                None,
                actor.id,
                {"ia_proveedor": nuevo_prov, "ubidots": self.ubidots.tiene_token, "guardado_env": guardar_en_env_local},
            )
        return self.resumen_estado_conectividad()

    def resumen_estado_conectividad(self, *, verificar_ollama: bool = False) -> dict[str, object]:
        """Resumen de estado para píldoras y barra inferior del App Shell v5.0."""
        cfg_ia = self._copiloto.orquestador.config
        ollama_ok: bool | None = None
        if verificar_ollama:
            ollama_ok = ClienteOllamaLocal(
                base_url=cfg_ia.ollama_base_url,
                modelo=cfg_ia.ollama_modelo,
                timeout_segundos=cfg_ia.ollama_timeout_segundos,
            ).esta_disponible(timeout_ping=0.5)

        estaciones = self._estaciones.listar()
        clima_pts = 0
        if estaciones:
            clima_pts = len(self.listar_pronostico_estacion(estaciones[0].id, horas=48))

        return {
            "ubidots_configurado": self.ubidots.tiene_token,
            "ultimo_ubidots_epoch": self._lecturas.ultimo_epoch_por_fuente("ubidots"),
            "clima_puntos_cache": clima_pts,
            "ia_proveedor": cfg_ia.proveedor_preferido,
            "ia_ollama_modelo": cfg_ia.ollama_modelo,
            "ia_ollama_url": cfg_ia.ollama_base_url,
            "ia_gemini_modelo": cfg_ia.gemini_modelo,
            "ia_gemini_configurado": bool(cfg_ia.gemini_api_key),
            "ia_ollama_disponible": ollama_ok,
            "canales_notificacion": self.notificador.canales_configurados,
            "puertos_serial": self.puertos_serial_disponibles(),
            "worker_activo": self.worker_activo,
            "ultima_sync_iso": self.ultima_sync_iso,
            "ultimo_estado_online": self.ultimo_estado_online,
            "lecturas_totales": self._lecturas.contar(),
        }
