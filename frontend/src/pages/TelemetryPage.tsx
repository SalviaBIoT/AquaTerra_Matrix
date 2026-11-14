import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  Download,
  FileSpreadsheet,
  GitCompare,
  Layers,
  LayoutGrid,
  Loader2,
  Percent,
  SlidersHorizontal,
} from "lucide-react";
import type { EChartsCoreOption } from "echarts";
import { toast } from "sonner";
import { EChartBox, obtenerPaletaECharts } from "../components/charts/EChartBox";
import { Badge } from "../components/common/Badge";
import { useApp } from "../context/AppContext";
import { api, descargarArchivo } from "../lib/api";
import {
  etiquetarFuerzaCorrelacion,
  etiquetarTipoEstacion,
  formatearNumero,
  nombreLegibleVariable,
} from "../lib/formatters";
import type {
  ComparativoMonitorResponse,
  CorrelacionResponse,
  SeriesResponse,
  TipoEstacion,
} from "../types/aquaterra";

const VENTANAS_HORAS = [
  { id: 6, etiqueta: "6h" },
  { id: 24, etiqueta: "24h" },
  { id: 168, etiqueta: "7d" },
  { id: 0, etiqueta: "Todo" },
];

const SUAVIZADOS_MOVILES = [
  { id: "raw", etiqueta: "Crudo" },
  { id: "5m", etiqueta: "5m" },
  { id: "15m", etiqueta: "15m" },
  { id: "30m", etiqueta: "30m" },
  { id: "1h", etiqueta: "1h" },
  { id: "6h", etiqueta: "6h" },
  { id: "24h", etiqueta: "24h" },
] as const;

type VentanaMovilId = (typeof SUAVIZADOS_MOVILES)[number]["id"];
type ModoGrafica = "dominio" | "individual" | "normalizado";

interface GrupoPanel {
  id: string;
  titulo: string;
  subtitulo: string;
  variables: string[];
  ejeSecundario?: string[];
  ejeIzquierdoNombre?: string;
  ejeDerechoNombre?: string;
}

const DOMINIOS_FISICOS: {
  id: string;
  titulo: string;
  subtitulo: string;
  candidatas: string[];
  ejeSecundario?: string[];
  ejeIzquierdoNombre?: string;
  ejeDerechoNombre?: string;
}[] = [
  {
    id: "hidrica",
    titulo: "Dinámica Hídrica y Suelo (%)",
    subtitulo:
      "Humedad edáfica (Sonda A/B), humedad relativa del aire y mojado foliar",
    candidatas: [
      "suelo_a",
      "suelo_b",
      "hum_aire",
      "humedad_suelo_pct",
      "humedad_rel_pct",
      "humedad_interna_pct",
      "mojado_foliar_pct",
    ],
    ejeIzquierdoNombre: "%",
  },
  {
    id: "termica_vapor",
    titulo: "Régimen Térmico y Estrés Vapor (°C · kPa)",
    subtitulo:
      "Temperatura de aire/raíz en eje izquierdo (°C) y Déficit de Presión de Vapor en eje derecho (kPa)",
    candidatas: [
      "temp_aire",
      "temp_raiz",
      "temp_suelo_c",
      "temp_c",
      "temp_interna_c",
      "temp_externa_c",
      "vpd",
      "vpd_kpa",
    ],
    ejeSecundario: ["vpd", "vpd_kpa"],
    ejeIzquierdoNombre: "°C",
    ejeDerechoNombre: "kPa",
  },
  {
    id: "barometrica",
    titulo: "Atmósfera Barométrica (hPa)",
    subtitulo:
      "Escala independiente para observar oscilaciones finas (~850–865 hPa) sin aplanar otros sensores",
    candidatas: ["presion", "presion_hpa"],
    ejeIzquierdoNombre: "hPa",
  },
  {
    id: "energia_hidrologia",
    titulo: "Energía, Radiación e Hidrología",
    subtitulo:
      "Batería, radio RSSI, radiación solar, nivel de agua y precipitación",
    candidatas: [
      "voltaje",
      "bateria_v",
      "bateria_pct",
      "radiacion_wm2",
      "lux",
      "rssi_dbm",
      "nivel_agua_cm",
      "caudal_l_min",
      "lluvia_mm",
      "peso_colmena_kg",
    ],
    ejeSecundario: ["radiacion_wm2", "lux"],
    ejeDerechoNombre: "Solar",
  },
];

function construirPanelesAdaptativos(
  tipo: TipoEstacion | undefined,
  clavesDisponibles: string[]
): GrupoPanel[] {
  const disponibles = new Set(clavesDisponibles);
  const usadas = new Set<string>();
  const paneles: GrupoPanel[] = [];

  for (const dom of DOMINIOS_FISICOS) {
    const vars = dom.candidatas.filter((c) => disponibles.has(c));
    if (vars.length === 0) continue;
    vars.forEach((c) => usadas.add(c));

    const sec = (dom.ejeSecundario ?? []).filter((c) => vars.includes(c));
    const tienePrimario = vars.some((c) => !sec.includes(c));
    const usarDobleEje = sec.length > 0 && tienePrimario;

    let subtitulo = dom.subtitulo;
    if (dom.id === "hidrica" && tipo === "sigatoka") {
      subtitulo = "Mojado foliar continuo, humedad relativa y estado hídrico del cultivo";
    } else if (dom.id === "termica_vapor" && tipo === "inbeersa") {
      subtitulo = "Estabilidad térmica interna vs exterior de colmena";
    }

    paneles.push({
      id: dom.id,
      titulo: dom.titulo,
      subtitulo,
      variables: vars,
      ejeSecundario: usarDobleEje ? sec : undefined,
      ejeIzquierdoNombre: dom.ejeIzquierdoNombre,
      ejeDerechoNombre: usarDobleEje ? dom.ejeDerechoNombre : undefined,
    });
  }

  const restantes = clavesDisponibles.filter((c) => !usadas.has(c));
  if (restantes.length > 0) {
    paneles.push({
      id: "complementarias",
      titulo:
        paneles.length === 0
          ? "Series Temporales Registradas"
          : "Variables Complementarias",
      subtitulo: "Canales adicionales reportados por el nodo",
      variables: restantes,
    });
  }

  return paneles;
}

interface ResumenCanal {
  variable: string;
  unidad: string;
  puntos: [number, number][];
  ultimo: number | null;
  minimo: number | null;
  maximo: number | null;
}

const PALETA_SERIES = [
  "#34D399",
  "#38BDF8",
  "#FBBF24",
  "#F472B6",
  "#A78BFA",
  "#FB923C",
  "#2DD4BF",
];

export function TelemetryPage() {
  const {
    estaciones,
    estacionActivaId,
    setEstacionActivaId,
    estacionActiva,
    temaEfectivo,
  } = useApp();

  const [horas, setHoras] = useState<number>(24);
  const [ventanaMovil, setVentanaMovil] = useState<VentanaMovilId>("raw");
  const [modoVista, setModoVista] = useState<ModoGrafica>("dominio");
  const [variablesOcultas, setVariablesOcultas] = useState<string[]>([]);
  const [seriesSuavizadas, setSeriesSuavizadas] = useState<
    Record<string, [number, number][]> | null
  >(null);
  const [seriesData, setSeriesData] = useState<SeriesResponse | null>(null);
  const [comparativo, setComparativo] =
    useState<ComparativoMonitorResponse | null>(null);
  const [cargando, setCargando] = useState(false);

  useEffect(() => {
    setVariablesOcultas([]);
  }, [estacionActivaId]);

  const [varX, setVarX] = useState<string>("");
  const [varY, setVarY] = useState<string>("");
  const [correlacion, setCorrelacion] = useState<CorrelacionResponse | null>(
    null
  );
  const [cargandoCorr, setCargandoCorr] = useState(false);

  const cargarTodo = useCallback(async (estId: number, winHoras: number) => {
    setCargando(true);
    try {
      const [sResp, compResp] = await Promise.all([
        api.get<SeriesResponse>(
          `/api/estaciones/${estId}/series?horas=${winHoras}`
        ),
        api.get<ComparativoMonitorResponse>("/api/monitor/comparativo"),
      ]);
      setSeriesData(sResp);
      setComparativo(compResp);

      const keys = Object.keys(sResp.series ?? {});
      setVarX((prev) => (prev && keys.includes(prev) ? prev : keys[0] ?? ""));
      setVarY((prev) =>
        prev && keys.includes(prev) ? prev : keys[1] ?? keys[0] ?? ""
      );
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Error cargando series."
      );
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    if (estacionActivaId !== null) {
      void cargarTodo(estacionActivaId, horas);
    }
  }, [estacionActivaId, horas, cargarTodo]);

  // Suavizado por ventana móvil SQLite (cuando ventanaMovil !== "raw")
  useEffect(() => {
    if (estacionActivaId === null || ventanaMovil === "raw" || !seriesData) {
      setSeriesSuavizadas(null);
      return;
    }
    const keys = Object.keys(seriesData.series ?? {});
    if (keys.length === 0) {
      setSeriesSuavizadas(null);
      return;
    }
    let cancelado = false;
    Promise.all(
      keys.map(async (variable) => {
        const resp = await api.get<{
          puntos: { ts_epoch: number; media_movil: number }[];
        }>(
          `/api/estaciones/${estacionActivaId}/ventana-movil?variable=${encodeURIComponent(
            variable
          )}&horas=${horas}&ventana=${ventanaMovil}`
        );
        return [
          variable,
          (resp.puntos ?? []).map(
            (p) => [p.ts_epoch, p.media_movil] as [number, number]
          ),
        ] as const;
      })
    )
      .then((entries) => {
        if (!cancelado) {
          setSeriesSuavizadas(Object.fromEntries(entries));
        }
      })
      .catch(() => {
        if (!cancelado) setSeriesSuavizadas(null);
      });
    return () => {
      cancelado = true;
    };
  }, [estacionActivaId, horas, ventanaMovil, seriesData]);

  // Correlación bivariada OLS
  useEffect(() => {
    if (estacionActivaId === null || !varX || !varY) {
      setCorrelacion(null);
      return;
    }
    let cancelado = false;
    setCargandoCorr(true);
    api
      .get<CorrelacionResponse>(
        `/api/estaciones/${estacionActivaId}/correlacion?var_x=${encodeURIComponent(
          varX
        )}&var_y=${encodeURIComponent(varY)}&horas=${horas}`
      )
      .then((res) => {
        if (!cancelado) setCorrelacion(res);
      })
      .catch(() => {
        if (!cancelado) setCorrelacion(null);
      })
      .finally(() => {
        if (!cancelado) setCargandoCorr(false);
      });
    return () => {
      cancelado = true;
    };
  }, [estacionActivaId, varX, varY, horas]);

  const clavesVariables = useMemo(
    () => Object.keys(seriesData?.series ?? {}),
    [seriesData]
  );

  const toggleVariable = useCallback((variable: string) => {
    setVariablesOcultas((prev) =>
      prev.includes(variable)
        ? prev.filter((item) => item !== variable)
        : [...prev, variable]
    );
  }, []);

  const clavesVisibles = useMemo(
    () => clavesVariables.filter((v) => !variablesOcultas.includes(v)),
    [clavesVariables, variablesOcultas]
  );

  const obtenerSerieEfectiva = useCallback(
    (variable: string): [number, number][] =>
      ventanaMovil !== "raw" && seriesSuavizadas?.[variable]
        ? seriesSuavizadas[variable]
        : seriesData?.series[variable] ?? [],
    [seriesData, seriesSuavizadas, ventanaMovil]
  );

  const resumenesCanales = useMemo<ResumenCanal[]>(() => {
    const units = seriesData?.unidades ?? {};
    return clavesVisibles.map((variable) => {
      const puntos = obtenerSerieEfectiva(variable);
      let minimo: number | null = null;
      let maximo: number | null = null;
      for (const [, valor] of puntos) {
        if (minimo === null || valor < minimo) minimo = valor;
        if (maximo === null || valor > maximo) maximo = valor;
      }
      const ultimo = puntos.length > 0 ? puntos[puntos.length - 1][1] : null;
      return {
        variable,
        unidad: units[variable] ?? "",
        puntos,
        ultimo,
        minimo,
        maximo,
      };
    });
  }, [clavesVisibles, obtenerSerieEfectiva, seriesData]);

  const paneles = useMemo(
    () =>
      construirPanelesAdaptativos(
        seriesData?.estacion.tipo ?? estacionActiva?.tipo,
        clavesVisibles
      ),
    [seriesData, estacionActiva, clavesVisibles]
  );

  const construirOpcionPanel = useCallback(
    (panel: GrupoPanel): EChartsCoreOption => {
      const pal = obtenerPaletaECharts(temaEfectivo);
      const units = seriesData?.unidades ?? {};
      const secundarias = new Set(panel.ejeSecundario ?? []);
      const tieneDobleEje = secundarias.size > 0;

      return {
        color: PALETA_SERIES,
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "cross" },
          backgroundColor: pal.surface,
          borderColor: pal.borderSubtle,
          textStyle: { color: pal.textPrimary, fontSize: 12 },
        },
        legend: {
          top: 0,
          left: 0,
          type: "scroll",
          textStyle: { color: pal.textSecondary, fontSize: 11 },
        },
        grid: {
          left: 52,
          right: tieneDobleEje ? 54 : 20,
          top: 40,
          bottom: 56,
        },
        dataZoom: [
          { type: "inside", filterMode: "none" },
          {
            type: "slider",
            height: 20,
            bottom: 8,
            borderColor: pal.borderSubtle,
            textStyle: { color: pal.textMuted, fontSize: 10 },
          },
        ],
        xAxis: {
          type: "time",
          axisLine: { lineStyle: { color: pal.borderSubtle } },
          axisLabel: { color: pal.textMuted, fontSize: 10 },
        },
        yAxis: tieneDobleEje
          ? [
              {
                type: "value",
                name: panel.ejeIzquierdoNombre ?? "",
                nameTextStyle: { color: pal.textMuted, fontSize: 10 },
                scale: true,
                splitLine: { lineStyle: { color: pal.borderSubtle } },
                axisLabel: { color: pal.textMuted, fontSize: 10 },
              },
              {
                type: "value",
                name: panel.ejeDerechoNombre ?? "",
                nameTextStyle: { color: pal.textMuted, fontSize: 10 },
                scale: true,
                splitLine: { show: false },
                axisLabel: { color: pal.textMuted, fontSize: 10 },
              },
            ]
          : {
              type: "value",
              name: panel.ejeIzquierdoNombre ?? "",
              nameTextStyle: { color: pal.textMuted, fontSize: 10 },
              scale: true,
              splitLine: { lineStyle: { color: pal.borderSubtle } },
              axisLabel: { color: pal.textMuted, fontSize: 10 },
            },
        series: panel.variables.map((v) => {
          const unit = units[v] ? ` (${units[v]})` : "";
          const fuente = obtenerSerieEfectiva(v);
          const pts = fuente.map(([ts, val]) => [ts * 1000, val]);
          return {
            name: `${nombreLegibleVariable(v)}${unit}`,
            type: "line",
            yAxisIndex: tieneDobleEje && secundarias.has(v) ? 1 : 0,
            showSymbol: pts.length < 25,
            symbolSize: 5,
            smooth: 0.25,
            data: pts,
          };
        }),
      };
    },
    [seriesData, obtenerSerieEfectiva, temaEfectivo]
  );

  const construirOpcionIndividual = useCallback(
    (canal: ResumenCanal, colorIndex: number): EChartsCoreOption => {
      const pal = obtenerPaletaECharts(temaEfectivo);
      const color = PALETA_SERIES[colorIndex % PALETA_SERIES.length];
      const pts = canal.puntos.map(([ts, val]) => [ts * 1000, val]);
      const etiquetaUnidad = canal.unidad ? ` (${canal.unidad})` : "";

      return {
        color: [color],
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "line" },
          backgroundColor: pal.surface,
          borderColor: pal.borderSubtle,
          textStyle: { color: pal.textPrimary, fontSize: 12 },
        },
        grid: { left: 48, right: 16, top: 18, bottom: 44 },
        dataZoom: [{ type: "inside", filterMode: "none" }],
        xAxis: {
          type: "time",
          axisLine: { lineStyle: { color: pal.borderSubtle } },
          axisLabel: { color: pal.textMuted, fontSize: 10 },
        },
        yAxis: {
          type: "value",
          scale: true,
          splitLine: { lineStyle: { color: pal.borderSubtle } },
          axisLabel: { color: pal.textMuted, fontSize: 10 },
        },
        series: [
          {
            name: `${nombreLegibleVariable(canal.variable)}${etiquetaUnidad}`,
            type: "line",
            showSymbol: pts.length < 25,
            symbolSize: 4,
            smooth: 0.25,
            areaStyle: { opacity: 0.14 },
            data: pts,
          },
        ],
      };
    },
    [temaEfectivo]
  );

  const opcionNormalizada = useMemo<EChartsCoreOption>(() => {
    const pal = obtenerPaletaECharts(temaEfectivo);
    const metaPorSerie = new Map<
      string,
      { unidad: string; min: number; span: number }
    >();

    const series = resumenesCanales.map((canal) => {
      const min = canal.minimo ?? 0;
      const max = canal.maximo ?? 0;
      const span = max - min;
      const etiquetaUnidad = canal.unidad ? ` (${canal.unidad})` : "";
      const serieNombre = `${nombreLegibleVariable(canal.variable)}${etiquetaUnidad}`;
      metaPorSerie.set(serieNombre, {
        unidad: canal.unidad,
        min,
        span,
      });

      const pts = canal.puntos.map(([ts, val]) => {
        const pct = span > 1e-9 ? ((val - min) / span) * 100 : 50;
        return [ts * 1000, Number(pct.toFixed(2)), val];
      });

      return {
        name: serieNombre,
        type: "line" as const,
        showSymbol: pts.length < 25,
        symbolSize: 4,
        smooth: 0.25,
        encode: { x: 0, y: 1 },
        data: pts,
      };
    });

    return {
      color: PALETA_SERIES,
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "cross" },
        backgroundColor: pal.surface,
        borderColor: pal.borderSubtle,
        textStyle: { color: pal.textPrimary, fontSize: 12 },
        formatter: (params: unknown) => {
          const items = (Array.isArray(params) ? params : [params]) as {
            marker?: string;
            seriesName?: string;
            axisValueLabel?: string;
            data?: unknown;
          }[];
          if (items.length === 0) return "";
          const fecha = items[0]?.axisValueLabel ?? "";
          const filas = items.map((item) => {
            const nombre = item.seriesName ?? "";
            const meta = metaPorSerie.get(nombre);
            const arr = Array.isArray(item.data)
              ? (item.data as number[])
              : undefined;
            const pct = arr && typeof arr[1] === "number" ? arr[1] : null;
            const realVal = arr && typeof arr[2] === "number" ? arr[2] : null;
            const realTexto =
              realVal !== null
                ? `${formatearNumero(realVal, 2)}${meta?.unidad ? ` ${meta.unidad}` : ""}`
                : "—";
            const pctTexto = pct !== null ? `${formatearNumero(pct, 1)}%` : "—";
            return `<div style="display:flex;justify-content:space-between;gap:14px;">
              <span>${item.marker ?? ""}${nombre}</span>
              <strong>${realTexto} <span style="opacity:0.7">(${pctTexto})</span></strong>
            </div>`;
          });
          return `<div style="font-size:11px;margin-bottom:4px;opacity:0.75">${fecha}</div>${filas.join("")}`;
        },
      },
      legend: {
        top: 0,
        left: 0,
        type: "scroll",
        textStyle: { color: pal.textSecondary, fontSize: 11 },
      },
      grid: { left: 48, right: 20, top: 42, bottom: 56 },
      dataZoom: [
        { type: "inside", filterMode: "none" },
        {
          type: "slider",
          height: 20,
          bottom: 8,
          borderColor: pal.borderSubtle,
          textStyle: { color: pal.textMuted, fontSize: 10 },
        },
      ],
      xAxis: {
        type: "time",
        axisLine: { lineStyle: { color: pal.borderSubtle } },
        axisLabel: { color: pal.textMuted, fontSize: 10 },
      },
      yAxis: {
        type: "value",
        min: 0,
        max: 100,
        axisLabel: {
          color: pal.textMuted,
          fontSize: 10,
          formatter: "{value}%",
        },
        splitLine: { lineStyle: { color: pal.borderSubtle } },
      },
      series,
    };
  }, [resumenesCanales, temaEfectivo]);

  const opcionCorrelacion = useMemo<EChartsCoreOption>(() => {
    const pal = obtenerPaletaECharts(temaEfectivo);
    const pares = correlacion?.pares ?? [];
    const recta = correlacion?.recta_ols ?? null;

    return {
      tooltip: {
        trigger: "item",
        backgroundColor: pal.surface,
        borderColor: pal.borderSubtle,
        textStyle: { color: pal.textPrimary, fontSize: 12 },
      },
      legend: {
        top: 0,
        right: 0,
        textStyle: { color: pal.textSecondary, fontSize: 11 },
      },
      grid: { left: 48, right: 22, top: 34, bottom: 34 },
      xAxis: {
        type: "value",
        scale: true,
        name: nombreLegibleVariable(varX),
        nameLocation: "middle",
        nameGap: 22,
        nameTextStyle: { color: pal.textMuted, fontSize: 10 },
        splitLine: { lineStyle: { color: pal.borderSubtle } },
        axisLabel: { color: pal.textMuted, fontSize: 10 },
      },
      yAxis: {
        type: "value",
        scale: true,
        splitLine: { lineStyle: { color: pal.borderSubtle } },
        axisLabel: { color: pal.textMuted, fontSize: 10 },
      },
      series: [
        {
          name: "Muestras sincronizadas",
          type: "scatter",
          symbolSize: 7,
          itemStyle: { color: pal.accent, opacity: 0.8 },
          data: pares,
        },
        ...(recta
          ? [
              {
                name: "Regresión OLS",
                type: "line",
                symbol: "none",
                lineStyle: { color: pal.warning, width: 2, type: "dashed" },
                data: recta,
              },
            ]
          : []),
      ],
    };
  }, [correlacion, varX, temaEfectivo]);

  const opcionHumedadParcelas = useMemo<EChartsCoreOption>(() => {
    const pal = obtenerPaletaECharts(temaEfectivo);
    const rows = comparativo?.humedad_por_parcela ?? [];
    return {
      tooltip: {
        trigger: "axis",
        backgroundColor: pal.surface,
        borderColor: pal.borderSubtle,
        textStyle: { color: pal.textPrimary, fontSize: 12 },
      },
      grid: { left: 100, right: 24, top: 16, bottom: 26 },
      xAxis: {
        type: "value",
        max: 100,
        splitLine: { lineStyle: { color: pal.borderSubtle } },
        axisLabel: { color: pal.textMuted, fontSize: 10, formatter: "{value}%" },
      },
      yAxis: {
        type: "category",
        data: rows.map((r) => r.nombre),
        axisLabel: { color: pal.textSecondary, fontSize: 11 },
      },
      series: [
        {
          type: "bar",
          data: rows.map((r) => ({
            value: r.humedad_pct,
            itemStyle: {
              color:
                r.humedad_pct < 35
                  ? pal.critical
                  : r.humedad_pct < 48
                  ? pal.warning
                  : pal.optimal,
              borderRadius: [0, 6, 6, 0],
            },
          })),
          barMaxWidth: 18,
        },
      ],
    };
  }, [comparativo, temaEfectivo]);

  const opcionConsumoParcelas = useMemo<EChartsCoreOption>(() => {
    const pal = obtenerPaletaECharts(temaEfectivo);
    const rows = comparativo?.consumo_por_parcela ?? [];
    return {
      tooltip: {
        trigger: "axis",
        backgroundColor: pal.surface,
        borderColor: pal.borderSubtle,
        textStyle: { color: pal.textPrimary, fontSize: 12 },
      },
      grid: { left: 52, right: 20, top: 16, bottom: 32 },
      xAxis: {
        type: "category",
        data: rows.map((r) => r.nombre),
        axisLabel: { color: pal.textSecondary, fontSize: 11 },
      },
      yAxis: {
        type: "value",
        splitLine: { lineStyle: { color: pal.borderSubtle } },
        axisLabel: { color: pal.textMuted, fontSize: 10, formatter: "{value} L" },
      },
      series: [
        {
          type: "bar",
          data: rows.map((r) => r.litros),
          barMaxWidth: 26,
          itemStyle: { color: pal.info, borderRadius: [6, 6, 0, 0] },
        },
      ],
    };
  }, [comparativo, temaEfectivo]);

  const handleExport = async (formato: "csv" | "xlsx") => {
    if (estacionActivaId === null) return;
    try {
      const cod = estacionActiva?.codigo ?? `estacion_${estacionActivaId}`;
      const ventanaExport = ventanaMovil === "raw" ? "1h" : ventanaMovil;
      await descargarArchivo(
        `/api/exportar/${formato}?estacion_id=${estacionActivaId}&ventana=${ventanaExport}`,
        formato === "csv" ? `serie_${cod}.csv` : `reporte_${cod}.xlsx`
      );
      toast.success(`Archivo .${formato} exportado correctamente.`);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Error exportando archivo."
      );
    }
  };

  return (
    <div className="space-y-6">
      {/* Cabecera de control de telemetría */}
      <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)]">
              Telemetría y Analítica Multipanel
            </h1>
            {estacionActiva && (
              <Badge tono="info">
                {etiquetarTipoEstacion(estacionActiva.tipo)}
              </Badge>
            )}
          </div>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            Series temporales sincronizadas con zoom interactivo, correlación
            bivariada de Pearson/OLS y comparativa hídrica por parcela.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <select
            value={estacionActivaId ?? ""}
            onChange={(e) =>
              setEstacionActivaId(
                e.target.value ? Number(e.target.value) : null
              )
            }
            aria-label="Seleccionar estación para telemetría"
            className="h-9 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-3 text-xs font-medium text-[var(--text-primary)]"
          >
            {estaciones.map((e) => (
              <option key={e.id} value={e.id}>
                {e.codigo} · {e.nombre}
              </option>
            ))}
          </select>

          <div
            role="group"
            aria-label="Ventana temporal"
            className="inline-flex rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-0.5"
          >
            {VENTANAS_HORAS.map((v) => (
              <button
                key={v.id}
                type="button"
                onClick={() => setHoras(v.id)}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                  horas === v.id
                    ? "bg-[var(--accent-primary)] text-[var(--accent-contrast)]"
                    : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                }`}
              >
                {v.etiqueta}
              </button>
            ))}
          </div>

          <select
            value={ventanaMovil}
            onChange={(e) => setVentanaMovil(e.target.value as VentanaMovilId)}
            aria-label="Media móvil de serie"
            title="Suavizado por ventana móvil SQLite y exportación"
            className="h-9 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-2.5 text-xs font-medium text-[var(--text-primary)]"
          >
            {SUAVIZADOS_MOVILES.map((sm) => (
              <option key={sm.id} value={sm.id}>
                Media móvil: {sm.etiqueta}
              </option>
            ))}
          </select>

          <button
            type="button"
            onClick={() => void handleExport("csv")}
            disabled={estacionActivaId === null}
            className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-3 text-xs font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] disabled:opacity-50"
          >
            <Download className="h-3.5 w-3.5 text-[var(--accent-primary)]" aria-hidden="true" />
            CSV
          </button>

          <button
            type="button"
            onClick={() => void handleExport("xlsx")}
            disabled={estacionActivaId === null}
            className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-3 text-xs font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] disabled:opacity-50"
          >
            <FileSpreadsheet
              className="h-3.5 w-3.5 text-[var(--status-optimal)]"
              aria-hidden="true"
            />
            Excel
          </button>
        </div>
      </div>

      {/* Barra de modo de escala y filtro rápido de variables */}
      {clavesVariables.length > 0 && (
        <div className="surface-card flex flex-col gap-3 p-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
              Canales activos ({clavesVisibles.length}/{clavesVariables.length}):
            </span>
            {clavesVariables.map((v, idx) => {
              const activo = !variablesOcultas.includes(v);
              const color = PALETA_SERIES[idx % PALETA_SERIES.length];
              const unit = seriesData?.unidades?.[v];
              return (
                <button
                  key={v}
                  type="button"
                  onClick={() => toggleVariable(v)}
                  aria-pressed={activo}
                  className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ${
                    activo
                      ? "border-[var(--border-subtle)] bg-[var(--bg-elevated)] text-[var(--text-primary)]"
                      : "border-transparent bg-[var(--bg-canvas)] text-[var(--text-muted)] opacity-60 hover:opacity-90"
                  }`}
                >
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ backgroundColor: activo ? color : "currentColor" }}
                    aria-hidden="true"
                  />
                  <span>{nombreLegibleVariable(v)}</span>
                  {unit && (
                    <span className="text-[10px] text-[var(--text-muted)]">
                      ({unit})
                    </span>
                  )}
                </button>
              );
            })}
            {variablesOcultas.length > 0 && (
              <button
                type="button"
                onClick={() => setVariablesOcultas([])}
                className="rounded-full px-2 py-1 text-[11px] font-semibold text-[var(--accent-primary)] hover:underline"
              >
                Mostrar todas
              </button>
            )}
          </div>

          <div
            role="group"
            aria-label="Modo de visualización de escalas"
            className="inline-flex shrink-0 flex-wrap rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-canvas)] p-0.5"
          >
            <button
              type="button"
              onClick={() => setModoVista("dominio")}
              className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-semibold transition-colors ${
                modoVista === "dominio"
                  ? "bg-[var(--accent-primary)] text-[var(--accent-contrast)]"
                  : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              }`}
            >
              <Layers className="h-3.5 w-3.5" aria-hidden="true" />
              Dominio físico
            </button>
            <button
              type="button"
              onClick={() => setModoVista("individual")}
              className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-semibold transition-colors ${
                modoVista === "individual"
                  ? "bg-[var(--accent-primary)] text-[var(--accent-contrast)]"
                  : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              }`}
            >
              <LayoutGrid className="h-3.5 w-3.5" aria-hidden="true" />
              Por variable
            </button>
            <button
              type="button"
              onClick={() => setModoVista("normalizado")}
              className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-semibold transition-colors ${
                modoVista === "normalizado"
                  ? "bg-[var(--accent-primary)] text-[var(--accent-contrast)]"
                  : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              }`}
            >
              <Percent className="h-3.5 w-3.5" aria-hidden="true" />
              Comparativa 0–100%
            </button>
          </div>
        </div>
      )}

      {/* Paneles adaptativos por dominio físico / individual / normalizado */}
      {cargando && !seriesData ? (
        <div className="surface-card space-y-3 p-6">
          <div className="skeleton h-6 w-48" />
          <div className="skeleton h-64 w-full" />
        </div>
      ) : clavesVariables.length === 0 ? (
        <section className="surface-card p-8 text-center">
          <Activity
            className="mx-auto h-8 w-8 text-[var(--text-muted)]"
            aria-hidden="true"
          />
          <h2 className="mt-3 text-base font-semibold text-[var(--text-primary)]">
            Sin muestras de telemetría en la ventana seleccionada
          </h2>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">
            Amplía la ventana a &ldquo;Todo&rdquo; o inyecta tramas desde
            Hardware IoT para visualizar curvas multipanel.
          </p>
        </section>
      ) : clavesVisibles.length === 0 ? (
        <section className="surface-card p-8 text-center">
          <h2 className="text-base font-semibold text-[var(--text-primary)]">
            Todos los canales están ocultos
          </h2>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">
            Activa al menos una variable arriba o restaura todas para graficar.
          </p>
          <button
            type="button"
            onClick={() => setVariablesOcultas([])}
            className="mt-3 rounded-xl bg-[var(--accent-primary)] px-4 py-2 text-xs font-semibold text-[var(--accent-contrast)]"
          >
            Mostrar todos los canales
          </button>
        </section>
      ) : modoVista === "normalizado" ? (
        <section className="surface-card p-5">
          <div className="mb-3 flex flex-col justify-between gap-2 sm:flex-row sm:items-start">
            <div>
              <h2 className="text-base font-semibold text-[var(--text-primary)]">
                Comparativa Normalizada (0–100% por rango observado)
              </h2>
              <p className="text-xs text-[var(--text-secondary)]">
                Permite correlacionar visualmente cambios de fase entre Presión (hPa), VPD (kPa) y Humedad (%). El tooltip conserva la magnitud física real.
              </p>
            </div>
            <span className="font-mono text-[11px] text-[var(--text-muted)]">
              {resumenesCanales.length} canales activos
            </span>
          </div>
          <EChartBox
            option={opcionNormalizada}
            height={360}
            ariaLabel="Comparativa normalizada 0 a 100 por ciento"
          />
        </section>
      ) : modoVista === "individual" ? (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
          {resumenesCanales.map((canal, idx) => (
            <section key={canal.variable} className="surface-card p-4">
              <div className="mb-2 flex items-start justify-between gap-2">
                <div>
                  <h2 className="text-sm font-semibold text-[var(--text-primary)]">
                    {nombreLegibleVariable(canal.variable)}
                    {canal.unidad ? ` (${canal.unidad})` : ""}
                  </h2>
                  <p className="mt-0.5 font-mono text-[11px] text-[var(--text-muted)]">
                    Mín {canal.minimo !== null ? formatearNumero(canal.minimo, 2) : "—"} · Máx{" "}
                    {canal.maximo !== null ? formatearNumero(canal.maximo, 2) : "—"}
                  </p>
                </div>
                <span className="rounded-lg bg-[var(--bg-elevated)] px-2 py-1 font-mono text-xs font-semibold tabular-nums text-[var(--accent-primary)]">
                  {canal.ultimo !== null
                    ? `${formatearNumero(canal.ultimo, 2)}${canal.unidad ? ` ${canal.unidad}` : ""}`
                    : "—"}
                </span>
              </div>
              <EChartBox
                option={construirOpcionIndividual(canal, idx)}
                height={210}
                ariaLabel={`Serie individual de ${nombreLegibleVariable(canal.variable)}`}
              />
            </section>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          {paneles.map((panel) => (
            <section key={panel.id} className="surface-card p-5">
              <div className="mb-3 flex items-start justify-between gap-2">
                <div>
                  <h2 className="text-base font-semibold text-[var(--text-primary)]">
                    {panel.titulo}
                  </h2>
                  <p className="text-xs text-[var(--text-secondary)]">
                    {panel.subtitulo}
                  </p>
                </div>
                <span className="font-mono text-[11px] text-[var(--text-muted)]">
                  {panel.variables.length}{" "}
                  {panel.variables.length === 1 ? "canal" : "canales"}
                </span>
              </div>
              <EChartBox
                option={construirOpcionPanel(panel)}
                height={300}
                ariaLabel={`Gráfica de ${panel.titulo}`}
              />
            </section>
          ))}
        </div>
      )}

      {/* Correlación Bivariada + Comparativos de Parcela */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
        {/* Correlación OLS (6 cols) */}
        <section className="surface-card p-5 xl:col-span-6">
          <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
            <div className="flex items-center gap-2">
              <GitCompare
                className="h-4 w-4 text-[var(--accent-primary)]"
                aria-hidden="true"
              />
              <div>
                <h2 className="text-base font-semibold text-[var(--text-primary)]">
                  Correlación Bivariada &amp; Regresión OLS
                </h2>
                <p className="text-xs text-[var(--text-secondary)]">
                  Emparejamiento temporal ≤ 300 s en núcleo analítico.
                </p>
              </div>
            </div>

            {clavesVariables.length >= 2 && (
              <div className="flex items-center gap-2">
                <select
                  value={varX}
                  onChange={(e) => setVarX(e.target.value)}
                  aria-label="Variable eje X"
                  className="h-8 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-2 text-xs text-[var(--text-primary)]"
                >
                  {clavesVariables.map((v) => (
                    <option key={v} value={v}>
                      X: {nombreLegibleVariable(v)}
                    </option>
                  ))}
                </select>
                <select
                  value={varY}
                  onChange={(e) => setVarY(e.target.value)}
                  aria-label="Variable eje Y"
                  className="h-8 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-2 text-xs text-[var(--text-primary)]"
                >
                  {clavesVariables.map((v) => (
                    <option key={v} value={v}>
                      Y: {nombreLegibleVariable(v)}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {cargandoCorr ? (
            <div className="flex h-64 items-center justify-center text-xs text-[var(--text-secondary)]">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
              Calculando regresión lineal…
            </div>
          ) : !correlacion || (correlacion.pares?.length ?? 0) === 0 ? (
            <div className="mt-4 rounded-xl bg-[var(--bg-elevated)] p-6 text-center text-xs text-[var(--text-secondary)]">
              Se necesitan al menos 2 variables con marcas de tiempo coincidentes
              para trazar el diagrama de dispersión.
            </div>
          ) : (
            <>
              <div className="mt-3 flex flex-wrap items-center gap-3 rounded-xl bg-[var(--bg-elevated)] px-3.5 py-2.5 text-xs">
                <span className="tabular-nums font-mono">
                  r ={" "}
                  <strong className="text-[var(--accent-primary)]">
                    {formatearNumero(correlacion.resultado.pearson_r, 3)}
                  </strong>
                </span>
                <span className="text-[var(--text-muted)]">·</span>
                <span className="tabular-nums font-mono">
                  m ={" "}
                  {formatearNumero(correlacion.resultado.pendiente_y_sobre_x, 3)}
                </span>
                <span className="text-[var(--text-muted)]">·</span>
                <span className="tabular-nums">
                  {correlacion.resultado.pares_alineados} pares
                </span>
                <span className="text-[var(--text-secondary)]">
                  — {etiquetarFuerzaCorrelacion(correlacion.resultado.interpretacion)}
                </span>
              </div>
              <div className="mt-3">
                <EChartBox
                  option={opcionCorrelacion}
                  height={250}
                  ariaLabel="Diagrama de dispersión y recta de regresión OLS"
                />
              </div>
            </>
          )}
        </section>

        {/* Comparativa de Parcelas (6 cols) */}
        <section className="surface-card flex flex-col justify-between gap-4 p-5 xl:col-span-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <SlidersHorizontal
                className="h-4 w-4 text-[var(--status-info)]"
                aria-hidden="true"
              />
              <div>
                <h2 className="text-base font-semibold text-[var(--text-primary)]">
                  Balance Hídrico Comparativo por Parcela
                </h2>
                <p className="text-xs text-[var(--text-secondary)]">
                  Humedad actual (%) vs consumo histórico acumulado (L).
                </p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                Humedad Edáfica (%)
              </h3>
              <EChartBox
                option={opcionHumedadParcelas}
                height={240}
                ariaLabel="Humedad comparativa entre parcelas"
              />
            </div>
            <div>
              <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                Volumen Aplicado (L)
              </h3>
              <EChartBox
                option={opcionConsumoParcelas}
                height={240}
                ariaLabel="Consumo de riego acumulado por parcela"
              />
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
