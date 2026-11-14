"""Motor determinista de diagnóstico y recalibración (`RuleBasedAdvisor`).

Garantiza que `AquaTerra Matrix` pueda diagnosticar riegos, analizar el pulso de
cualquier familia de estación (`INTI`, `InBeersa`, `Sigatoka`, `Conservación`) y
proponer ajustes de calibración con latencia cero y 100 % offline en campo
(páramos o fincas sin conectividad), además de servir como respaldo automático
cuando Gemini AI Studio u Ollama no estén disponibles.
"""

from __future__ import annotations

from aquaterra.core.copiloto.contratos_ia import ContextoDiagnosticoCopiloto, PropuestaCopiloto
from aquaterra.core.copiloto.cotas_calibracion import (
    PARAMETROS_CALIBRACION_POR_DEFECTO,
    auditar_y_acotar_ajustes,
)
from aquaterra.core.domain.entidades import EfectividadRiego, TipoEstacion


class AsesorDeterministaCopiloto:
    """Sistema experto basado en reglas físicas y agronómicas."""

    proveedor_id: str = "local_reglas"

    @staticmethod
    def _es_charla_conversacional(texto: str) -> bool:
        """Detecta saludos o preguntas abiertas de identidad sin petición técnica."""
        disparadores_tecnicos = (
            "humedad",
            "suelo",
            "vpd",
            "temp",
            "presion",
            "presión",
            "adc",
            "calibr",
            "riego",
            "regue",
            "regué",
            "alerta",
            "nido",
            "colmena",
            "sigatoka",
            "paramo",
            "páramo",
            "ruido",
            "ema",
            "analiza",
            "diagnost",
            "audit",
            "umbral",
            "lluvia",
            "estres",
            "estrés",
            "riesgo",
            "paso la mano",
            "pasó la mano",
            "satur",
            "insuficien",
        )
        if any(tok in texto for tok in disparadores_tecnicos):
            return False
        saludos_o_identidad = (
            "hola",
            "buenos dias",
            "buenos días",
            "buenas tardes",
            "buenas noches",
            "buenas",
            "hey",
            "saludos",
            "que tal",
            "qué tal",
            "como estas",
            "cómo estás",
            "quien eres",
            "quién eres",
            "que haces",
            "qué haces",
            "que puedes",
            "qué puedes",
            "qué mas puedes",
            "qué más puedes",
            "gracias",
            "ayuda",
            "mandarino",
            "sugerencia",
            "sugerencias",
            "que recomiendas",
            "qué recomiendas",
            "al respecto",
            "pasos",
        )
        return any(s in texto for s in saludos_o_identidad)

    def _responder_como_mandarino(
        self, ctx: ContextoDiagnosticoCopiloto, alertas: list[str]
    ) -> PropuestaCopiloto:
        """Genera respuesta cálida y contextualizada (saludo, capacidades o pasos prácticos)."""
        texto = ctx.mensaje_usuario.lower()
        pulso = ctx.resumen_pulso

        if any(tok in texto for tok in ("sugerencia", "recomiend", "al respecto", "pasos", "solucion")):
            if pulso is not None and pulso.alertas_detectadas:
                alerta_txt = "; ".join(pulso.alertas_detectadas[:2])
                if pulso.tipo_estacion.value == "inbeersa_abejas":
                    msg = (
                        f"Para atender {pulso.nombre_estacion} ({alerta_txt}), te recomiendo 3 pasos inmediatos: "
                        "1) inspeccionar sellado térmico y corriente de aire frío en la piquera/tapa del nido; "
                        "2) verificar ventilación si la humedad interna supera 85 % para evitar condensación; "
                        "3) revisar alimentación y cableado I2C/1-Wire del nodo ESP32 por posibles cortes de trama."
                    )
                else:
                    msg = (
                        f"Respecto a {pulso.nombre_estacion} ({alerta_txt}), mis recomendaciones prácticas son: "
                        "1) inspeccionar sensor capacitivo/drenaje en campo antes de relajar umbrales; "
                        "2) confirmar estabilidad de paquetes LoRa/Serial y batería solar; "
                        "3) si el sensor está estable y deseas ajustar umbrales, pídeme 'recalibrar con cotas seguras'."
                    )
            elif ctx.panorama_ecosistema:
                criticas = [
                    n for n in ctx.panorama_ecosistema if n.get("severidad") in ("critico", "atencion")
                ]
                if criticas:
                    foco = criticas[0]
                    msg = (
                        f"Te sugiero priorizar {foco.get('nombre')}, que presenta estado {foco.get('severidad')}. "
                        "Ábrela en la columna izquierda para revisar el sensor afectado, validar si la lectura "
                        "responde a una condición real de campo y ejecutar calibración segura si hace falta."
                    )
                else:
                    msg = (
                        "Tus estaciones activas están estables. Como mantenimiento preventivo te "
                        "sugiero revisar la completitud 24h de cada nodo y validar Open-Meteo antes de regar."
                    )
            else:
                msg = (
                    "Para darte pasos exactos, selecciona una estación a la izquierda o cuéntame si "
                    "revisas suelo, riego automático, colmena Melipona o conectividad del ESP32."
                )
            return PropuestaCopiloto(
                diagnostico_tecnico=msg,
                justificacion_agronomica="",
                ajustes_propuestos={},
                confianza=0.92,
                alertas_consideradas=tuple(dict.fromkeys(alertas)),
                proveedor_ia=self.proveedor_id,
            )

        if any(tok in texto for tok in ("qué puedes", "que puedes", "qué más puedes", "que haces", "qué haces")):
            msg = (
                "Puedo acompañarte en 4 frentes sin mezclar hilos: 1) diagnosticar telemetría viva "
                "(humedad edáfica, VPD, temperatura de nido y lluvia); 2) explicar por qué se activa "
                "un candado antes de regar; 3) proponer recalibraciones auditadas dentro de cotas "
                "metrológicas con rollback en 1 clic; 4) cruzar el estado global de tus estaciones."
            )
            return PropuestaCopiloto(
                diagnostico_tecnico=msg,
                justificacion_agronomica="",
                ajustes_propuestos={},
                confianza=0.95,
                alertas_consideradas=tuple(dict.fromkeys(alertas)),
                proveedor_ia=self.proveedor_id,
            )
        if pulso is not None and pulso.alertas_detectadas:
            primera = pulso.alertas_detectadas[0]
            msg = (
                f"¡Hola! Soy Mandarino, tu copiloto Bio-IoT en AquaTerra Matrix. "
                f"Estoy en línea siguiendo a {pulso.nombre_estacion} y detecté una novedad activa: "
                f"{primera}. Si quieres, la analizamos juntos o revisamos si conviene ajustar umbrales."
            )
        elif pulso is not None:
            resumen_vars: list[str] = []
            for clave in ("suelo_a", "temp_aire", "vpd", "temp_interna_c"):
                est = pulso.variables.get(clave)
                if est is not None:
                    resumen_vars.append(f"{clave}: {est.ultimo_valor:.1f}")
            contexto_txt = f" ({' · '.join(resumen_vars[:3])})" if resumen_vars else ""
            msg = (
                f"¡Hola! Soy Mandarino, tu copiloto agronómico y Bio-IoT. "
                f"Veo a {pulso.nombre_estacion} operando en estado "
                f"{pulso.severidad.value}{contexto_txt}. Puedo explicarte variables de "
                "telemetría, revisar alertas de tus nodos o auditar cambios seguros. "
                "¿Por dónde empezamos?"
            )
        elif ctx.panorama_ecosistema:
            criticas = [
                n for n in ctx.panorama_ecosistema if n.get("severidad") in ("critico", "atencion")
            ]
            if criticas:
                foco = criticas[0]
                alertas_n = foco.get("alertas") or []
                detalle = f": {alertas_n[0]}" if alertas_n else ""
                msg = (
                    f"¡Hola! Soy Mandarino, tu copiloto Bio-IoT en AquaTerra Matrix. "
                    f"Revisando todo tu ecosistema detecté prioridad en {foco.get('nombre')}{detalle}. "
                    "Puedes abrir esa estación en el panel izquierdo o preguntarme por cualquier nodo."
                )
            else:
                msg = (
                    f"¡Hola! Soy Mandarino, tu copiloto inteligente en AquaTerra Matrix. "
                    f"Veo {len(ctx.panorama_ecosistema)} estación(es) activas operando en rango normal. "
                    "Elige una estación a la izquierda para profundizar o pregúntame lo que necesites."
                )
        else:
            msg = (
                "¡Hola! Soy Mandarino, tu copiloto inteligente del ecosistema TerraBit. "
                "Puedo diagnosticar estaciones, interpretar tendencias hídricas o térmicas "
                "y auditar calibraciones seguras. ¿Qué nodo te gustaría revisar hoy?"
            )
        return PropuestaCopiloto(
            diagnostico_tecnico=msg,
            justificacion_agronomica="",
            ajustes_propuestos={},
            confianza=0.95,
            alertas_consideradas=tuple(dict.fromkeys(alertas)),
            proveedor_ia=self.proveedor_id,
        )

    def diagnosticar(self, ctx: ContextoDiagnosticoCopiloto) -> PropuestaCopiloto:
        texto = ctx.mensaje_usuario.lower()
        actuales: dict[str, float] = dict(PARAMETROS_CALIBRACION_POR_DEFECTO)
        for k, v in ctx.parametros_actuales.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                actuales[k] = float(v)

        alertas: list[str] = list(ctx.candados_activos)
        if ctx.resumen_pulso is not None:
            alertas.extend(ctx.resumen_pulso.alertas_detectadas)

        if self._es_charla_conversacional(texto):
            return self._responder_como_mandarino(ctx, alertas)

        ajustes_brutos: dict[str, float] = {}
        bloques_diag: list[str] = []
        bloques_just: list[str] = []

        inc = ctx.ultima_incidencia_riego

        # 1. Detección de exceso de riego / saturación / escorrentía
        palabras_exceso = (
            "pasó la mano",
            "paso la mano",
            "exceso",
            "encharc",
            "saturad",
            "escorrent",
            "demasiada agua",
            "sobre riego",
            "sobrerriego",
        )
        hubo_exceso_texto = any(p in texto for p in palabras_exceso)
        hubo_exceso_sensor = inc is not None and (
            inc.efectividad is EfectividadRiego.EXCESO_PERCOLACION
            or inc.humedad_a_despues > actuales["capacidad_campo_pct"] + 3.0
        )

        if hubo_exceso_texto or hubo_exceso_sensor:
            nueva_lamina = round(actuales["lamina_max_l_m2"] - 1.5, 2)
            nuevo_umbral = round(actuales["umbral_humedad_pct"] - 3.0, 2)
            ajustes_brutos["lamina_max_l_m2"] = nueva_lamina
            ajustes_brutos["umbral_humedad_pct"] = nuevo_umbral

            detalle_inc = (
                f" (último riego llevó Suelo A de {inc.humedad_a_antes:.1f}% a "
                f"{inc.humedad_a_despues:.1f}%, Δθ_A={inc.delta_a_pct:+.1f}%)"
                if inc is not None
                else ""
            )
            bloques_diag.append(
                f"Se identifica condición de sobrerriego / saturación por encima de la "
                f"capacidad de campo óptima{detalle_inc}."
            )
            bloques_just.append(
                f"Se propone reducir la lámina máxima por evento de {actuales['lamina_max_l_m2']:.1f} "
                f"a {nueva_lamina:.1f} L/m² y bajar el umbral de disparo de "
                f"{actuales['umbral_humedad_pct']:.1f}% a {nuevo_umbral:.1f}% para evitar "
                "percolación profunda, hipoxia radicular y pérdida de nutrientes por lixiviación."
            )

        # 2. Detección de riego insuficiente / baja respuesta radicular
        palabras_insuficiente = (
            "insuficiente",
            "faltó agua",
            "falto agua",
            "quedó seco",
            "quedo seco",
            "no subió",
            "no subio",
            "poca agua",
        )
        hubo_insuf_texto = any(p in texto for p in palabras_insuficiente)
        hubo_insuf_sensor = (
            inc is not None
            and inc.efectividad
            in (EfectividadRiego.INFILTRACION_PARCIAL, EfectividadRiego.SIN_RESPUESTA_EN_SUELO)
            and not hubo_exceso_texto
        )

        if hubo_insuf_texto or hubo_insuf_sensor:
            nueva_lamina = round(actuales["lamina_max_l_m2"] + 1.5, 2)
            nuevo_umbral = round(actuales["umbral_humedad_pct"] + 3.0, 2)
            ajustes_brutos["lamina_max_l_m2"] = nueva_lamina
            ajustes_brutos["umbral_humedad_pct"] = nuevo_umbral
            bloques_diag.append(
                "El frente de humectación del riego no logró incrementar suficientemente "
                "la humedad volumétrica en el horizonte radicular A."
            )
            bloques_just.append(
                f"Se sugiere elevar el umbral de activación a {nuevo_umbral:.1f}% y la lámina "
                f"máxima a {nueva_lamina:.1f} L/m² para vencer la histéresis de secado superficial."
            )

        # 3. Deriva o descalibración del sensor capacitivo de suelo (ADC 12 bits)
        palabras_adc = (
            "adc",
            "sensor marca",
            "calibrar sensor",
            "capacitivo",
            "lectura errónea",
            "lectura erronea",
            "marca bajo",
            "marca alto",
        )
        if any(p in texto for p in palabras_adc):
            if "marca bajo" in texto or "marca seco" in texto:
                nuevo_adc_agua = round(actuales["adc_agua"] + 150.0, 2)
                ajustes_brutos["adc_agua"] = nuevo_adc_agua
                bloques_diag.append(
                    "Subestimación de humedad en sonda capacitiva: el suelo presenta humedad "
                    "física superior a la reportada por la curva lineal ADC."
                )
                bloques_just.append(
                    f"En sensores capacitivos (ESP32 ADC 12 bits), incrementar la referencia "
                    f"húmeda `adc_agua` de {actuales['adc_agua']:.0f} a {nuevo_adc_agua:.0f} cuentas "
                    "desplaza la curva hacia arriba para compensar menor acoplamiento dieléctrico "
                    "(por macroporosidad o contacto sonda-suelo)."
                )
            else:
                nuevo_adc_seco = round(actuales["adc_seco"] - 150.0, 2)
                ajustes_brutos["adc_seco"] = nuevo_adc_seco
                bloques_diag.append(
                    "Se detecta solicitud de ajuste metrológico sobre la curva de conversión ADC "
                    "del sensor capacitivo de suelo."
                )
                bloques_just.append(
                    f"Se ajusta la cota seca `adc_seco` de {actuales['adc_seco']:.0f} a "
                    f"{nuevo_adc_seco:.0f} cuentas manteniendo una ventana dinámica > 400 cuentas "
                    "respecto a `adc_agua`."
                )

        # 4. Ruido eléctrico en lecturas analógicas -> ajuste de filtro EMA
        palabras_ruido = ("ruido", "oscila", "picos", "inestable", "ema", "filtro")
        if any(p in texto for p in palabras_ruido):
            nuevo_alpha = round(max(0.05, actuales["ema_alpha"] - 0.08), 3)
            ajustes_brutos["ema_alpha"] = nuevo_alpha
            bloques_diag.append(
                "Presencia de fluctuaciones de alta frecuencia (ruido eléctrico/EMI) en el canal ADC."
            )
            bloques_just.append(
                f"Se reduce el factor `ema_alpha` del filtro de media móvil exponencial de "
                f"{actuales['ema_alpha']:.2f} a {nuevo_alpha:.2f}, incrementando la constante de "
                "tiempo de suavizado sin añadir retardos bloqueantes en el ESP32."
            )

        # 5. Contexto específico por familia de estación (InBeersa / Sigatoka / Conservación)
        if ctx.resumen_pulso is not None:
            pulso = ctx.resumen_pulso
            if pulso.tipo_estacion is TipoEstacion.INBEERSA and (
                "abeja" in texto or "colmena" in texto or "nido" in texto or not bloques_diag
            ):
                ind_b = pulso.inbeersa
                if ind_b is not None:
                    bloques_diag.append(
                        f"Estado bio-climático InBeersa ({pulso.codigo_estacion}): "
                        f"ΔT(nido-amb)={ind_b.delta_temp_medio_c}°C, "
                        f"homeostasis={ind_b.en_rango_homeostasis}, "
                        f"audios={ind_b.conteo_audios_bioacusticos}."
                    )
                    if "umbral" in texto or "frío" in texto or "frio" in texto:
                        nuevo_t_nido = round(actuales["temp_nido_min_c"] + 0.8, 2)
                        ajustes_brutos["temp_nido_min_c"] = nuevo_t_nido
                        bloques_just.append(
                            f"Se eleva `temp_nido_min_c` a {nuevo_t_nido}°C para anticipar "
                            "alertas de enfriamiento del disco de cría de Melipona eburnea."
                        )

            elif pulso.tipo_estacion is TipoEstacion.SIGATOKA and (
                "sigatoka" in texto or "hoja" in texto or "hongo" in texto or not bloques_diag
            ):
                ind_s = pulso.sigatoka
                if ind_s is not None:
                    bloques_diag.append(
                        f"Vigilancia fitosanitaria Sigatoka ({pulso.codigo_estacion}): "
                        f"{ind_s.horas_humectacion_foliar_24h:.1f} h de humectación foliar en 24h "
                        f"(alerta fúngica={ind_s.alerta_infeccion_fungica})."
                    )
                    if "sensible" in texto or "tempran" in texto or "preventiv" in texto:
                        nuevo_mojado = round(actuales["umbral_mojado_foliar_pct"] - 5.0, 2)
                        ajustes_brutos["umbral_mojado_foliar_pct"] = nuevo_mojado
                        bloques_just.append(
                            f"Se reduce `umbral_mojado_foliar_pct` a {nuevo_mojado}% para "
                            "endurecer la detección preventiva de película de agua en hoja."
                        )

        # 6. Si fue una consulta general / resumen sin disparadores de recalibración
        if not bloques_diag:
            if ctx.resumen_pulso is not None:
                bloques_diag.append(
                    f"Diagnóstico general de {ctx.resumen_pulso.nombre_estacion} "
                    f"[{ctx.resumen_pulso.severidad.value.upper()}]: "
                    f"{ctx.resumen_pulso.diagnostico_determinista}"
                )
            else:
                bloques_diag.append(
                    "Estación/parcela en seguimiento operativo. Parámetros de calibración dentro "
                    "de rangos nominales."
                )

        if not bloques_just:
            if ajustes_brutos:
                bloques_just.append(
                    "Ajustes calculados de forma determinista respetando las cotas físicas del nodo."
                )
            else:
                bloques_just.append(
                    "No se requieren cambios en los parámetros de calibración actuales para esta "
                    "consulta; los umbrales vigentes operan dentro de márgenes seguros."
                )

        auditoria = auditar_y_acotar_ajustes(ajustes_brutos, actuales)
        return PropuestaCopiloto(
            diagnostico_tecnico=" ".join(bloques_diag),
            justificacion_agronomica=" ".join(bloques_just),
            ajustes_propuestos=auditoria.ajustes_seguros,
            confianza=0.92 if ajustes_brutos else 0.88,
            alertas_consideradas=tuple(dict.fromkeys(alertas)),
            proveedor_ia=self.proveedor_id,
        )
