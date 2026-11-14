"""Servicio de Radar de Estaciones, Búsqueda Multicriterio y Auto-Detección de Orígenes (Fase B4 — Módulo 0).

Responsabilidades:
1. Priorizar estaciones según su severidad (``CRITICO`` -> ``ATENCION`` -> ``OPTIMO`` -> ``SIN_DATOS``).
2. Filtrar estaciones por código, nombre, tipo de ecosistema o parcela vinculada.
3. Detectar archivos de telemetría en directorios/MicroSD (``data.csv``, ``data.json``,
   ``MUNDONUEVO.csv``, ``buffer_sigatoka.json``) e inferir su ``TipoEstacion``.
4. Importar en un solo paso un archivo detectado hacia su estación en SQLite.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from aquaterra.application.pulso_servicio import NodePulseService
from aquaterra.core.analitica import NivelSeveridadPulso
from aquaterra.core.domain import Estacion, TipoEstacion
from aquaterra.infrastructure.db.repositorios import (
    RepositorioEstaciones,
    RepositorioEventosEstacion,
    RepositorioLecturas,
    RepositorioParcelas,
)
from aquaterra.infrastructure.iot_ingest import (
    parsear_csv_conservacion,
    parsear_csv_nodo_inti,
    parsear_csv_sigatoka,
    parsear_jsonl_inbeersa,
)

_PRIORIDAD_SEVERIDAD: dict[NivelSeveridadPulso, int] = {
    NivelSeveridadPulso.CRITICO: 0,
    NivelSeveridadPulso.ATENCION: 1,
    NivelSeveridadPulso.OPTIMO: 2,
    NivelSeveridadPulso.SIN_DATOS: 3,
}


@dataclass(frozen=True, slots=True)
class EntradaRadarEstacion:
    estacion: Estacion
    severidad: NivelSeveridadPulso
    alertas_activas: int
    completitud_24h_pct: float
    ultimo_ts_epoch: int | None
    diagnostico_resumen: str
    parcelas_asociadas: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OrigenDatosDetectado:
    ruta_archivo: Path
    tipo_estacion_inferido: TipoEstacion
    tamano_bytes: int


@dataclass(frozen=True, slots=True)
class ResultadoImportacionEstacion:
    estacion_id: int
    tipo_estacion: TipoEstacion
    lecturas_nuevas: int
    eventos_nuevos: int
    archivo_origen: Path


def _inferir_tipo_archivo(ruta: Path) -> TipoEstacion | None:
    nombre = ruta.name.lower()
    if nombre in {"mundonuevo.csv", "buffer_sigatoka.json"}:
        return TipoEstacion.SIGATOKA
    if nombre == "data.json" or nombre.endswith(".jsonl"):
        return TipoEstacion.INBEERSA
    if not nombre.endswith(".csv"):
        return None

    try:
        with ruta.open("r", encoding="utf-8", errors="ignore") as f:
            primera_linea = f.readline().strip().lower()
    except OSError:
        return None

    if "humectacion_foliar" in primera_linea or "lluvia_mm_min" in primera_linea:
        return TipoEstacion.SIGATOKA
    if "nivel_freatico_cm" in primera_linea or "humedad_turba" in primera_linea:
        return TipoEstacion.CONSERVACION
    if "humedada" in primera_linea or "tempraiz" in primera_linea:
        return TipoEstacion.TERRABIT_INTI
    return None


class StationDiscoveryService:
    """Radar de estaciones priorizado por criticidad y detector/importador de archivos de campo."""

    def __init__(self, conexion: sqlite3.Connection):
        self._db = conexion
        self._estaciones = RepositorioEstaciones(conexion)
        self._parcelas = RepositorioParcelas(conexion)
        self._lecturas = RepositorioLecturas(conexion)
        self._eventos = RepositorioEventosEstacion(conexion)
        self._pulso = NodePulseService(conexion)

    def listar_radar_priorizado(self) -> list[EntradaRadarEstacion]:
        """Devuelve todas las estaciones activas ordenadas desde la más crítica hasta la más estable."""
        parcelas_por_estacion: dict[int, list[str]] = {}
        for p in self._parcelas.listar():
            if p.estacion_id is not None:
                parcelas_por_estacion.setdefault(p.estacion_id, []).append(p.nombre)

        entradas: list[EntradaRadarEstacion] = []
        for est in self._estaciones.listar():
            if not est.activa:
                continue
            pulso = self._pulso.obtener_pulso_24h(est.id)
            ultimo_ep = self._lecturas.ultimo_epoch(est.id)
            num_alertas = (
                len(pulso.alertas_detectadas)
                if pulso.severidad is not NivelSeveridadPulso.SIN_DATOS
                else 0
            )
            entradas.append(
                EntradaRadarEstacion(
                    estacion=est,
                    severidad=pulso.severidad,
                    alertas_activas=num_alertas,
                    completitud_24h_pct=pulso.completitud_global_pct,
                    ultimo_ts_epoch=ultimo_ep,
                    diagnostico_resumen=pulso.diagnostico_determinista,
                    parcelas_asociadas=tuple(sorted(parcelas_por_estacion.get(est.id, ()))),
                )
            )

        entradas.sort(
            key=lambda e: (
                _PRIORIDAD_SEVERIDAD[e.severidad],
                -e.alertas_activas,
                e.estacion.codigo.lower(),
            )
        )
        return entradas

    def buscar_estaciones(
        self,
        consulta: str = "",
        *,
        tipo_estacion: TipoEstacion | None = None,
        solo_con_alertas: bool = False,
    ) -> list[EntradaRadarEstacion]:
        """Filtra el radar priorizado por texto libre (código, nombre, tipo o parcela), ecosistema y alertas."""
        termino = consulta.strip().lower()
        resultado: list[EntradaRadarEstacion] = []
        for entrada in self.listar_radar_priorizado():
            if tipo_estacion is not None and entrada.estacion.tipo is not tipo_estacion:
                continue
            if solo_con_alertas and entrada.alertas_activas == 0:
                continue
            if termino:
                campos = (
                    entrada.estacion.codigo.lower(),
                    entrada.estacion.nombre.lower(),
                    entrada.estacion.tipo.value.lower(),
                    *(nom.lower() for nom in entrada.parcelas_asociadas),
                )
                if not any(termino in campo for campo in campos):
                    continue
            resultado.append(entrada)
        return resultado

    @staticmethod
    def detectar_archivos_estacion(directorios: Sequence[str | Path]) -> list[OrigenDatosDetectado]:
        """Escanea directorios o unidades MicroSD buscando archivos de telemetría reconocidos."""
        hallados: list[OrigenDatosDetectado] = []
        vistos: set[Path] = set()

        for base_raw in directorios:
            base = Path(base_raw)
            if not base.exists() or not base.is_dir():
                continue
            candidatos = [p for p in base.iterdir() if p.is_file()]
            for archivo in sorted(candidatos):
                resuelto = archivo.resolve()
                if resuelto in vistos:
                    continue
                tipo = _inferir_tipo_archivo(archivo)
                if tipo is not None:
                    vistos.add(resuelto)
                    hallados.append(
                        OrigenDatosDetectado(
                            ruta_archivo=archivo,
                            tipo_estacion_inferido=tipo,
                            tamano_bytes=archivo.stat().st_size,
                        )
                    )
        return hallados

    def importar_archivo_estacion(
        self,
        estacion_id: int,
        ruta_archivo: str | Path,
    ) -> ResultadoImportacionEstacion:
        """Importa un archivo de estación usando el adaptador acorde al ``TipoEstacion``."""
        estacion = self._estaciones.obtener(estacion_id)
        ruta = Path(ruta_archivo)

        eventos_nuevos = 0
        if estacion.tipo is TipoEstacion.SIGATOKA:
            lecturas, eventos = parsear_csv_sigatoka(ruta, estacion_id=estacion.id)
            with self._db:
                lecturas_nuevas = self._lecturas.insertar_lote(lecturas)
                eventos_nuevos = self._eventos.insertar_lote(eventos)
        elif estacion.tipo is TipoEstacion.INBEERSA:
            lecturas = parsear_jsonl_inbeersa(ruta, estacion_id=estacion.id)
            with self._db:
                lecturas_nuevas = self._lecturas.insertar_lote(lecturas)
        elif estacion.tipo is TipoEstacion.CONSERVACION:
            lecturas = parsear_csv_conservacion(ruta, estacion_id=estacion.id)
            with self._db:
                lecturas_nuevas = self._lecturas.insertar_lote(lecturas)
        else:
            lecturas = parsear_csv_nodo_inti(ruta, estacion_id=estacion.id)
            with self._db:
                lecturas_nuevas = self._lecturas.insertar_lote(lecturas)

        if lecturas_nuevas > 0:
            self.sincronizar_humedad_parcelas(estacion.id)

        return ResultadoImportacionEstacion(
            estacion_id=estacion.id,
            tipo_estacion=estacion.tipo,
            lecturas_nuevas=lecturas_nuevas,
            eventos_nuevos=eventos_nuevos,
            archivo_origen=ruta,
        )

    def sincronizar_humedad_parcelas(self, estacion_id: int) -> int:
        """Sincroniza `parcelas.humedad_pct` con la última lectura válida de `suelo_a` de la estación."""
        serie_suelo = self._lecturas.serie(estacion_id, "suelo_a")
        if not serie_suelo:
            return 0
        ultima_humedad = round(float(serie_suelo[-1][1]), 1)
        parcelas_vinculadas = [
            p for p in self._parcelas.listar(solo_activas=True) if p.estacion_id == estacion_id
        ]
        if not parcelas_vinculadas:
            return 0
        with self._db:
            for p in parcelas_vinculadas:
                self._parcelas.actualizar_humedad(p.id, ultima_humedad)
        return len(parcelas_vinculadas)
