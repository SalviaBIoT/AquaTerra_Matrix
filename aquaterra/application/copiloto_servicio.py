"""Servicio de Aplicación del Copiloto de Calibración y Diagnóstico Asistido (Fase B5).

Orquesta el flujo completo de la Pestaña 4 (Soporte, Diagnóstico y Recalibración):
1. Reúne automáticamente el contexto real desde SQLite (`NodePulseService`,
   `DecisionAndControlService`, `RepositorioCalibraciones` y `RepositorioIncidenciaRiego`).
2. Ejecuta el `OrquestadorIA` en cascada (`Gemini AI Studio` -> `Ollama Local` ->
   `AsesorDeterministaCopiloto`).
3. Audita cada parámetro sugerido contra `CATALOGO_COTAS_CALIBRACION` para impedir
   alucinaciones o saltos bruscos de umbral/ADC.
4. Persiste la conversación en `conversaciones_copiloto` y permite aplicar o
   revertir versiones de calibración en 1 clic (`calibraciones_nodo`).
5. Exporta el historial validado a formato `.jsonl` para entrenamiento / Fine-Tuning
   en Google AI Studio o Google Colab.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from aquaterra.application.control_servicio import DecisionAndControlService
from aquaterra.application.pulso_servicio import NodePulseService
from aquaterra.core import tiempo
from aquaterra.core.control.enclavamientos import (
    CAPACIDAD_CAMPO_POR_SUELO,
    LAMINA_MAX_L_M2_POR_SUELO,
)
from aquaterra.core.copiloto.contratos_ia import (
    ContextoDiagnosticoCopiloto,
    PropuestaCopiloto,
    construir_system_instruction_terrabit,
)
from aquaterra.core.copiloto.cotas_calibracion import (
    PARAMETROS_CALIBRACION_POR_DEFECTO,
    ResultadoAuditoriaCalibracion,
    auditar_y_acotar_ajustes,
)
from aquaterra.core.domain import (
    EntidadNoEncontrada,
    ErrorValidacion,
    Estacion,
    InteraccionCopiloto,
    Parcela,
    PuntoPronosticoClima,
    VersionCalibracion,
)
from aquaterra.infrastructure.clima import (
    LATITUD_UTP_PEREIRA,
    LONGITUD_UTP_PEREIRA,
    ClienteOpenMeteo,
)
from aquaterra.infrastructure.db.repositorios import (
    RepositorioCalibraciones,
    RepositorioCopiloto,
    RepositorioEstaciones,
    RepositorioIncidenciaRiego,
    RepositorioParcelas,
    RepositorioPronosticoClima,
)
from aquaterra.infrastructure.ia.proveedores import (
    ConfiguracionIA,
    OrquestadorIA,
    ProveedorCopilotoProtocol,
)


@dataclass(frozen=True, slots=True)
class RespuestaCopilotoCompleta:
    """Resultado integral de una consulta al Copiloto con trazabilidad de auditoría."""

    interaccion: InteraccionCopiloto
    propuesta: PropuestaCopiloto
    auditoria: ResultadoAuditoriaCalibracion
    version_aplicada: VersionCalibracion | None = None


@dataclass(frozen=True, slots=True)
class ItemBusquedaInteligente:
    """Elemento hallado por el buscador transversal de bitácoras, eventos y estaciones."""

    categoria: str  # "estacion" | "parcela" | "evento_estacion" | "incidencia_riego" | "copiloto"
    referencia_id: int
    titulo: str
    detalle: str
    ts_iso: str | None = None


@dataclass(frozen=True, slots=True)
class ResultadoBusquedaInteligente:
    """Resultado unificado de la barra de búsqueda inteligente."""

    consulta: str
    total_hallazgos: int
    items: tuple[ItemBusquedaInteligente, ...]


class CalibrationCopilotService:
    """Caso de uso para diagnóstico conversacional, recalibración segura y rollback."""

    def __init__(
        self,
        conexion: sqlite3.Connection,
        *,
        config_ia: ConfiguracionIA | None = None,
        proveedor_override: ProveedorCopilotoProtocol | None = None,
    ) -> None:
        self._db = conexion
        self._calibraciones = RepositorioCalibraciones(conexion)
        self._copiloto_repo = RepositorioCopiloto(conexion)
        self._estaciones = RepositorioEstaciones(conexion)
        self._incidencias = RepositorioIncidenciaRiego(conexion)
        self._parcelas = RepositorioParcelas(conexion)
        self._clima_repo = RepositorioPronosticoClima(conexion)
        self._clima_cliente = ClienteOpenMeteo(timeout_segundos=4.0)
        self._pulso_srv = NodePulseService(conexion)
        self._control_srv = DecisionAndControlService(conexion)
        self.orquestador = OrquestadorIA(config_ia, proveedor_override=proveedor_override)

    def _construir_contexto_climatico(
        self,
        estacion_obj: Estacion | None,
        *,
        ahora_ep: int,
        permitir_descarga_viva: bool,
    ) -> dict[str, object] | None:
        """Obtiene pronóstico horario de Open-Meteo (caché SQLite o descarga rápida en vivo)."""
        est_objetivo = estacion_obj
        if est_objetivo is None:
            activas = [e for e in self._estaciones.listar() if e.activa]
            est_objetivo = activas[0] if activas else None
        if est_objetivo is None:
            return None

        puntos: list[PuntoPronosticoClima] = self._clima_repo.ventana(
            est_objetivo.id,
            desde_epoch=ahora_ep - 3600,
            hasta_epoch=ahora_ep + 36 * 3600,
        )
        origen = "Open-Meteo (caché local SQLite)"
        if not puntos and permitir_descarga_viva:
            try:
                _, _, descargados = self._clima_cliente.descargar_pronostico_estacion(
                    est_objetivo, dias=3
                )
                if descargados:
                    with self._db:
                        self._clima_repo.guardar_lote(descargados)
                    puntos = [
                        p
                        for p in descargados
                        if (ahora_ep - 3600) <= p.ts_objetivo_epoch <= (ahora_ep + 36 * 3600)
                    ]
                    origen = "Open-Meteo (descarga directa en tiempo real)"
            except Exception:
                puntos = []

        if not puntos:
            return None

        punto_actual = min(puntos, key=lambda p: abs(p.ts_objetivo_epoch - ahora_ep))
        proximas_24 = [p for p in puntos if ahora_ep - 1800 <= p.ts_objetivo_epoch <= ahora_ep + 24 * 3600]
        if not proximas_24:
            proximas_24 = puntos[:24]

        temps = [p.temp_c for p in proximas_24 if p.temp_c is not None]
        hums = [p.hum_relativa_pct for p in proximas_24 if p.hum_relativa_pct is not None]
        vientos = [p.viento_ms for p in proximas_24 if p.viento_ms is not None]
        probs = [p.lluvia_prob_pct for p in proximas_24 if p.lluvia_prob_pct is not None]
        lluvia_total = round(sum((p.lluvia_mm or 0.0) for p in proximas_24), 2)
        et0_total = round(sum((p.et0_mm or 0.0) for p in proximas_24), 2)

        lat = est_objetivo.latitud if est_objetivo.latitud is not None else LATITUD_UTP_PEREIRA
        lon = est_objetivo.longitud if est_objetivo.longitud is not None else LONGITUD_UTP_PEREIRA

        return {
            "fuente": origen,
            "ubicacion": {
                "estacion": est_objetivo.nombre,
                "latitud": lat,
                "longitud": lon,
            },
            "ahora": {
                "hora_iso": punto_actual.ts_objetivo_iso,
                "temp_c": punto_actual.temp_c,
                "humedad_relativa_pct": punto_actual.hum_relativa_pct,
                "lluvia_prob_pct": punto_actual.lluvia_prob_pct,
                "lluvia_mm": punto_actual.lluvia_mm,
                "viento_ms": punto_actual.viento_ms,
                "et0_mm_h": punto_actual.et0_mm,
            },
            "resumen_24h": {
                "temp_min_c": round(min(temps), 1) if temps else None,
                "temp_max_c": round(max(temps), 1) if temps else None,
                "humedad_promedio_pct": round(sum(hums) / len(hums), 1) if hums else None,
                "lluvia_prob_max_pct": round(max(probs), 0) if probs else None,
                "lluvia_acumulada_24h_mm": lluvia_total,
                "viento_max_ms": round(max(vientos), 1) if vientos else None,
                "et0_acumulada_24h_mm": et0_total,
            },
            "proximas_horas": [
                {
                    "hora_iso": p.ts_objetivo_iso,
                    "temp_c": p.temp_c,
                    "hum_pct": p.hum_relativa_pct,
                    "lluvia_prob_pct": p.lluvia_prob_pct,
                    "lluvia_mm": p.lluvia_mm,
                }
                for p in proximas_24[::3][:8]
            ],
        }

    def obtener_calibracion_efectiva(
        self,
        *,
        estacion_id: int | None = None,
        parcela_id: int | None = None,
    ) -> tuple[int, dict[str, float | int | str | bool]]:
        """Devuelve `(version_actual, parametros_efectivos)` combinando defaults, suelo y versión activa."""
        parametros: dict[str, float | int | str | bool] = dict(PARAMETROS_CALIBRACION_POR_DEFECTO)

        if parcela_id is not None:
            try:
                parcela = self._parcelas.obtener(parcela_id)
                parametros["capacidad_campo_pct"] = CAPACIDAD_CAMPO_POR_SUELO.get(
                    parcela.tipo_suelo, parametros["capacidad_campo_pct"]
                )
                parametros["lamina_max_l_m2"] = LAMINA_MAX_L_M2_POR_SUELO.get(
                    parcela.tipo_suelo, parametros["lamina_max_l_m2"]
                )
            except EntidadNoEncontrada:
                pass

        activa = self._calibraciones.obtener_activa(
            estacion_id=estacion_id,
            parcela_id=parcela_id,
        )
        if activa is None and parcela_id is not None and estacion_id is not None:
            # Si no hay calibración para el par exacto (estación, parcela), busca por parcela o estación
            activa = self._calibraciones.obtener_activa(
                estacion_id=None, parcela_id=parcela_id
            ) or self._calibraciones.obtener_activa(estacion_id=estacion_id, parcela_id=None)

        if activa is not None:
            parametros.update(activa.parametros)
            return activa.version, parametros

        return 0, parametros

    def consultar_copiloto(
        self,
        mensaje_usuario: str,
        *,
        estacion_id: int | None = None,
        parcela_id: int | None = None,
        usuario_id: int | None = None,
        aplicar_ajustes: bool = False,
        ahora_epoch: int | None = None,
    ) -> RespuestaCopilotoCompleta:
        """Ejecuta diagnóstico contextualizado, audita ajustes y guarda la conversación."""
        mensaje_limpio = mensaje_usuario.strip()
        if not mensaje_limpio:
            raise ErrorValidacion("El mensaje para el Copiloto no puede estar vacío.")

        parcela: Parcela | None = None
        if parcela_id is not None:
            parcela = self._parcelas.obtener(parcela_id)
            if estacion_id is None and parcela.estacion_id is not None:
                estacion_id = parcela.estacion_id

        version_actual, parametros_actuales = self.obtener_calibracion_efectiva(
            estacion_id=estacion_id,
            parcela_id=parcela_id,
        )

        resumen_pulso = (
            self._pulso_srv.obtener_pulso_24h(estacion_id, hasta_epoch=ahora_epoch)
            if estacion_id is not None
            else None
        )

        ultima_incidencia = None
        candados_activos: tuple[str, ...] = ()
        if parcela_id is not None:
            lista_inc = self._incidencias.listar_por_parcela(parcela_id)
            if lista_inc:
                ultima_incidencia = lista_inc[-1]
            recomendacion = self._control_srv.recomendar_riego_parcela(
                parcela_id,
                momento_epoch=ahora_epoch,
            )
            candados_activos = recomendacion.veredicto_seguridad.motivos_bloqueo

        estacion_obj: Estacion | None = None
        if estacion_id is not None:
            try:
                estacion_obj = self._estaciones.obtener(estacion_id)
            except EntidadNoEncontrada:
                estacion_obj = None

        ahora_ref = ahora_epoch if ahora_epoch is not None else tiempo.a_epoch(tiempo.ahora())
        fecha_hora_local = tiempo.a_iso(tiempo.desde_epoch(ahora_ref))

        panorama_items: list[dict[str, object]] = []
        try:
            for est in self._estaciones.listar():
                if not est.activa:
                    continue
                if resumen_pulso is not None and est.id == resumen_pulso.estacion_id:
                    p_est = resumen_pulso
                else:
                    p_est = self._pulso_srv.obtener_pulso_24h(est.id, hasta_epoch=ahora_epoch)
                ultimas_vars = {
                    var: round(stat.ultimo_valor, 2)
                    for var, stat in list(p_est.variables.items())[:5]
                }
                panorama_items.append(
                    {
                        "estacion_id": est.id,
                        "codigo": est.codigo,
                        "nombre": est.nombre,
                        "tipo": est.tipo.value,
                        "severidad": p_est.severidad.value,
                        "alertas": list(p_est.alertas_detectadas[:3]),
                        "ultimas_variables": ultimas_vars,
                    }
                )
        except Exception:
            panorama_items = []

        parcelas_rel: list[dict[str, object]] = []
        try:
            for p_item in self._parcelas.listar():
                if not p_item.activa:
                    continue
                if estacion_id is None or p_item.estacion_id in (estacion_id, None):
                    parcelas_rel.append(
                        {
                            "id": p_item.id,
                            "nombre": p_item.nombre,
                            "cultivo": p_item.cultivo,
                            "tipo_suelo": p_item.tipo_suelo.value,
                            "humedad_pct": round(p_item.humedad_pct, 1),
                        }
                    )
        except Exception:
            parcelas_rel = []

        clima_pronostico = self._construir_contexto_climatico(
            estacion_obj,
            ahora_ep=ahora_ref,
            permitir_descarga_viva=(
                ahora_epoch is None and self.orquestador._override is None
            ),
        )

        previos = self._copiloto_repo.listar(
            estacion_id=estacion_id,
            parcela_id=parcela_id,
            solo_sin_estacion=(estacion_id is None),
        )
        ultimos_turnos = tuple(
            {
                "usuario": item.mensaje_usuario,
                "mandarino": item.diagnostico_ia[:450],
            }
            for item in previos[-5:]
        )

        ctx = ContextoDiagnosticoCopiloto(
            mensaje_usuario=mensaje_limpio,
            parametros_actuales=parametros_actuales,
            version_calibracion_actual=version_actual,
            resumen_pulso=resumen_pulso,
            parcela=parcela,
            ultima_incidencia_riego=ultima_incidencia,
            candados_activos=candados_activos,
            panorama_ecosistema=tuple(panorama_items),
            ultimos_turnos=ultimos_turnos,
            clima_pronostico=clima_pronostico,
            fecha_hora_local=fecha_hora_local,
            parcelas_relacionadas=tuple(parcelas_rel[:8]),
        )

        propuesta, auditoria = self.orquestador.diagnosticar_con_auditoria(ctx)

        version_creada: VersionCalibracion | None = None
        with self._db:
            if (
                aplicar_ajustes
                and propuesta.ajustes_propuestos
                and (estacion_id is not None or parcela_id is not None)
            ):
                nuevos_parametros = {**parametros_actuales, **propuesta.ajustes_propuestos}
                version_creada = self._calibraciones.guardar_nueva_version(
                    estacion_id=estacion_id,
                    parcela_id=parcela_id,
                    parametros=nuevos_parametros,
                    motivo=f"Copiloto ({propuesta.proveedor_ia}): {mensaje_limpio[:80]}",
                    autor_id=usuario_id,
                )

            texto_guardado = (
                f"{propuesta.diagnostico_tecnico}\n\n"
                f"Justificación: {propuesta.justificacion_agronomica}"
                if propuesta.justificacion_agronomica.strip()
                else propuesta.diagnostico_tecnico
            )
            interaccion = self._copiloto_repo.registrar(
                mensaje_usuario=mensaje_limpio,
                diagnostico_ia=texto_guardado,
                proveedor_ia=propuesta.proveedor_ia,
                estacion_id=estacion_id,
                parcela_id=parcela_id,
                usuario_id=usuario_id,
                ajustes_propuestos=propuesta.ajustes_propuestos or None,
                calibracion_aplicada_id=version_creada.id if version_creada else None,
            )

        return RespuestaCopilotoCompleta(
            interaccion=interaccion,
            propuesta=propuesta,
            auditoria=auditoria,
            version_aplicada=version_creada,
        )

    def aplicar_ajustes_interaccion(
        self,
        interaccion_id: int,
        *,
        autor_id: int | None = None,
        motivo_adicional: str | None = None,
    ) -> VersionCalibracion:
        """Aplica en 1 clic los ajustes propuestos en una interacción previa del Copiloto."""
        fila = self._db.execute(
            "SELECT * FROM conversaciones_copiloto WHERE id = ?", (interaccion_id,)
        ).fetchone()
        if fila is None:
            raise EntidadNoEncontrada("InteraccionCopiloto", interaccion_id)

        interaccion = self._copiloto_repo._a_entidad(fila)
        if not interaccion.ajustes_propuestos:
            raise ErrorValidacion(
                f"La interacción #{interaccion_id} no contiene ajustes de calibración propuestos."
            )
        if interaccion.estacion_id is None and interaccion.parcela_id is None:
            raise ErrorValidacion(
                "La interacción no está asociada a una estación ni a una parcela específica."
            )

        _, parametros_actuales = self.obtener_calibracion_efectiva(
            estacion_id=interaccion.estacion_id,
            parcela_id=interaccion.parcela_id,
        )
        auditoria = auditar_y_acotar_ajustes(interaccion.ajustes_propuestos, parametros_actuales)
        nuevos_parametros = {**parametros_actuales, **auditoria.ajustes_seguros}
        motivo = motivo_adicional or f"Aplicado desde interacción Copiloto #{interaccion_id}"

        with self._db:
            nueva_version = self._calibraciones.guardar_nueva_version(
                estacion_id=interaccion.estacion_id,
                parcela_id=interaccion.parcela_id,
                parametros=nuevos_parametros,
                motivo=motivo,
                autor_id=autor_id,
            )
            self._db.execute(
                "UPDATE conversaciones_copiloto SET calibracion_aplicada_id = ? WHERE id = ?",
                (nueva_version.id, interaccion_id),
            )
        return nueva_version

    def revertir_calibracion(
        self,
        *,
        estacion_id: int | None = None,
        parcela_id: int | None = None,
        version_id_destino: int | None = None,
        autor_id: int | None = None,
    ) -> VersionCalibracion:
        """Revierte en 1 clic a una versión anterior de calibración (rollback no destructivo)."""
        with self._db:
            if version_id_destino is not None:
                return self._calibraciones.restaurar_version(
                    version_id_destino, autor_id=autor_id
                )

            versiones = self._calibraciones.listar_versiones(
                estacion_id=estacion_id,
                parcela_id=parcela_id,
            )
            if len(versiones) < 2:
                raise ErrorValidacion(
                    "No existe una versión previa de calibración hacia la cual hacer rollback."
                )
            version_previa = versiones[-2]
            return self._calibraciones.restaurar_version(
                version_previa.id, autor_id=autor_id
            )

    def listar_historial_conversaciones(
        self,
        *,
        estacion_id: int | None = None,
        parcela_id: int | None = None,
        solo_sin_estacion: bool = False,
    ) -> list[InteraccionCopiloto]:
        return self._copiloto_repo.listar(
            estacion_id=estacion_id,
            parcela_id=parcela_id,
            solo_sin_estacion=solo_sin_estacion,
        )

    def exportar_dataset_entrenamiento_jsonl(
        self,
        ruta_destino: Path | str,
        *,
        solo_con_ajustes: bool = False,
    ) -> int:
        """Exporta el historial de `conversaciones_copiloto` en formato JSONL para Fine-Tuning.

        Cada línea generada contiene la instrucción del sistema, el mensaje del
        operador y la salida estructurada del modelo validada, lista para subir a
        Google AI Studio (Tuned Models) o entrenar con Unsloth en Google Colab.
        """
        ruta = Path(ruta_destino)
        ruta.parent.mkdir(parents=True, exist_ok=True)

        interacciones = self._copiloto_repo.listar()
        instruccion_sistema = construir_system_instruction_terrabit()
        exportadas = 0

        with ruta.open("w", encoding="utf-8") as fh:
            for item in interacciones:
                if solo_con_ajustes and not item.ajustes_propuestos:
                    continue
                registro = {
                    "system_instruction": instruccion_sistema,
                    "messages": [
                        {"role": "user", "content": item.mensaje_usuario},
                        {
                            "role": "model",
                            "content": json.dumps(
                                {
                                    "diagnostico_ia": item.diagnostico_ia,
                                    "ajustes_propuestos": item.ajustes_propuestos or {},
                                },
                                ensure_ascii=False,
                            ),
                        },
                    ],
                    "metadata": {
                        "interaccion_id": item.id,
                        "estacion_id": item.estacion_id,
                        "parcela_id": item.parcela_id,
                        "proveedor_ia": item.proveedor_ia,
                        "calibracion_aplicada_id": item.calibracion_aplicada_id,
                        "ts_iso": item.ts_iso,
                    },
                }
                fh.write(json.dumps(registro, ensure_ascii=False) + "\n")
                exportadas += 1

        return exportadas

    @staticmethod
    def _etiquetar_variable_reporte(clave: str) -> str:
        mapa = {
            "suelo_a": "Humedad Suelo A",
            "suelo_b": "Humedad Suelo B",
            "humedad_suelo_pct": "Humedad de Suelo",
            "hum_aire": "Humedad Relativa",
            "humedad_rel_pct": "Humedad Relativa",
            "temp_aire": "Temperatura Aire",
            "temp_c": "Temperatura Aire",
            "temp_raiz": "Temperatura Radicular",
            "temp_suelo_c": "Temperatura Suelo",
            "presion": "Presión Atmosférica",
            "vpd": "VPD",
            "vpd_kpa": "VPD",
            "voltaje": "Voltaje Nodo",
            "bateria_v": "Batería",
            "bateria_pct": "Batería",
            "radiacion_wm2": "Radiación Solar",
            "mojado_foliar_pct": "Mojado Foliar",
            "nivel_agua_cm": "Nivel Freático",
            "caudal_l_min": "Caudal",
            "lluvia_mm": "Precipitación",
        }
        return mapa.get(clave, clave.replace("_", " ").capitalize())

    @staticmethod
    def _etiquetar_proveedor_ia(proveedor_id: str) -> str:
        mapa = {
            "local_reglas": "Motor Determinista Local",
            "gemini": "Google Gemini AI",
            "ollama": "Ollama Local",
        }
        for k, etiqueta in mapa.items():
            if proveedor_id.startswith(k):
                return etiqueta
        return proveedor_id.replace("_", " ").capitalize()

    @staticmethod
    def _limpiar_sintaxis_cruda(texto: str) -> str:
        return texto.replace("`", "").strip()

    def generar_reporte_pulso_24h(
        self,
        estacion_id: int,
        *,
        hasta_epoch: int | None = None,
    ) -> dict[str, object]:
        """Genera un informe ejecutivo 24h en formato texto limpio y estructura JSON."""
        pulso = self._pulso_srv.obtener_pulso_24h(estacion_id, hasta_epoch=hasta_epoch)
        _, params = self.obtener_calibracion_efectiva(estacion_id=estacion_id)
        ctx = ContextoDiagnosticoCopiloto(
            mensaje_usuario=(
                "Redacta un resumen ejecutivo claro, conciso y estructurado de las últimas "
                "24 horas de operación para ingeniería agronómica."
            ),
            parametros_actuales=params,
            resumen_pulso=pulso,
        )
        propuesta, _ = self.orquestador.diagnosticar_con_auditoria(ctx)
        proveedor_legible = self._etiquetar_proveedor_ia(propuesta.proveedor_ia)

        lecturas = [
            {
                "clave": k,
                "nombre": self._etiquetar_variable_reporte(k),
                "valor": round(float(v.ultimo_valor), 2),
                "unidad": v.unidad or "",
            }
            for k, v in list(pulso.variables.items())[:8]
        ]
        lineas_lecturas = (
            "\n".join(
                f"  - {item['nombre']}: {item['valor']:.1f}"
                f"{(' ' + item['unidad']) if item['unidad'] else ''}"
                for item in lecturas
            )
            if lecturas
            else "  - Sin lecturas registradas en las últimas 24 horas."
        )
        alertas = list(pulso.alertas_detectadas)
        lineas_alertas = (
            "\n".join(f"  - {a}" for a in alertas)
            if alertas
            else "  - Sin alertas críticas activas."
        )
        diagnostico_limpio = self._limpiar_sintaxis_cruda(propuesta.diagnostico_tecnico)
        justificacion_limpia = self._limpiar_sintaxis_cruda(propuesta.justificacion_agronomica)

        mensaje = (
            f"REPORTE EJECUTIVO 24H — {pulso.nombre_estacion} ({pulso.codigo_estacion})\n"
            f"Estado: {pulso.severidad.value.upper()} | "
            f"Completitud 24h: {pulso.completitud_global_pct:.0f}% | "
            f"Motor: {proveedor_legible}\n\n"
            f"TELEMETRÍA RECIENTE\n{lineas_lecturas}\n\n"
            f"ALERTAS ACTIVAS\n{lineas_alertas}\n\n"
            f"DIAGNÓSTICO TÉCNICO\n{diagnostico_limpio}\n\n"
            f"RECOMENDACIÓN AGRONÓMICA\n{justificacion_limpia}"
        )
        return {
            "mensaje": mensaje,
            "proveedor_ia": propuesta.proveedor_ia,
            "reporte": {
                "estacion": pulso.nombre_estacion,
                "codigo": pulso.codigo_estacion,
                "severidad": pulso.severidad.value,
                "completitud_pct": round(float(pulso.completitud_global_pct), 1),
                "proveedor_ia": propuesta.proveedor_ia,
                "proveedor_legible": proveedor_legible,
                "lecturas": lecturas,
                "alertas": alertas,
                "diagnostico": diagnostico_limpio,
                "justificacion": justificacion_limpia,
            },
        }

    def narrar_pulso_24h(
        self,
        estacion_id: int,
        *,
        hasta_epoch: int | None = None,
    ) -> tuple[str, str]:
        """Genera un reporte ejecutivo 24h listo para UI, WhatsApp, Telegram o n8n.

        Devuelve `(mensaje_formateado, proveedor_ia)`.
        """
        res = self.generar_reporte_pulso_24h(estacion_id, hasta_epoch=hasta_epoch)
        return str(res["mensaje"]), str(res["proveedor_ia"])

    def buscar_inteligente_bitacora(
        self,
        consulta: str,
        *,
        limite: int = 25,
    ) -> ResultadoBusquedaInteligente:
        """Barra de búsqueda inteligente transversal sobre estaciones, parcelas, eventos y copiloto."""
        termino = consulta.strip().lower()
        if not termino:
            return ResultadoBusquedaInteligente(consulta="", total_hallazgos=0, items=())

        hallazgos: list[ItemBusquedaInteligente] = []
        like_param = f"%{termino}%"

        # 1. Estaciones
        filas_est = self._db.execute(
            """SELECT id, codigo, nombre, tipo, creado_en FROM estaciones
               WHERE lower(codigo) LIKE ? OR lower(nombre) LIKE ? OR lower(tipo) LIKE ?
               ORDER BY id ASC LIMIT ?""",
            (like_param, like_param, like_param, limite),
        ).fetchall()
        for f in filas_est:
            hallazgos.append(
                ItemBusquedaInteligente(
                    categoria="estacion",
                    referencia_id=int(f["id"]),
                    titulo=f"Estación {f['nombre']} ({f['codigo']})",
                    detalle=f"Familia: {f['tipo']}",
                    ts_iso=f["creado_en"],
                )
            )

        # 2. Parcelas
        filas_par = self._db.execute(
            """SELECT id, nombre, cultivo, tipo_suelo, humedad_pct, actualizado_en FROM parcelas
               WHERE activa = 1 AND (lower(nombre) LIKE ? OR lower(cultivo) LIKE ? OR lower(tipo_suelo) LIKE ?)
               ORDER BY id ASC LIMIT ?""",
            (like_param, like_param, like_param, limite),
        ).fetchall()
        for f in filas_par:
            hallazgos.append(
                ItemBusquedaInteligente(
                    categoria="parcela",
                    referencia_id=int(f["id"]),
                    titulo=f"Parcela {f['nombre']} ({f['cultivo']})",
                    detalle=f"Suelo {f['tipo_suelo']} · Humedad actual {f['humedad_pct']:.1f}%",
                    ts_iso=f["actualizado_en"],
                )
            )

        # 3. Eventos discretos de estación
        filas_ev = self._db.execute(
            """SELECT id, estacion_id, tipo_evento, valor_texto, archivo_ruta, ts_iso
               FROM eventos_estacion
               WHERE lower(tipo_evento) LIKE ? OR lower(COALESCE(valor_texto, '')) LIKE ?
                     OR lower(COALESCE(archivo_ruta, '')) LIKE ?
               ORDER BY ts_epoch DESC LIMIT ?""",
            (like_param, like_param, like_param, limite),
        ).fetchall()
        for f in filas_ev:
            hallazgos.append(
                ItemBusquedaInteligente(
                    categoria="evento_estacion",
                    referencia_id=int(f["id"]),
                    titulo=f"Evento '{f['tipo_evento']}' (Estación #{f['estacion_id']})",
                    detalle=str(f["valor_texto"] or f["archivo_ruta"] or ""),
                    ts_iso=f["ts_iso"],
                )
            )

        # 4. Incidencia de riegos
        filas_inc = self._db.execute(
            """SELECT id, evento_riego_id, delta_a_pct, efectividad, observaciones, evaluado_en
               FROM incidencia_riego
               WHERE lower(efectividad) LIKE ? OR lower(COALESCE(observaciones, '')) LIKE ?
               ORDER BY id DESC LIMIT ?""",
            (like_param, like_param, limite),
        ).fetchall()
        for f in filas_inc:
            hallazgos.append(
                ItemBusquedaInteligente(
                    categoria="incidencia_riego",
                    referencia_id=int(f["id"]),
                    titulo=f"Incidencia Riego #{f['evento_riego_id']} [{f['efectividad']}]",
                    detalle=f"Δθ_A={f['delta_a_pct']:+.1f}% · {f['observaciones'] or ''}",
                    ts_iso=f["evaluado_en"],
                )
            )

        # 5. Conversaciones del Copiloto
        filas_cop = self._db.execute(
            """SELECT id, mensaje_usuario, diagnostico_ia, proveedor_ia, ts_iso
               FROM conversaciones_copiloto
               WHERE lower(mensaje_usuario) LIKE ? OR lower(diagnostico_ia) LIKE ?
               ORDER BY id DESC LIMIT ?""",
            (like_param, like_param, limite),
        ).fetchall()
        for f in filas_cop:
            hallazgos.append(
                ItemBusquedaInteligente(
                    categoria="copiloto",
                    referencia_id=int(f["id"]),
                    titulo=f"Consulta Copiloto ({f['proveedor_ia']}): {str(f['mensaje_usuario'])[:60]}",
                    detalle=str(f["diagnostico_ia"])[:140],
                    ts_iso=f["ts_iso"],
                )
            )

        recortados = tuple(hallazgos[:limite])
        return ResultadoBusquedaInteligente(
            consulta=consulta.strip(),
            total_hallazgos=len(recortados),
            items=recortados,
        )
