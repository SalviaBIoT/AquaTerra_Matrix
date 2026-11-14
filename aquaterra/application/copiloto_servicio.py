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
    InteraccionCopiloto,
    Parcela,
    VersionCalibracion,
)
from aquaterra.infrastructure.db.repositorios import (
    RepositorioCalibraciones,
    RepositorioCopiloto,
    RepositorioIncidenciaRiego,
    RepositorioParcelas,
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
        self._incidencias = RepositorioIncidenciaRiego(conexion)
        self._parcelas = RepositorioParcelas(conexion)
        self._pulso_srv = NodePulseService(conexion)
        self._control_srv = DecisionAndControlService(conexion)
        self.orquestador = OrquestadorIA(config_ia, proveedor_override=proveedor_override)

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

        ctx = ContextoDiagnosticoCopiloto(
            mensaje_usuario=mensaje_limpio,
            parametros_actuales=parametros_actuales,
            version_calibracion_actual=version_actual,
            resumen_pulso=resumen_pulso,
            parcela=parcela,
            ultima_incidencia_riego=ultima_incidencia,
            candados_activos=candados_activos,
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

            interaccion = self._copiloto_repo.registrar(
                mensaje_usuario=mensaje_limpio,
                diagnostico_ia=(
                    f"{propuesta.diagnostico_tecnico}\n\n"
                    f"Justificación: {propuesta.justificacion_agronomica}"
                ),
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
    ) -> list[InteraccionCopiloto]:
        return self._copiloto_repo.listar(estacion_id=estacion_id, parcela_id=parcela_id)

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
