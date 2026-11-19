import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import {
  BookOpen,
  CloudSun,
  Compass,
  FileBarChart2,
  History,
  Home,
  MessageCircle,
  MessageSquare,
  MessageSquarePlus,
  Send,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import { Badge, SeveridadBadge } from "../components/common/Badge";
import { MandarinoAvatar } from "../components/common/MandarinoAvatar";
import { ChatMessageList } from "../components/copilot/ChatMessageList";
import { ProactiveBoundsPanel } from "../components/copilot/ProactiveBoundsPanel";
import { StationSidebar } from "../components/copilot/StationSidebar";
import type {
  CanalChatId,
  MensajeChat,
  TabDerecha,
} from "../components/copilot/types";
import { useApp } from "../context/AppContext";
import { api, ApiError } from "../lib/api";
import { etiquetarProveedorIA, limpiarTextoCopiloto } from "../lib/formatters";
import type {
  ConsultarCopilotoResponse,
  EstadoCopilotoResponse,
  InteraccionCopiloto,
  Parcela,
  PronosticoPunto,
} from "../types/aquaterra";

interface TarjetaPrincipal {
  id: string;
  tipo: "chat" | "reporte";
  etiqueta: string;
  titulo: string;
  detalle: string;
  prompt: string;
}

interface PasoDidacticoMandarino {
  id: string;
  titulo: string;
  resumen: string;
  ejemplo: string;
  consejo: string;
  prompts: { etiqueta: string; texto: string }[];
}

const STORAGE_CHATS_KEY = "aquaterra_mandarino_chats_v1";
const VENTANA_MENSAJES_INICIAL = 30;
const PASO_CARGA_ANTIGUOS = 25;

const PASOS_DIDACTICOS: PasoDidacticoMandarino[] = [
  {
    id: "diagnostico",
    titulo: "1. Leer Telemetría",
    resumen:
      "Mandarino cruza las últimas 24 horas del nodo seleccionado (suelo, VPD, temperatura de nido o lluvia) sin mezclar chats de otras estaciones.",
    ejemplo:
      "Útil para entender cambios de humedad o tendencias antes de ir al cultivo.",
    consejo:
      "Luego puedes repreguntarle en el mismo hilo: «¿qué sugerencias prácticas me das?»",
    prompts: [
      {
        etiqueta: "Resumen claro 24h",
        texto:
          "¿Cómo ha estado esta estación en las últimas 24 horas y qué debo vigilar?",
      },
      {
        etiqueta: "Sugerencias en campo",
        texto:
          "¿Qué sugerencias prácticas de revisión en campo me das según el estado actual?",
      },
    ],
  },
  {
    id: "calibracion",
    titulo: "2. Recalibrar Cotas",
    resumen:
      "Calcula ajustes seguros de humedad, lluvia y lámina auditados contra límites metrológicos reales, con tabla comparativa y rollback en 1 clic.",
    ejemplo:
      "Úsalo cuando notes riego excesivo, sensor desfasado o riesgo por lluvia.",
    consejo:
      "Ningún parámetro toca tu nodo sin que presiones el botón «Aplicar».",
    prompts: [
      {
        etiqueta: "Auditar umbrales",
        texto:
          "Audita los límites físicos y umbrales de calibración actuales y muéstralos en una tabla.",
      },
      {
        etiqueta: "Proteger ante lluvia",
        texto:
          "Evalúa si conviene ajustar umbrales ante riesgo de lluvia o saturación del suelo.",
      },
    ],
  },
  {
    id: "ecosistema",
    titulo: "3. Módulos Aislados",
    resumen:
      "Cada nodo tiene su módulo independiente y su sección en el historial. Mandarino conserva conciencia global sin contaminar las conversaciones entre sí.",
    ejemplo:
      "Desde Asistente Global puedes pedir prioridades generales o conversar libremente.",
    consejo:
      "Usa «Inicio Mandarino» en la barra superior en cualquier momento para regresar aquí.",
    prompts: [
      {
        etiqueta: "Panorama de la finca",
        texto:
          "Dame un panorama general rápido de todas mis estaciones activas y prioridades hoy.",
      },
      {
        etiqueta: "¿Qué puedes hacer?",
        texto: "Hola Mandarino, ¿qué más puedes hacer hoy por mí en este proyecto?",
      },
    ],
  },
];

function canalKey(canal: CanalChatId): string {
  return canal === "general" ? "general" : `est-${canal}`;
}

function leerChatsGuardados(): Record<string, MensajeChat[]> {
  try {
    const raw = window.sessionStorage.getItem(STORAGE_CHATS_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, MensajeChat[]>;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function dividirTextoGuardado(raw: string): {
  principal: string;
  recomendacion: string;
} {
  const limpio = limpiarTextoCopiloto(raw);
  const partes = limpio.split(/\n+Justificación:\s*/i);
  const principal = (partes[0] ?? "").trim();
  const recomendacion = (partes[1] ?? "").trim();
  return { principal, recomendacion };
}

function convertirHistorialAMensajes(
  itemsCronologicos: InteraccionCopiloto[],
  nombrePorEstacion: Map<number, string>
): MensajeChat[] {
  const salida: MensajeChat[] = [];
  for (const item of itemsCronologicos) {
    const estNom =
      item.estacion_id !== null
        ? nombrePorEstacion.get(item.estacion_id) ?? `Estación #${item.estacion_id}`
        : "Ecosistema Global";
    const canalOrigen: CanalChatId =
      item.estacion_id !== null ? item.estacion_id : "general";

    salida.push({
      id: `hist-u-${item.id}`,
      autor: "usuario",
      textoPrincipal: item.mensaje_usuario,
      estacionEtiqueta: estNom,
      canalOrigen,
      tsIso: item.ts_iso,
    });
    const { principal, recomendacion } = dividirTextoGuardado(
      item.diagnostico_ia
    );
    salida.push({
      id: `hist-b-${item.id}`,
      autor: "mandarino",
      textoPrincipal: principal,
      recomendacion,
      proveedor: item.proveedor_ia,
      ajustesSeguros:
        (item.ajustes_propuestos as Record<string, number> | null) ?? undefined,
      interaccionId: item.id,
      calibracionAplicadaId: item.calibracion_aplicada_id,
      estacionEtiqueta: estNom,
      canalOrigen,
      promptOrigen: item.mensaje_usuario,
      rawJson: {
        interaccion_id: item.id,
        estacion_id: item.estacion_id,
        proveedor_ia: item.proveedor_ia,
        ajustes_propuestos: item.ajustes_propuestos ?? {},
        calibracion_aplicada_id: item.calibracion_aplicada_id,
        ts_iso: item.ts_iso,
      },
      tsIso: item.ts_iso,
    });
  }
  return salida;
}

export function CopilotPage() {
  const {
    usuario,
    estaciones,
    entradasRadar,
    setEstacionActivaId,
    estadoSistema,
  } = useApp();
  const esAdmin = usuario?.rol === "admin";
  const primerNombre =
    (usuario?.nombre ?? usuario?.usuario ?? "Operador")
      .trim()
      .split(/\s+/)[0] || "Operador";

  const [canalActivo, setCanalActivo] = useState<CanalChatId>("general");
  const [parcelas, setParcelas] = useState<Parcela[]>([]);
  const [parcelaId, setParcelaId] = useState<number | null>(null);
  const [estado, setEstado] = useState<EstadoCopilotoResponse | null>(null);
  const [cargandoEstado, setCargandoEstado] = useState(true);
  const [climaResumen, setClimaResumen] = useState<PronosticoPunto | null>(null);

  // Hilos segmentados persistentes en la sesión actual
  const [chatsPorCanal, setChatsPorCanal] = useState<
    Record<string, MensajeChat[]>
  >(() => leerChatsGuardados());
  const [limiteMensajesPorCanal, setLimiteMensajesPorCanal] = useState<
    Record<string, number>
  >({});

  const [mensaje, setMensaje] = useState("");
  const [consultandoCanalKey, setConsultandoCanalKey] = useState<string | null>(
    null
  );

  const [tabDerecha, setTabDerecha] = useState<TabDerecha>("proactivo");
  const [vistaCentro, setVistaCentro] = useState<"auto" | "inicio" | "chat">(
    "auto"
  );
  const [guiaDidacticaIdx, setGuiaDidacticaIdx] = useState<number>(0);
  const [ultimaConsulta, setUltimaConsulta] =
    useState<ConsultarCopilotoResponse["respuesta"] | null>(null);
  const [aplicandoId, setAplicandoId] = useState<number | null>(null);
  const [revirtiendo, setRevirtiendo] = useState(false);

  const [scrollTriggerToken, setScrollTriggerToken] = useState(0);
  const [mensajeDestacadoId, setMensajeDestacadoId] = useState<string | null>(
    null
  );
  const contenedorScrollRef = useRef<HTMLDivElement | null>(null);

  const claveActiva = canalKey(canalActivo);
  const estacionFocalId = canalActivo === "general" ? null : canalActivo;
  const consultandoActual = consultandoCanalKey === claveActiva;

  useEffect(() => {
    try {
      window.sessionStorage.setItem(
        STORAGE_CHATS_KEY,
        JSON.stringify(chatsPorCanal)
      );
    } catch {
      // Ignorar si sessionStorage supera cuota
    }
  }, [chatsPorCanal]);

  const nombrePorEstacion = useMemo(
    () => new Map(estaciones.map((e) => [e.id, e.nombre])),
    [estaciones]
  );

  const estacionFocalObj = useMemo(
    () =>
      estacionFocalId !== null
        ? estaciones.find((e) => e.id === estacionFocalId) ?? null
        : null,
    [estaciones, estacionFocalId]
  );

  const entradaFocal = useMemo(
    () =>
      estacionFocalId !== null
        ? entradasRadar.find((e) => e.estacion.id === estacionFocalId) ?? null
        : null,
    [entradasRadar, estacionFocalId]
  );

  const parcelasDelCanal = useMemo(() => {
    if (estacionFocalId === null) return parcelas;
    return parcelas.filter(
      (p) => p.estacion_id === estacionFocalId || p.estacion_id === null
    );
  }, [parcelas, estacionFocalId]);

  useEffect(() => {
    api
      .get<{ parcelas: Parcela[] }>("/api/parcelas")
      .then((r) => setParcelas(r.parcelas ?? []))
      .catch(() => setParcelas([]));
  }, []);

  const cargarEstadoCopiloto = useCallback(async () => {
    setCargandoEstado(true);
    try {
      const qs = new URLSearchParams();
      if (estacionFocalId !== null) {
        qs.set("estacion_id", String(estacionFocalId));
      } else {
        qs.set("solo_sin_estacion", "true");
      }
      if (parcelaId !== null) qs.set("parcela_id", String(parcelaId));
      const resp = await api.get<EstadoCopilotoResponse>(
        `/api/copiloto/estado?${qs.toString()}`
      );
      setEstado(resp);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Error cargando estado de Mandarino."
      );
    } finally {
      setCargandoEstado(false);
    }
  }, [estacionFocalId, parcelaId]);

  useEffect(() => {
    void cargarEstadoCopiloto();
  }, [cargarEstadoCopiloto]);

  useEffect(() => {
    const estClimaId =
      estacionFocalId ?? (estaciones.length > 0 ? estaciones[0].id : null);
    if (estClimaId === null) return;
    let cancelado = false;
    api
      .get<{ puntos: PronosticoPunto[] }>(
        `/api/estaciones/${estClimaId}/pronostico?horas=12`
      )
      .then((res) => {
        if (cancelado) return;
        const pts = res.puntos ?? [];
        if (pts.length === 0) {
          setClimaResumen(null);
          return;
        }
        const ahoraSec = Math.floor(Date.now() / 1000);
        const cercano = pts.reduce((mejor, p) =>
          Math.abs(p.ts_objetivo_epoch - ahoraSec) <
          Math.abs(mejor.ts_objetivo_epoch - ahoraSec)
            ? p
            : mejor
        );
        setClimaResumen(cercano);
      })
      .catch(() => {
        if (!cancelado) setClimaResumen(null);
      });
    return () => {
      cancelado = true;
    };
  }, [estacionFocalId, estaciones]);

  const mensajesCanal = useMemo(
    () => chatsPorCanal[claveActiva] ?? [],
    [chatsPorCanal, claveActiva]
  );

  const limiteVisible =
    limiteMensajesPorCanal[claveActiva] ?? VENTANA_MENSAJES_INICIAL;

  const mensajesVentana = useMemo(() => {
    if (mensajesCanal.length <= limiteVisible) return mensajesCanal;
    return mensajesCanal.slice(mensajesCanal.length - limiteVisible);
  }, [mensajesCanal, limiteVisible]);

  const cantidadOcultaArriba = Math.max(
    0,
    mensajesCanal.length - mensajesVentana.length
  );

  const seleccionarCanal = (destino: CanalChatId) => {
    setCanalActivo(destino);
    setParcelaId(null);
    setVistaCentro("auto");
    setMensajeDestacadoId(null);
    setScrollTriggerToken((t) => t + 1);
    if (destino !== "general") {
      setEstacionActivaId(destino);
    }
  };

  // Estrictamente 2 tarjetas limpias en la vista principal: Chat Normal y Reporte Técnico
  const tarjetasPrincipales = useMemo<TarjetaPrincipal[]>(() => {
    if (estacionFocalObj) {
      return [
        {
          id: `chat-normal-${canalActivo}`,
          tipo: "chat",
          etiqueta: "Chat Normal",
          titulo: `Conversar sobre ${estacionFocalObj.nombre}`,
          detalle:
            "Diálogo ágil y contextualizado para resolver dudas o pedir recomendaciones prácticas.",
          prompt: `Hola Mandarino, cuéntame de forma clara cómo ves a ${estacionFocalObj.nombre} hoy.`,
        },
        {
          id: `reporte-est-${canalActivo}`,
          tipo: "reporte",
          etiqueta: "Reporte Técnico",
          titulo: `Reporte 24h y cotas de ${estacionFocalObj.nombre}`,
          detalle:
            "Diagnóstico estructurado en tabla con variables medidas, alertas y límites físicos.",
          prompt: `Genera un reporte técnico completo de ${estacionFocalObj.nombre} con tabla de variables y evaluación de cotas seguras.`,
        },
      ];
    }

    return [
      {
        id: "chat-normal-global",
        tipo: "chat",
        etiqueta: "Chat Normal",
        titulo: "Iniciar charla con Mandarino",
        detalle:
          "Conversa de forma natural con tu copiloto agrícola sobre cualquier duda o idea de campo.",
        prompt: "Hola Mandarino, preséntate brevemente y dime en qué nos enfocamos hoy.",
      },
      {
        id: "reporte-global-ecosistema",
        tipo: "reporte",
        etiqueta: "Reporte Ecosistema",
        titulo: "Reporte general de estaciones",
        detalle:
          "Resumen comparativo de tus nodos activos con severidad y prioridades agronómicas.",
        prompt:
          "Genera un reporte estructurado del estado actual de todas las estaciones activas y qué nodo merece atención primero.",
      },
    ];
  }, [canalActivo, estacionFocalObj]);

  const enviarConsulta = async (
    textoCustom?: string,
    canalOverride?: CanalChatId
  ) => {
    const q = (textoCustom ?? mensaje).trim();
    if (!q || consultandoCanalKey !== null) return;

    const canalObjetivo =
      canalOverride !== undefined ? canalOverride : canalActivo;
    const keyObjetivo = canalKey(canalObjetivo);
    const estIdEnviar = canalObjetivo === "general" ? null : canalObjetivo;

    if (canalObjetivo !== canalActivo) {
      seleccionarCanal(canalObjetivo);
    }

    const estEtiqueta =
      estIdEnviar !== null
        ? nombrePorEstacion.get(estIdEnviar) ?? `Estación #${estIdEnviar}`
        : "Ecosistema Global";

    const msgUsuario: MensajeChat = {
      id: `usr-${Date.now()}`,
      autor: "usuario",
      textoPrincipal: q,
      estacionEtiqueta: estEtiqueta,
      canalOrigen: canalObjetivo,
      tsIso: new Date().toISOString(),
    };

    setMensajeDestacadoId(null);
    setVistaCentro("chat");
    setChatsPorCanal((prev) => ({
      ...prev,
      [keyObjetivo]: [...(prev[keyObjetivo] ?? []), msgUsuario],
    }));
    setScrollTriggerToken((t) => t + 1);
    if (!textoCustom) setMensaje("");
    setConsultandoCanalKey(keyObjetivo);

    try {
      const resp = await api.post<ConsultarCopilotoResponse>(
        "/api/copiloto/consultar",
        {
          mensaje: q,
          estacion_id: estIdEnviar,
          parcela_id: estIdEnviar !== null ? parcelaId : null,
          aplicar_ajustes: false,
        }
      );
      const r = resp.respuesta;
      setUltimaConsulta(r);

      const ajustesSeg = r.auditoria.ajustes_seguros ?? {};
      const msgBot: MensajeChat = {
        id: `bot-${r.interaccion.id}-${Date.now()}`,
        autor: "mandarino",
        textoPrincipal: limpiarTextoCopiloto(r.propuesta.diagnostico_tecnico),
        recomendacion: limpiarTextoCopiloto(
          r.propuesta.justificacion_agronomica ?? ""
        ).trim(),
        proveedor: r.propuesta.proveedor_ia,
        confianza: r.propuesta.confianza,
        alertas: r.propuesta.alertas_consideradas ?? [],
        ajustesSeguros: ajustesSeg,
        recortes: r.auditoria.recortes_aplicados ?? [],
        advertencias: r.auditoria.advertencias_seguridad ?? [],
        clavesRechazadas: r.auditoria.claves_rechazadas ?? [],
        interaccionId: r.interaccion.id,
        calibracionAplicadaId: r.interaccion.calibracion_aplicada_id,
        estacionEtiqueta: estEtiqueta,
        canalOrigen: canalObjetivo,
        promptOrigen: q,
        rawJson: r as unknown as Record<string, unknown>,
        tsIso: r.interaccion.ts_iso,
      };
      setChatsPorCanal((prev) => ({
        ...prev,
        [keyObjetivo]: [...(prev[keyObjetivo] ?? []), msgBot],
      }));
      setScrollTriggerToken((t) => t + 1);
      if (Object.keys(ajustesSeg).length > 0) {
        setTabDerecha("cotas");
      }
      await cargarEstadoCopiloto();
    } catch (err) {
      const detalle =
        err instanceof ApiError
          ? err.detail
          : "No logré conectar con el motor de análisis.";
      toast.error(detalle);
      setChatsPorCanal((prev) => ({
        ...prev,
        [keyObjetivo]: [
          ...(prev[keyObjetivo] ?? []),
          {
            id: `err-${Date.now()}`,
            autor: "mandarino",
            textoPrincipal: `Tuve un inconveniente procesando esa consulta: ${detalle}.`,
            proveedor: "sistema",
            estacionEtiqueta: estEtiqueta,
            canalOrigen: canalObjetivo,
            promptOrigen: q,
            tsIso: new Date().toISOString(),
          },
        ],
      }));
      setScrollTriggerToken((t) => t + 1);
    } finally {
      setConsultandoCanalKey(null);
    }
  };

  const handleRetomarHistorialCanal = () => {
    const historial = estado?.historial ?? [];
    if (historial.length === 0) return;
    const cronologico = [...historial].reverse();
    const convertidos = convertirHistorialAMensajes(
      cronologico,
      nombrePorEstacion
    );
    setMensajeDestacadoId(null);
    setVistaCentro("chat");
    setChatsPorCanal((prev) => ({
      ...prev,
      [claveActiva]: convertidos,
    }));
    setScrollTriggerToken((t) => t + 1);
  };

  const handleAbrirHistorialDeEstacion = async (
    interaccion: InteraccionCopiloto
  ) => {
    const destino: CanalChatId =
      interaccion.estacion_id !== null ? interaccion.estacion_id : "general";
    const keyDest = canalKey(destino);
    seleccionarCanal(destino);

    try {
      const qs = new URLSearchParams();
      if (destino !== "general") {
        qs.set("estacion_id", String(destino));
      } else {
        qs.set("solo_sin_estacion", "true");
      }
      const resp = await api.get<EstadoCopilotoResponse>(
        `/api/copiloto/estado?${qs.toString()}`
      );
      setEstado(resp);
      const convertidos = convertirHistorialAMensajes(
        [...(resp.historial ?? [])].reverse(),
        nombrePorEstacion
      );
      // Asegurar que la ventana muestre al menos hasta el mensaje seleccionado
      const idxObjetivo = convertidos.findIndex(
        (m) => m.id === `hist-u-${interaccion.id}`
      );
      if (idxObjetivo >= 0) {
        const desdeObjetivo = convertidos.length - idxObjetivo + 4;
        if (desdeObjetivo > VENTANA_MENSAJES_INICIAL) {
          setLimiteMensajesPorCanal((prev) => ({
            ...prev,
            [keyDest]: desdeObjetivo,
          }));
        }
        setMensajeDestacadoId(`hist-u-${interaccion.id}`);
      } else {
        setMensajeDestacadoId(null);
      }

      setVistaCentro("chat");
      setChatsPorCanal((prev) => ({
        ...prev,
        [keyDest]: convertidos,
      }));
      setScrollTriggerToken((t) => t + 1);
    } catch {
      toast.error("No se pudo abrir el historial de esa estación.");
    }
  };

  const handleRegenerar = (msgBot: MensajeChat) => {
    let prompt = msgBot.promptOrigen;
    if (!prompt) {
      const lista = chatsPorCanal[claveActiva] ?? [];
      const idx = lista.findIndex((x) => x.id === msgBot.id);
      for (let i = idx - 1; i >= 0; i -= 1) {
        if (lista[i].autor === "usuario") {
          prompt = lista[i].textoPrincipal;
          break;
        }
      }
    }
    if (!prompt) {
      toast.info("No se encontró el prompt original para regenerar.");
      return;
    }
    void enviarConsulta(prompt, msgBot.canalOrigen ?? canalActivo);
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    void enviarConsulta();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      void enviarConsulta();
    }
  };

  const handleAplicarPropuesta = async (
    interaccionId: number,
    keyHilo: string
  ) => {
    setAplicandoId(interaccionId);
    try {
      const resp = await api.post<{ version: { id: number; version: number } }>(
        "/api/copiloto/aplicar",
        {
          interaccion_id: interaccionId,
          motivo_adicional: "Aprobado por operador/admin en Mandarino IA",
        }
      );
      toast.success(
        `Calibración aplicada correctamente (Versión v${resp.version.version}).`
      );
      setChatsPorCanal((prev) => ({
        ...prev,
        [keyHilo]: (prev[keyHilo] ?? []).map((m) =>
          m.interaccionId === interaccionId
            ? { ...m, calibracionAplicadaId: resp.version.id ?? 1 }
            : m
        ),
      }));
      await cargarEstadoCopiloto();
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "No se pudieron aplicar ajustes."
      );
    } finally {
      setAplicandoId(null);
    }
  };

  const handleRollback = async (versionId?: number) => {
    setRevirtiendo(true);
    try {
      const resp = await api.post<{ version: { version: number } }>(
        "/api/copiloto/rollback",
        {
          estacion_id: estacionFocalId,
          parcela_id: parcelaId,
          version_id_destino: versionId ?? null,
        }
      );
      toast.success(
        `Calibración revertida correctamente a versión v${resp.version.version}.`
      );
      await cargarEstadoCopiloto();
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "Error ejecutando rollback."
      );
    } finally {
      setRevirtiendo(false);
    }
  };

  const cotas = Object.values(estado?.catalogo_cotas ?? {});
  const ajustesSegurosInspector = ultimaConsulta?.auditoria.ajustes_seguros ?? {};
  const recortesMap = new Map(
    (ultimaConsulta?.auditoria.recortes_aplicados ?? []).map((r) => [
      r.clave,
      r,
    ])
  );

  const motorActivoNombre = etiquetarProveedorIA(
    estadoSistema?.ia_proveedor === "gemini" ||
      estadoSistema?.ia_gemini_configurado
      ? "gemini"
      : estadoSistema?.ia_ollama_disponible
      ? "ollama"
      : "local_reglas"
  );

  const alertasEcosistema = useMemo(
    () =>
      entradasRadar.filter(
        (e) =>
          e.severidad === "critico" ||
          e.severidad === "atencion" ||
          e.alertas_activas > 0
      ),
    [entradasRadar]
  );

  const historialGlobalReciente = estado?.historial_reciente_global ?? [];
  const mostrarInicio =
    vistaCentro === "inicio" ||
    (vistaCentro === "auto" && mensajesCanal.length === 0);
  const pasoDidacticoActivo =
    PASOS_DIDACTICOS[guiaDidacticaIdx] ?? PASOS_DIDACTICOS[0];

  const solucionesVersiones = estado?.versiones_globales ?? estado?.versiones ?? [];
  const solucionesAplicadasCount = historialGlobalReciente.filter(
    (h) => h.calibracion_aplicada_id !== null
  ).length;

  return (
    <div className="space-y-4">
      {/* Cabecera de estudio Mandarino IA */}
      <header className="surface-card flex flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-5">
        <div className="flex items-center gap-3">
          <MandarinoAvatar size="sm" pensando={consultandoActual} />
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-lg font-bold tracking-tight text-[var(--text-primary)]">
                Mandarino IA Studio
              </h1>
              <span className="inline-flex items-center gap-1 rounded-full border border-[var(--mandarino-border)] bg-[var(--mandarino-soft)] px-2.5 py-0.5 text-[11px] font-semibold text-[#fb923c]">
                <span
                  className="h-1.5 w-1.5 rounded-full bg-[#2ecc71]"
                  aria-hidden="true"
                />
                {motorActivoNombre}
              </span>
              {canalActivo === "general" ? (
                <Badge tono="neutral">Asistente Global SalviaBIoT</Badge>
              ) : (
                entradaFocal && (
                  <SeveridadBadge severidad={entradaFocal.severidad} />
                )
              )}
              {climaResumen && climaResumen.temp_c !== undefined && climaResumen.temp_c !== null && (
                <span
                  title="Pronóstico meteorológico enlazado vía Open-Meteo"
                  className="inline-flex items-center gap-1 rounded-full border border-[#38bdf8]/35 bg-[#38bdf8]/10 px-2.5 py-0.5 text-[11px] font-medium text-[#38bdf8]"
                >
                  <CloudSun className="h-3 w-3" aria-hidden="true" />
                  {climaResumen.temp_c.toFixed(1)} °C
                  {climaResumen.lluvia_prob_pct !== undefined &&
                  climaResumen.lluvia_prob_pct !== null
                    ? ` · ${Math.round(climaResumen.lluvia_prob_pct)}% lluvia`
                    : ""}
                </span>
              )}
            </div>
            <p className="text-xs text-[var(--text-secondary)]">
              Motor cognitivo modular con memoria aislada por estación y visión global SalviaBIoT
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() =>
              setVistaCentro((prev) =>
                prev === "inicio" && mensajesCanal.length > 0 ? "chat" : "inicio"
              )
            }
            aria-label="Ir al apartado principal de Mandarino"
            className={`inline-flex h-8 items-center gap-1.5 rounded-xl border px-3 text-xs font-semibold transition-all ${
              mostrarInicio
                ? "border-[#f97316] bg-[var(--mandarino-soft)] text-[#fb923c]"
                : "border-[var(--border-subtle)] bg-[var(--bg-canvas)] text-[var(--text-secondary)] hover:border-[#f5b041]/60 hover:text-[#f5b041]"
            }`}
          >
            <Home className="h-3.5 w-3.5" aria-hidden="true" />
            Inicio Mandarino
          </button>

          {estacionFocalId !== null && parcelasDelCanal.length > 0 && (
            <select
              value={parcelaId ?? ""}
              onChange={(e) =>
                setParcelaId(e.target.value ? Number(e.target.value) : null)
              }
              aria-label="Parcela en contexto de estación"
              className="h-8 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-canvas)] px-2.5 text-xs text-[var(--text-primary)]"
            >
              <option value="">Toda la estación</option>
              {parcelasDelCanal.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nombre} ({p.cultivo})
                </option>
              ))}
            </select>
          )}

          {mensajesCanal.length > 0 && (
            <button
              type="button"
              onClick={() => {
                setVistaCentro("inicio");
                setMensajeDestacadoId(null);
                setChatsPorCanal((prev) => ({
                  ...prev,
                  [claveActiva]: [],
                }));
              }}
              className="inline-flex h-8 items-center gap-1.5 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-canvas)] px-3 text-xs font-medium text-[var(--text-secondary)] hover:border-[#f5b041]/60 hover:text-[#f5b041]"
            >
              <MessageSquarePlus className="h-3.5 w-3.5" aria-hidden="true" />
              Limpiar hilo
            </button>
          )}
        </div>
      </header>

      {/* Arquitectura Modular 3 Columnas */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <StationSidebar
          estaciones={estaciones}
          entradasRadar={entradasRadar}
          canalActivo={canalActivo}
          chatsPorCanal={chatsPorCanal}
          onSeleccionarCanal={seleccionarCanal}
        />

        {/* COLUMNA CENTRAL (6 cols): Ventana Fija con Inicio Didáctico o Chat Enriquecido */}
        <section
          aria-label="Conversación activa con Mandarino"
          className="surface-card relative flex h-[640px] flex-col overflow-hidden xl:col-span-6 xl:h-[calc(100dvh-13rem)] xl:min-h-[540px] xl:max-h-[820px]"
        >
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -top-24 left-1/2 h-56 w-[480px] -translate-x-1/2 rounded-full bg-[radial-gradient(circle,rgba(249,115,22,0.13)_0%,transparent_72%)]"
          />

          {/* Subbarra de contexto y navegación */}
          <div className="relative z-10 flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-[var(--border-subtle)] px-4 py-2.5 text-xs">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-[var(--text-primary)]">
                {estacionFocalObj
                  ? `Hilo: ${estacionFocalObj.nombre}`
                  : "Asistente Global SalviaBIoT"}
              </span>
              {estacionFocalObj && (
                <span className="hidden font-mono text-[11px] text-[var(--text-muted)] sm:inline">
                  · v{estado?.version_actual ?? 0}
                </span>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-1.5">
              {mensajesCanal.length > 0 && (
                <div
                  role="group"
                  aria-label="Navegación interna de Mandarino"
                  className="inline-flex rounded-full border border-[var(--border-subtle)] bg-[var(--bg-canvas)] p-0.5"
                >
                  <button
                    type="button"
                    onClick={() => setVistaCentro("inicio")}
                    className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium transition-colors ${
                      mostrarInicio
                        ? "bg-[#f97316] text-white"
                        : "text-[var(--text-secondary)] hover:text-[#f5b041]"
                    }`}
                  >
                    <Compass className="h-3 w-3" aria-hidden="true" />
                    Principal
                  </button>
                  <button
                    type="button"
                    onClick={() => setVistaCentro("chat")}
                    className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium transition-colors ${
                      !mostrarInicio
                        ? "bg-[#f97316] text-white"
                        : "text-[var(--text-secondary)] hover:text-[#f5b041]"
                    }`}
                  >
                    <MessageSquare className="h-3 w-3" aria-hidden="true" />
                    Chat ({mensajesCanal.length})
                  </button>
                </div>
              )}

              {(estado?.historial?.length ?? 0) > 0 && mensajesCanal.length === 0 && (
                <button
                  type="button"
                  onClick={handleRetomarHistorialCanal}
                  className="inline-flex items-center gap-1 rounded-full border border-[#f5b041]/45 bg-[#f5b041]/10 px-2.5 py-1 text-[11px] font-medium text-[#f5b041] hover:bg-[#f5b041]/20"
                >
                  <History className="h-3 w-3" aria-hidden="true" />
                  Cargar historial ({estado?.historial.length})
                </button>
              )}
            </div>
          </div>

          {mostrarInicio ? (
            <div className="relative z-10 flex-1 min-h-0 overflow-y-auto px-4 py-4 sm:px-6">
              <div className="mx-auto flex max-w-2xl flex-col items-center py-2 text-center sm:py-3">
                <MandarinoAvatar size="xl" flotar />

                <span className="mt-2 inline-flex items-center gap-1.5 rounded-full border border-[var(--mandarino-border)] bg-[var(--mandarino-soft)] px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-[#fb923c]">
                  <Sparkles className="h-3 w-3" aria-hidden="true" />
                  {estacionFocalObj
                    ? `Canal Especializado · ${estacionFocalObj.codigo}`
                    : "Bienvenida al Centro Conversacional"}
                </span>

                <h2 className="mt-3 bg-gradient-to-r from-[var(--text-primary)] via-[#f5b041] to-[#f97316] bg-clip-text text-2xl font-extrabold tracking-tight text-transparent sm:text-3xl">
                  {estacionFocalObj
                    ? `Listo en ${estacionFocalObj.nombre}, ${primerNombre}.`
                    : `¡Hola, ${primerNombre}! Soy Mandarino.`}
                </h2>

                <p className="mt-2 max-w-xl text-xs leading-relaxed text-[var(--text-secondary)] sm:text-sm">
                  {estacionFocalObj
                    ? "Hilo aislado exclusivamente para este nodo. Pregúntame por sus lecturas, pide un reporte o evalúa calibraciones dentro de cotas."
                    : "Elige una estación a la izquierda para conversar sobre un nodo puntual o inicia aquí una consulta directa sobre todo el ecosistema SalviaBIoT."}
                </p>

                {mensajesCanal.length > 0 && (
                  <button
                    type="button"
                    onClick={() => setVistaCentro("chat")}
                    className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-[#f97316] px-4 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-[#ea580c]"
                  >
                    <MessageSquare className="h-3.5 w-3.5" aria-hidden="true" />
                    Volver a tu conversación activa ({mensajesCanal.length} mensajes)
                  </button>
                )}

                {/* Dos tarjetas limpias: Chat Normal y Reporte Técnico (sin tarjeta de alerta redundante) */}
                <div className="mt-5 grid w-full grid-cols-1 gap-3 text-left sm:grid-cols-2">
                  {tarjetasPrincipales.map((t) => (
                    <button
                      key={t.id}
                      type="button"
                      disabled={consultandoCanalKey !== null}
                      onClick={() => void enviarConsulta(t.prompt, canalActivo)}
                      className={`group rounded-2xl border p-4 text-left transition-all hover:-translate-y-0.5 disabled:opacity-50 ${
                        t.tipo === "reporte"
                          ? "border-[#2ecc71]/40 bg-[#2ecc71]/10 hover:border-[#2ecc71]"
                          : "border-[#f5b041]/40 bg-[#f5b041]/10 hover:border-[#f97316]"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span
                          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                            t.tipo === "reporte"
                              ? "bg-[#2ecc71]/20 text-[#2ecc71]"
                              : "bg-[#f5b041]/20 text-[#f5b041]"
                          }`}
                        >
                          {t.tipo === "reporte" ? (
                            <FileBarChart2 className="h-3 w-3" aria-hidden="true" />
                          ) : (
                            <MessageCircle className="h-3 w-3" aria-hidden="true" />
                          )}
                          {t.etiqueta}
                        </span>
                        <span className="text-[11px] font-medium text-[var(--text-muted)] group-hover:text-[var(--text-primary)]">
                          Iniciar →
                        </span>
                      </div>
                      <div className="mt-2 text-sm font-semibold text-[var(--text-primary)]">
                        {t.titulo}
                      </div>
                      <p className="mt-1 text-xs leading-relaxed text-[var(--text-secondary)]">
                        {t.detalle}
                      </p>
                    </button>
                  ))}
                </div>

                {/* Guía Didáctica Interactiva */}
                <div className="mt-4 w-full rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3.5 text-left">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-[#f5b041]">
                      <BookOpen className="h-3.5 w-3.5" aria-hidden="true" />
                      Guía Didáctica Interactiva
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {PASOS_DIDACTICOS.map((paso, idx) => (
                        <button
                          key={paso.id}
                          type="button"
                          onClick={() => setGuiaDidacticaIdx(idx)}
                          className={`rounded-lg px-2 py-1 text-[11px] font-semibold transition-colors ${
                            idx === guiaDidacticaIdx
                              ? "bg-[#f97316] text-white"
                              : "bg-[var(--bg-surface)] text-[var(--text-secondary)] hover:text-[#f5b041]"
                          }`}
                        >
                          {paso.titulo}
                        </button>
                      ))}
                    </div>
                  </div>

                  <p className="mt-2.5 text-xs leading-relaxed text-[var(--text-primary)]">
                    {pasoDidacticoActivo.resumen}
                  </p>
                  <div className="mt-2 grid grid-cols-1 gap-1.5 text-[11px] text-[var(--text-secondary)] sm:grid-cols-2">
                    <div className="rounded-xl bg-[var(--bg-surface)] px-2.5 py-1.5">
                      <strong className="text-[#2ecc71]">Cuándo usarlo:</strong>{" "}
                      {pasoDidacticoActivo.ejemplo}
                    </div>
                    <div className="rounded-xl bg-[var(--bg-surface)] px-2.5 py-1.5">
                      <strong className="text-[#f5b041]">Tip rápido:</strong>{" "}
                      {pasoDidacticoActivo.consejo}
                    </div>
                  </div>
                  <div className="mt-2.5 flex flex-wrap gap-1.5">
                    {pasoDidacticoActivo.prompts.map((pr) => (
                      <button
                        key={pr.etiqueta}
                        type="button"
                        disabled={consultandoCanalKey !== null}
                        onClick={() =>
                          void enviarConsulta(
                            pr.texto,
                            pasoDidacticoActivo.id === "ecosistema"
                              ? "general"
                              : canalActivo
                          )
                        }
                        className="inline-flex items-center gap-1 rounded-full border border-[var(--mandarino-border)] bg-[var(--mandarino-soft)] px-2.5 py-1 text-[11px] font-medium text-[#fb923c] hover:brightness-110 disabled:opacity-50"
                      >
                        <Sparkles className="h-3 w-3" aria-hidden="true" />
                        Probar: {pr.etiqueta}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <ChatMessageList
              mensajesVentana={mensajesVentana}
              cantidadOcultaArriba={cantidadOcultaArriba}
              primerNombre={primerNombre}
              consultandoActual={consultandoActual}
              esAdmin={esAdmin}
              aplicandoId={aplicandoId}
              claveActiva={claveActiva}
              scrollTriggerToken={scrollTriggerToken}
              mensajeDestacadoId={mensajeDestacadoId}
              contenedorRef={contenedorScrollRef}
              onCargarAnteriores={() =>
                setLimiteMensajesPorCanal((prev) => ({
                  ...prev,
                  [claveActiva]:
                    (prev[claveActiva] ?? VENTANA_MENSAJES_INICIAL) +
                    PASO_CARGA_ANTIGUOS,
                }))
              }
              onAplicarPropuesta={(id) =>
                void handleAplicarPropuesta(id, claveActiva)
              }
              onVerCotas={() => setTabDerecha("cotas")}
              onRegenerar={handleRegenerar}
              onQuickReply={(p) => void enviarConsulta(p, canalActivo)}
            />
          )}

          {/* Barra inferior siempre fija en la ventana del chat */}
          <form
            onSubmit={handleSubmit}
            className="relative z-10 shrink-0 space-y-2 border-t border-[var(--border-subtle)] bg-[var(--bg-surface)] px-4 py-2.5 sm:px-5"
          >
            {!mostrarInicio && (
              <div className="flex flex-wrap items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => setVistaCentro("inicio")}
                  className="inline-flex items-center gap-1 rounded-full border border-[var(--border-subtle)] bg-[var(--bg-canvas)] px-2.5 py-0.5 text-[11px] font-medium text-[var(--text-secondary)] hover:border-[#f5b041]/60 hover:text-[#f5b041]"
                >
                  <Home className="h-3 w-3" aria-hidden="true" />
                  Ir al Inicio de Mandarino
                </button>
                <button
                  type="button"
                  disabled={consultandoCanalKey !== null}
                  onClick={() =>
                    void enviarConsulta(
                      "¿Qué sugerencias prácticas me das al respecto?",
                      canalActivo
                    )
                  }
                  className="inline-flex items-center gap-1 rounded-full border border-[#f5b041]/40 bg-[#f5b041]/10 px-2.5 py-0.5 text-[11px] font-medium text-[#f5b041] hover:bg-[#f5b041]/20 disabled:opacity-50"
                >
                  ¿Qué sugerencias me das?
                </button>
              </div>
            )}
            <label htmlFor="mandarino-input" className="visually-hidden">
              Conversa con Mandarino
            </label>
            <div className="flex items-end gap-2 rounded-2xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] p-1.5 transition-all focus-within:border-[#f97316] focus-within:shadow-[0_0_0_3px_rgba(249,115,22,0.16)]">
              <textarea
                id="mandarino-input"
                rows={1}
                value={mensaje}
                onChange={(e) => setMensaje(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={
                  estacionFocalObj
                    ? `Escríbele a Mandarino sobre ${estacionFocalObj.nombre}…`
                    : "Escríbele a Mandarino sobre todo el ecosistema…"
                }
                className="max-h-28 min-h-[38px] w-full resize-none bg-transparent px-2.5 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none"
              />
              <button
                type="submit"
                disabled={consultandoCanalKey !== null || !mensaje.trim()}
                aria-label="Enviar mensaje a Mandarino"
                className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-xl bg-gradient-to-r from-[#f97316] to-[#ea580c] px-3.5 text-xs font-semibold text-white shadow-sm transition-all hover:brightness-110 disabled:opacity-45"
              >
                <Send className="h-3.5 w-3.5" aria-hidden="true" />
                <span className="hidden sm:inline">Enviar</span>
              </button>
            </div>
          </form>
        </section>

        <ProactiveBoundsPanel
          tabDerecha={tabDerecha}
          onCambiarTab={setTabDerecha}
          alertasEcosistema={alertasEcosistema}
          solucionesVersiones={solucionesVersiones}
          solucionesCountFallback={solucionesAplicadasCount}
          historialGlobalReciente={historialGlobalReciente}
          nombrePorEstacion={nombrePorEstacion}
          cargandoEstado={cargandoEstado}
          cotas={cotas}
          parametrosActuales={estado?.parametros_actuales ?? {}}
          ajustesSegurosInspector={ajustesSegurosInspector}
          recortesMap={recortesMap}
          esAdmin={esAdmin}
          revirtiendo={revirtiendo}
          totalVersionesCanal={estado?.versiones?.length ?? 0}
          onResolverAlerta={(prompt, estId) => void enviarConsulta(prompt, estId)}
          onAbrirHistorialItem={(item) =>
            void handleAbrirHistorialDeEstacion(item)
          }
          onRollback={() => void handleRollback()}
        />
      </div>
    </div>
  );
}
