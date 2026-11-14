"""Pruebas integrales de la Fase B5: Copiloto IA, Guardarraíles de Calibración, Rollback y Mejoras IoT."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aquaterra.application.contenedor import construir_contenedor
from aquaterra.application.copiloto_servicio import CalibrationCopilotService
from aquaterra.config import Configuracion
from aquaterra.core.copiloto import (
    ContextoDiagnosticoCopiloto,
    PropuestaCopiloto,
    auditar_y_acotar_ajustes,
)
from aquaterra.core.domain.entidades import (
    DatosParcela,
    LecturaSensor,
    TipoEstacion,
    TipoSuelo,
)
from aquaterra.infrastructure.db.repositorios import (
    RepositorioEstaciones,
    RepositorioLecturas,
    RepositorioParcelas,
)
from aquaterra.infrastructure.ia import (
    MODELO_GEMINI_POR_DEFECTO,
    ConfiguracionIA,
    normalizar_modelo_gemini,
    parsear_respuesta_json_ia,
)


def test_auditoria_cotas_bloquea_alucinaciones_y_saltos_bruscos() -> None:
    """Riesgo 3: Ningún modelo puede inyectar claves falsas ni saltar más de delta_max_por_paso."""
    actuales = {
        "umbral_humedad_pct": 45.0,
        "capacidad_campo_pct": 70.0,
        "adc_seco": 3200.0,
        "adc_agua": 1450.0,
    }
    propuestos_alucinados = {
        "umbral_humedad_pct": 5.0,        # Salto de -40% (máx permitido ±10% -> debe quedar en 35.0%)
        "adc_agua": 3000.0,               # Salto excesivo -> acotado por paso a 1800.0
        "frecuencia_cuantica_ghz": 99.9,  # Clave inventada -> rechazada
        "ema_alpha": "no_es_numero",      # Tipo inválido -> rechazado
    }

    res = auditar_y_acotar_ajustes(propuestos_alucinados, actuales)

    assert res.tuvo_intervencion_guardarrailes is True
    assert "frecuencia_cuantica_ghz" in res.claves_rechazadas
    assert "ema_alpha" in res.claves_rechazadas
    assert res.ajustes_seguros["umbral_humedad_pct"] == pytest.approx(35.0)
    assert res.ajustes_seguros["adc_agua"] == pytest.approx(1800.0)
    assert len(res.recortes_aplicados) == 2


def test_auditoria_invariantes_cruzadas_capacidad_campo_y_adc() -> None:
    """Verifica que umbral_humedad_pct <= capacidad_campo - 5% y adc_agua <= adc_seco - 400."""
    actuales = {
        "umbral_humedad_pct": 62.0,
        "capacidad_campo_pct": 65.0,
        "adc_seco": 2200.0,
        "adc_agua": 1750.0,
    }
    propuestos = {
        "umbral_humedad_pct": 64.0,  # Supera 65 - 5 = 60% -> debe recortarse a 60.0%
        "adc_agua": 1950.0,          # Supera 2200 - 400 = 1800 -> debe recortarse a 1800.0
    }

    res = auditar_y_acotar_ajustes(propuestos, actuales)
    assert res.ajustes_seguros["umbral_humedad_pct"] == pytest.approx(60.0)
    assert res.ajustes_seguros["adc_agua"] == pytest.approx(1800.0)


def test_normalizar_modelo_gemini_reemplaza_modelos_deprecados() -> None:
    assert normalizar_modelo_gemini("gemini-2.5-flash") == MODELO_GEMINI_POR_DEFECTO
    assert normalizar_modelo_gemini("gemini-1.5-pro") == MODELO_GEMINI_POR_DEFECTO
    assert normalizar_modelo_gemini("gemini-4-argon") == "gemini-4-argon"


def test_parsear_respuesta_json_ia_con_bloque_markdown() -> None:
    raw = """```json
    {
      "diagnostico_tecnico": "Exceso de lámina detectado en horizonte A.",
      "justificacion_agronomica": "Reducir lámina evita lixiviación.",
      "ajustes_propuestos": {"lamina_max_l_m2": 6.5},
      "confianza": 0.94,
      "alertas_consideradas": ["Saturación Suelo A"]
    }
    ```"""
    prop = parsear_respuesta_json_ia(raw, proveedor_ia="gemini:gemini-4-hydrogen")
    assert prop.proveedor_ia == "gemini:gemini-4-hydrogen"
    assert prop.ajustes_propuestos == {"lamina_max_l_m2": 6.5}
    assert prop.confianza == pytest.approx(0.94)


def test_ciclo_completo_copiloto_reglas_aplicacion_rollback_y_exportacion_jsonl(
    tmp_path: Path,
) -> None:
    cfg = Configuracion(ruta_db=tmp_path / "copiloto_test.db")
    cont = construir_contenedor(cfg, sembrar_legacy=False)
    try:
        with cont.conexion:
            est = RepositorioEstaciones(cont.conexion).crear(
                "INTI-COP-01", "Estación INTI Lote Norte", TipoEstacion.TERRABIT_INTI
            )
            parcela = RepositorioParcelas(cont.conexion).crear(
                DatosParcela(
                    nombre="Lote Norte Aguacate",
                    cultivo="Maiz",
                    area_m2=120.0,
                    humedad_pct=52.0,
                    tipo_suelo=TipoSuelo.FRANCO,
                    riego_auto=True,
                    estacion_id=est.id,
                )
            )

        cont.copiloto.orquestador.config = ConfiguracionIA(proveedor_preferido="local_reglas")

        # 1. Consulta por exceso de riego ("se nos pasó la mano")
        r1 = cont.copiloto.consultar_copiloto(
            "La última vez regué pero se nos pasó la mano y quedó saturado",
            parcela_id=parcela.id,
        )
        assert r1.propuesta.proveedor_ia == "local_reglas"
        assert "lamina_max_l_m2" in r1.propuesta.ajustes_propuestos
        assert "umbral_humedad_pct" in r1.propuesta.ajustes_propuestos
        assert r1.version_aplicada is None

        # 2. Aplicar en 1 clic los ajustes de esa interacción -> crea versión v1
        v1 = cont.copiloto.aplicar_ajustes_interaccion(r1.interaccion.id)
        assert v1.version == 1
        assert v1.activa is True
        assert v1.parametros["umbral_humedad_pct"] == pytest.approx(42.0)

        # 3. Segunda consulta por ruido eléctrico en el ADC aplicando de inmediato -> versión v2
        r2 = cont.copiloto.consultar_copiloto(
            "Notamos mucho ruido y picos en el filtro ema del sensor",
            parcela_id=parcela.id,
            aplicar_ajustes=True,
        )
        assert r2.version_aplicada is not None
        assert r2.version_aplicada.version == 2
        assert r2.version_aplicada.parametros["ema_alpha"] < 0.20

        # 4. Rollback en 1 clic -> restaura los parámetros de v1 en una nueva versión v3 trazable
        v3_rollback = cont.copiloto.revertir_calibracion(
            estacion_id=est.id,
            parcela_id=parcela.id,
        )
        assert v3_rollback.version == 3
        assert "Rollback a versión v1" in v3_rollback.motivo
        assert v3_rollback.parametros["ema_alpha"] == pytest.approx(v1.parametros["ema_alpha"])

        # 5. Exportar dataset JSONL para futuro Fine-Tuning en AI Studio / Colab
        ruta_jsonl = tmp_path / "dataset_sft.jsonl"
        total_lineas = cont.copiloto.exportar_dataset_entrenamiento_jsonl(
            ruta_jsonl, solo_con_ajustes=True
        )
        assert total_lineas == 2
        lineas = [json.loads(linea) for linea in ruta_jsonl.read_text(encoding="utf-8").splitlines()]
        assert len(lineas) == 2
        assert "system_instruction" in lineas[0]
        assert lineas[0]["messages"][0]["role"] == "user"
    finally:
        cont.cerrar()


def test_copiloto_con_proveedor_externo_alucinado_y_fallback_ante_error(
    tmp_path: Path,
) -> None:
    cfg = Configuracion(ruta_db=tmp_path / "copiloto_override.db")
    cont = construir_contenedor(cfg, sembrar_legacy=False)
    try:
        with cont.conexion:
            est = RepositorioEstaciones(cont.conexion).crear(
                "INTI-LLM-01", "Estación Prueba LLM", TipoEstacion.TERRABIT_INTI
            )

        class ProveedorSimuladoAlucinado:
            proveedor_id = "gemini:gemini-4-hydrogen"

            def diagnosticar(self, ctx: ContextoDiagnosticoCopiloto) -> PropuestaCopiloto:
                return PropuestaCopiloto(
                    diagnostico_tecnico="Diagnóstico simulado desde nube.",
                    justificacion_agronomica="Prueba de acotamiento.",
                    ajustes_propuestos={
                        "umbral_humedad_pct": 1.0,  # Fuera de rango y salto > 10%
                        "clave_inexistente": 500.0,
                    },
                    confianza=0.95,
                    proveedor_ia=self.proveedor_id,
                )

        srv_ia = CalibrationCopilotService(
            cont.conexion, proveedor_override=ProveedorSimuladoAlucinado()
        )
        resp = srv_ia.consultar_copiloto(
            "Ajustar umbral por favor",
            estacion_id=est.id,
            aplicar_ajustes=True,
        )
        assert resp.auditoria.tuvo_intervencion_guardarrailes is True
        assert "clave_inexistente" in resp.auditoria.claves_rechazadas
        assert resp.propuesta.ajustes_propuestos["umbral_humedad_pct"] == pytest.approx(35.0)
        assert resp.version_aplicada is not None
        assert resp.version_aplicada.parametros["umbral_humedad_pct"] == pytest.approx(35.0)

        # Ahora probamos caída de red en el proveedor -> debe caer limpio a local_reglas
        class ProveedorCaido:
            proveedor_id = "ollama:gemma3:4b"

            def diagnosticar(self, ctx: ContextoDiagnosticoCopiloto) -> PropuestaCopiloto:
                raise ConnectionError("Servidor Ollama apagado")

        srv_caido = CalibrationCopilotService(cont.conexion, proveedor_override=ProveedorCaido())
        resp_fallback = srv_caido.consultar_copiloto(
            "Estado general de la estación", estacion_id=est.id
        )
        assert resp_fallback.propuesta.proveedor_ia == "local_reglas"
    finally:
        cont.cerrar()


def test_reparacion_timestamps_rtc_y_sincronizacion_humedad_parcela(tmp_path: Path) -> None:
    """Verifica las 2 mejoras complementarias: re-anclaje RTC (calidad=2) y sync de suelo_a."""
    cfg = Configuracion(ruta_db=tmp_path / "mejoras_iot.db")
    cont = construir_contenedor(cfg, sembrar_legacy=False)
    try:
        with cont.conexion:
            est = RepositorioEstaciones(cont.conexion).crear(
                "INTI-RTC-01", "Estación Páramo RTC", TipoEstacion.TERRABIT_INTI
            )
            parcela = RepositorioParcelas(cont.conexion).crear(
                DatosParcela(
                    nombre="Parcela Sincronizada",
                    cultivo="Fresas",
                    area_m2=80.0,
                    humedad_pct=40.0,
                    tipo_suelo=TipoSuelo.FRANCO,
                    riego_auto=True,
                    estacion_id=est.id,
                )
            )

        # 1. Insertar lecturas con RTC reiniciado en el año 2000 (epoch ~946684800, calidad=2)
        repo_lec = RepositorioLecturas(cont.conexion)
        with cont.conexion:
            repo_lec.insertar_lote(
                [
                    LecturaSensor(
                        estacion_id=est.id,
                        variable="suelo_a",
                        valor=58.0,
                        ts_epoch=946_684_800,
                        ts_iso="2000-01-01T00:00:00-05:00",
                        fuente="sd_csv",
                        unidad="%",
                        calidad=2,
                    ),
                    LecturaSensor(
                        estacion_id=est.id,
                        variable="suelo_a",
                        valor=61.5,
                        ts_epoch=946_685_100,
                        ts_iso="2000-01-01T00:05:00-05:00",
                        fuente="sd_csv",
                        unidad="%",
                        calidad=2,
                    ),
                ]
            )

        # Mientras tengan calidad=2 no aparecen en la serie válida
        assert repo_lec.serie(est.id, "suelo_a") == []

        # Re-anclamos sabiendo que la última muestra se recogió en ts_fin_real = 1_763_080_000
        with cont.conexion:
            reparadas = repo_lec.reparar_timestamps_rtc(
                est.id, ts_fin_real_epoch=1_763_080_000
            )
        assert reparadas == 2

        serie_reparada = repo_lec.serie(est.id, "suelo_a")
        assert len(serie_reparada) == 2
        assert serie_reparada[-1] == (1_763_080_000, 61.5)

        # 2. Sincronizar humedad de parcela vinculada
        actualizadas = cont.radar.sincronizar_humedad_parcelas(est.id)
        assert actualizadas == 1
        parcela_refrescada = cont.parcelas.obtener(parcela.id)
        assert parcela_refrescada.humedad_pct == pytest.approx(61.5)
    finally:
        cont.cerrar()


def test_mandarino_saludo_conversacional_y_modo_tecnico() -> None:
    """Verifica que Mandarino responda con calidez a saludos sin disparar auditorías frías."""
    from aquaterra.core.copiloto.asesor_reglas import AsesorDeterministaCopiloto

    asesor = AsesorDeterministaCopiloto()
    ctx_saludo = ContextoDiagnosticoCopiloto(
        mensaje_usuario="Hola",
        parametros_actuales={},
    )
    prop_saludo = asesor.diagnosticar(ctx_saludo)
    assert "Mandarino" in prop_saludo.diagnostico_tecnico
    assert prop_saludo.justificacion_agronomica == ""
    assert prop_saludo.ajustes_propuestos == {}

    ctx_mixto = ContextoDiagnosticoCopiloto(
        mensaje_usuario="Hola, revisa el umbral porque el riego quedó insuficiente",
        parametros_actuales={"umbral_humedad_pct": 45.0, "lamina_max_l_m2": 8.0},
    )
    prop_tecnica = asesor.diagnosticar(ctx_mixto)
    assert "umbral_humedad_pct" in prop_tecnica.ajustes_propuestos
    assert prop_tecnica.justificacion_agronomica != ""


def test_segmentacion_estricta_general_vs_estacion_y_contexto_global(
    tmp_path: Path,
) -> None:
    """Verifica aislamiento de historial por estación sin perder conciencia global."""
    cfg = Configuracion(ruta_db=tmp_path / "segmentacion_test.db")
    cont = construir_contenedor(cfg, sembrar_legacy=False)
    try:
        with cont.conexion:
            est1 = RepositorioEstaciones(cont.conexion).crear(
                "NODE-A", "Estación Alpha", TipoEstacion.TERRABIT_INTI
            )
        cont.copiloto.orquestador.config = ConfiguracionIA(proveedor_preferido="local_reglas")

        # 1. Charla general (estacion_id=None) -> recibe panorama global del nodo
        res_gen = cont.copiloto.consultar_copiloto("Hola Mandarino", estacion_id=None)
        diag_lower = res_gen.propuesta.diagnostico_tecnico.lower()
        assert "estación alpha" in diag_lower or "estación" in diag_lower

        # 2. Charla en Estación Alpha (estacion_id=est1.id)
        cont.copiloto.consultar_copiloto("Analiza el pulso de Alpha", estacion_id=est1.id)

        hist_general = cont.copiloto.listar_historial_conversaciones(solo_sin_estacion=True)
        hist_alpha = cont.copiloto.listar_historial_conversaciones(estacion_id=est1.id)

        assert len(hist_general) == 1
        assert hist_general[0].mensaje_usuario == "Hola Mandarino"
        assert len(hist_alpha) == 1
        assert hist_alpha[0].mensaje_usuario == "Analiza el pulso de Alpha"
    finally:
        cont.cerrar()


def test_memoria_multiturno_segmentada_y_circuit_breaker_cuota(tmp_path: Path) -> None:
    """Verifica memoria de turnos aislada por hilo y cooldown ante error 429 de Gemini."""
    from aquaterra.infrastructure.ia.proveedores import (
        OrquestadorIA,
        _es_error_cuota_gemini,
    )

    turnos_capturados: list[tuple[dict[str, str], ...]] = []

    class CapturingMock:
        proveedor_id = "mock_memoria"

        def diagnosticar(self, ctx: ContextoDiagnosticoCopiloto) -> PropuestaCopiloto:
            turnos_capturados.append(ctx.ultimos_turnos)
            return PropuestaCopiloto(
                diagnostico_tecnico=f"Respuesta a: {ctx.mensaje_usuario}",
                justificacion_agronomica="",
                ajustes_propuestos={},
                confianza=0.95,
                alertas_consideradas=(),
                proveedor_ia=self.proveedor_id,
            )

    cfg = Configuracion(ruta_db=tmp_path / "memoria_test.db")
    cont = construir_contenedor(cfg, sembrar_legacy=False)
    try:
        with cont.conexion:
            est = RepositorioEstaciones(cont.conexion).crear(
                "NODE-M", "Nodo Memoria", TipoEstacion.TERRABIT_INTI
            )
        cont.copiloto.orquestador = OrquestadorIA(proveedor_override=CapturingMock())

        # Turno 1 general -> historial vacío
        cont.copiloto.consultar_copiloto("Mensaje Gen 1", estacion_id=None)
        assert turnos_capturados[-1] == ()

        # Turno 1 estación -> sigue aislado (no recibe "Mensaje Gen 1")
        cont.copiloto.consultar_copiloto("Mensaje Est 1", estacion_id=est.id)
        assert turnos_capturados[-1] == ()

        # Turno 2 general -> recibe SOLO "Mensaje Gen 1"
        cont.copiloto.consultar_copiloto("¿Qué sugerencias me das?", estacion_id=None)
        assert len(turnos_capturados[-1]) == 1
        assert turnos_capturados[-1][0]["usuario"] == "Mensaje Gen 1"

        assert _es_error_cuota_gemini(RuntimeError("Error code: 429 - too_many_requests")) is True
        assert _es_error_cuota_gemini(RuntimeError("Timeout de lectura")) is False
    finally:
        cont.cerrar()


def test_prompt_modo_ligero_vs_tecnico() -> None:
    """Verifica que los saludos omitan parámetros numéricos de calibración (two-tier)."""
    from aquaterra.core.copiloto.contratos_ia import (
        construir_prompt_contexto_copiloto,
        es_consulta_ligera,
    )

    assert es_consulta_ligera("Hola Mandarino") is True
    assert es_consulta_ligera("Audita los umbrales de calibración ante lluvia") is False

    prompt_ligero = construir_prompt_contexto_copiloto(
        ContextoDiagnosticoCopiloto(
            mensaje_usuario="Hola Mandarino",
            parametros_actuales={"umbral_humedad_pct": 45.0},
        )
    )
    assert '"modo": "charla_ligera"' in prompt_ligero
    assert "umbral_humedad_pct" not in prompt_ligero

    prompt_tecnico = construir_prompt_contexto_copiloto(
        ContextoDiagnosticoCopiloto(
            mensaje_usuario="Audita umbral de riego",
            parametros_actuales={"umbral_humedad_pct": 45.0},
        )
    )
    assert '"modo": "analisis_tecnico"' in prompt_tecnico
    assert "umbral_humedad_pct" in prompt_tecnico


def test_mandarino_inyecta_clima_open_meteo_y_evita_texto_generico(tmp_path: Path) -> None:
    """Verifica enlace climático Open-Meteo al Copiloto y supresión de relleno genérico."""
    from aquaterra.core import tiempo
    from aquaterra.core.copiloto.contratos_ia import (
        construir_prompt_contexto_copiloto,
        es_consulta_ligera,
    )
    from aquaterra.core.domain.entidades import PuntoPronosticoClima
    from aquaterra.infrastructure.db.repositorios import RepositorioPronosticoClima
    from aquaterra.infrastructure.ia.proveedores import OrquestadorIA

    assert es_consulta_ligera("¿Qué tal está el clima hoy?") is False

    sin_just = parsear_respuesta_json_ia(
        json.dumps(
            {
                "diagnostico_tecnico": "¡Hola! Hoy hay 21.5 °C en UTP Pereira.",
                "justificacion_agronomica": "",
                "ajustes_propuestos": {},
                "confianza": 0.98,
                "alertas_consideradas": [],
            }
        ),
        proveedor_ia="gemini:gemini-3.5-flash-lite",
    )
    assert sin_just.justificacion_agronomica == ""

    capturados: list[ContextoDiagnosticoCopiloto] = []

    class WeatherMock:
        proveedor_id = "mock-weather"

        def diagnosticar(self, ctx: ContextoDiagnosticoCopiloto) -> PropuestaCopiloto:
            capturados.append(ctx)
            return PropuestaCopiloto(
                diagnostico_tecnico="Clima enlazado.",
                justificacion_agronomica="",
                ajustes_propuestos={},
                confianza=0.95,
                alertas_consideradas=(),
                proveedor_ia=self.proveedor_id,
            )

    cfg = Configuracion(ruta_db=tmp_path / "clima_copiloto.db")
    cont = construir_contenedor(cfg, sembrar_legacy=False)
    try:
        ahora_ep = tiempo.a_epoch(tiempo.ahora())
        with cont.conexion:
            est = RepositorioEstaciones(cont.conexion).crear(
                "inti-clima",
                "TerraBit-NodoINTI",
                TipoEstacion.TERRABIT_INTI,
                latitud=4.7905,
                longitud=-75.6904,
            )
            RepositorioPronosticoClima(cont.conexion).guardar_lote(
                [
                    PuntoPronosticoClima(
                        estacion_id=est.id,
                        ts_objetivo_epoch=ahora_ep + 600,
                        ts_objetivo_iso=tiempo.a_iso(tiempo.desde_epoch(ahora_ep + 600)),
                        temp_c=21.4,
                        hum_relativa_pct=78.0,
                        lluvia_prob_pct=45.0,
                        lluvia_mm=1.2,
                        viento_ms=1.8,
                        et0_mm=0.22,
                    )
                ]
            )
        cont.copiloto.orquestador = OrquestadorIA(proveedor_override=WeatherMock())
        cont.copiloto.consultar_copiloto(
            "¿Tienes los datos exactos del clima hoy?",
            estacion_id=est.id,
            ahora_epoch=ahora_ep,
        )
        assert len(capturados) == 1
        assert capturados[0].clima_pronostico is not None
        assert capturados[0].clima_pronostico["ahora"]["temp_c"] == pytest.approx(21.4)
        prompt = construir_prompt_contexto_copiloto(capturados[0])
        assert '"clima_actual_y_pronostico"' in prompt
        assert "21.4" in prompt
    finally:
        cont.cerrar()



