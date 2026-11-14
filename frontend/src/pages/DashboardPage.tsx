import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  BellRing,
  Check,
  CloudRain,
  Copy,
  Droplets,
  MapPin,
  Radio,
  Search,
  Sparkles,
} from "lucide-react";
import type { EChartsCoreOption } from "echarts";
import { toast } from "sonner";
import { EChartBox, obtenerPaletaECharts } from "../components/charts/EChartBox";
import { Badge, SeveridadBadge } from "../components/common/Badge";
import { useApp } from "../context/AppContext";
import { api } from "../lib/api";
import {
  etiquetarProveedorIA,
  etiquetarTipoEstacion,
  formatearFechaHora,
  formatearHaceMinutos,
  formatearNumero,
  limpiarTextoCopiloto,
  minutosDesdeEpoch,
  nombreLegibleVariable,
} from "../lib/formatters";
import type {
  PronosticoPunto,
  ReportePulsoIA,
  ResumenPulso24h,
  SeriesResponse,
  TipoEstacion,
} from "../types/aquaterra";

export function DashboardPage() {
  const {
    resumenRadar,
    entradasRadar,
    estacionActivaId,
    setEstacionActivaId,
    estacionActiva,
    setVistaActiva,
    recargarGlobal,
    cargandoGlobal,
    temaEfectivo,
  } = useApp();

  const [filtroTexto, setFiltroTexto] = useState("");
  const [filtroTipo, setFiltroTipo] = useState<string>("");
  const [soloAlertas, setSoloAlertas] = useState(false);

  const [pulsoDetalle, setPulsoDetalle] = useState<ResumenPulso24h | null>(null);
  const [pronostico, setPronostico] = useState<PronosticoPunto[]>([]);
  const [seriesFoco, setSeriesFoco] = useState<SeriesResponse | null>(null);
  const [cargandoEstacion, setCargandoEstacion] = useState(false);

  const [narrativaIA, setNarrativaIA] = useState<{
    mensaje: string;
    proveedor: string;
    estacionId: number;
    reporte?: ReportePulsoIA | null;
  } | null>(null);
  const [narrando, setNarrando] = useState(false);
  const [notificando, setNotificando] = useState(false);
  const [copiado, setCopiado] = useState(false);
  const [sembrando, setSembrando] = useState(false);

  const cargarDetalleEstacion = useCallback(
    async (id: number, esObsoleto?: () => boolean) => {
      setCargandoEstacion(true);
      try {
        const [pulsoResp, climaResp, seriesResp] = await Promise.all([
          api.get<{ pulso: ResumenPulso24h }>(
            `/api/estaciones/${id}/pulso?ventana_horas=24`
          ),
          api.get<{ puntos: PronosticoPunto[] }>(
            `/api/estaciones/${id}/pronostico?horas=48`
          ),
          api.get<SeriesResponse>(`/api/estaciones/${id}/series?horas=24`),
        ]);
        if (esObsoleto?.()) return;
        setPulsoDetalle(pulsoResp.pulso);
        setPronostico(climaResp.puntos ?? []);
        setSeriesFoco(seriesResp);
      } catch {
        if (esObsoleto?.()) return;
        setPulsoDetalle(null);
        setPronostico([]);
        setSeriesFoco(null);
      } finally {
        if (!esObsoleto?.()) setCargandoEstacion(false);
      }
    },
    []
  );

  useEffect(() => {
    if (estacionActivaId === null) return;
    let cancelado = false;
    void cargarDetalleEstacion(estacionActivaId, () => cancelado);
    return () => {
      cancelado = true;
    };
  }, [estacionActivaId, cargarDetalleEstacion]);

  const entradasFiltradas = useMemo(() => {
    const q = filtroTexto.trim().toLowerCase();
    return entradasRadar.filter((e) => {
      if (filtroTipo && e.estacion.tipo !== filtroTipo) return false;
      if (
        soloAlertas &&
        e.severidad !== "critico" &&
        e.severidad !== "atencion"
      ) {
        return false;
      }
      if (!q) return true;
      return (
        e.estacion.codigo.toLowerCase().includes(q) ||
        e.estacion.nombre.toLowerCase().includes(q) ||
        (e.diagnostico_resumen ?? "").toLowerCase().includes(q) ||
        (e.parcelas_asociadas ?? []).some((p) => p.toLowerCase().includes(q))
      );
    });
  }, [entradasRadar, filtroTexto, filtroTipo, soloAlertas]);

  const completitudMedia = useMemo(() => {
    if (entradasRadar.length === 0) return 0;
    const suma = entradasRadar.reduce(
      (acc, e) => acc + (e.completitud_24h_pct ?? 0),
      0
    );
    return suma / entradasRadar.length;
  }, [entradasRadar]);

  const handleNarrar24h = async () => {
    if (estacionActivaId === null) {
      toast.error("Selecciona una estación primero.");
      return;
    }
    setNarrando(true);
    try {
      const resp = await api.post<{
        estacion_id: number;
        mensaje: string;
        proveedor_ia: string;
        reporte?: ReportePulsoIA | null;
      }>(`/api/estaciones/${estacionActivaId}/narrar-24h`);
      setNarrativaIA({
        mensaje: resp.mensaje,
        proveedor: resp.proveedor_ia,
        estacionId: resp.estacion_id,
        reporte: resp.reporte ?? null,
      });
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "No se pudo generar la narrativa."
      );
    } finally {
      setNarrando(false);
    }
  };

  const handleNotificar24h = async () => {
    if (estacionActivaId === null) return;
    setNotificando(true);
    try {
      const resp = await api.post<{
        mensaje: string;
        envios: Record<string, boolean>;
      }>("/api/sistema/notificar-24h", { estacion_id: estacionActivaId });
      setNarrativaIA({
        mensaje: resp.mensaje,
        proveedor: "alerta-despacho",
        estacionId: estacionActivaId,
      });
      const canales = Object.entries(resp.envios ?? {})
        .filter(([, ok]) => ok)
        .map(([k]) => k);
      toast.success(
        canales.length > 0
          ? `Reporte 24h despachado por: ${canales.join(", ")}`
          : "Reporte 24h generado localmente (sin webhooks externos activos)."
      );
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Error enviando alerta 24h."
      );
    } finally {
      setNotificando(false);
    }
  };

  const handleSembrarBase = async () => {
    setSembrando(true);
    try {
      await api.post("/api/estaciones/sembrar-base");
      await recargarGlobal();
      toast.success("Estaciones base TerraBit sembradas en SQLite WAL.");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "No se pudieron sembrar estaciones."
      );
    } finally {
      setSembrando(false);
    }
  };

  const handleCopiar = async () => {
    if (!narrativaIA?.mensaje) return;
    try {
      await navigator.clipboard.writeText(narrativaIA.mensaje);
      setCopiado(true);
      window.setTimeout(() => setCopiado(false), 1800);
    } catch {
      toast.error("No se pudo copiar al portapapeles.");
    }
  };

  // Sparkline de la estación focal para el KPI 4
  const sparklineOption = useMemo<EChartsCoreOption>(() => {
    const pal = obtenerPaletaECharts(temaEfectivo);
    const claves = Object.keys(seriesFoco?.series ?? {});
    const clavePreferida =
      claves.find((k) => k.includes("humedad_suelo")) ??
      claves.find((k) => k.includes("temp")) ??
      claves[0];
    const pts = (clavePreferida ? seriesFoco?.series[clavePreferida] : []) ?? [];
    const data = pts.slice(-24).map(([ts, val]) => [ts * 1000, val]);

    return {
      grid: { left: 0, right: 0, top: 4, bottom: 2 },
      xAxis: { type: "time", show: false },
      yAxis: { type: "value", show: false, scale: true },
      series: [
        {
          type: "line",
          data,
          smooth: 0.35,
          showSymbol: false,
          lineStyle: { color: pal.accent, width: 2 },
          areaStyle: {
            color:
              temaEfectivo === "dark"
                ? "rgba(52, 211, 153, 0.16)"
                : "rgba(5, 150, 105, 0.14)",
          },
        },
      ],
    };
  }, [seriesFoco, temaEfectivo]);

  // Gráfico combinado Open-Meteo 48h
  const climaOption = useMemo<EChartsCoreOption>(() => {
    const pal = obtenerPaletaECharts(temaEfectivo);
    const slice = pronostico.slice(0, 48);
    const fechas = slice.map((p) => {
      const d = new Date(p.ts_objetivo_epoch * 1000);
      return `${d.getDate()}/${d.getMonth() + 1} ${String(
        d.getHours()
      ).padStart(2, "0")}:00`;
    });
    const lluvia = slice.map((p) => p.lluvia_mm ?? 0);
    const temp = slice.map((p) => p.temp_c ?? null);

    return {
      tooltip: {
        trigger: "axis",
        backgroundColor: pal.surface,
        borderColor: pal.borderSubtle,
        textStyle: { color: pal.textPrimary, fontSize: 12 },
      },
      legend: {
        top: 0,
        right: 0,
        textStyle: { color: pal.textSecondary, fontSize: 11 },
        itemWidth: 12,
        itemHeight: 8,
      },
      grid: { left: 36, right: 36, top: 34, bottom: 26 },
      xAxis: {
        type: "category",
        data: fechas,
        axisLine: { lineStyle: { color: pal.borderSubtle } },
        axisLabel: { color: pal.textMuted, fontSize: 10 },
      },
      yAxis: [
        {
          type: "value",
          name: "mm",
          nameTextStyle: { color: pal.textMuted, fontSize: 10 },
          splitLine: { lineStyle: { color: pal.borderSubtle } },
          axisLabel: { color: pal.textMuted, fontSize: 10 },
        },
        {
          type: "value",
          name: "°C",
          nameTextStyle: { color: pal.textMuted, fontSize: 10 },
          splitLine: { show: false },
          axisLabel: { color: pal.textMuted, fontSize: 10 },
        },
      ],
      series: [
        {
          name: "Lluvia (mm)",
          type: "bar",
          data: lluvia,
          barMaxWidth: 10,
          itemStyle: { color: pal.info, borderRadius: [3, 3, 0, 0] },
        },
        {
          name: "Temp (°C)",
          type: "line",
          yAxisIndex: 1,
          data: temp,
          smooth: true,
          showSymbol: false,
          lineStyle: { color: pal.warning, width: 2 },
          itemStyle: { color: pal.warning },
        },
      ],
    };
  }, [pronostico, temaEfectivo]);

  const variablesLista = useMemo(() => {
    const vars = pulsoDetalle?.variables ?? {};
    return Object.values(vars).map((v) => ({
      clave: v.variable,
      nombre: nombreLegibleVariable(v.variable),
      unidad: v.unidad ?? "",
      ultimo: v.ultimo_valor,
      promedio: v.media_24h,
      minimo: v.min_24h,
      maximo: v.max_24h,
      muestras: v.muestras ?? 0,
    }));
  }, [pulsoDetalle]);

  const indicadoresEspecializados = useMemo(() => {
    if (!pulsoDetalle) return [];
    const bloque =
      pulsoDetalle.inti ??
      pulsoDetalle.inbeersa ??
      pulsoDetalle.sigatoka ??
      pulsoDetalle.conservacion;
    if (!bloque) return [];
    return Object.entries(bloque)
      .filter(([, val]) => val !== null && val !== undefined && val !== "")
      .map(([clave, val]) => ({
        clave,
        nombre: nombreLegibleVariable(clave),
        valor:
          typeof val === "number"
            ? formatearNumero(val, 1)
            : typeof val === "boolean"
              ? val
                ? "Sí"
                : "No"
              : String(val),
      }));
  }, [pulsoDetalle]);

  return (
    <div className="space-y-6">
      {/* Encabezado limpio de página */}
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)]">
            Radar General del Ecosistema
          </h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            Priorización automática por severidad bio-física, completitud 24h y
            pronóstico hiperlocal Open-Meteo.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {entradasRadar.length === 0 && (
            <button
              type="button"
              onClick={() => void handleSembrarBase()}
              disabled={sembrando}
              className="inline-flex items-center gap-2 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-surface)] px-3.5 py-2 text-xs font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-elevated)]"
            >
              <Radio className="h-3.5 w-3.5 text-[var(--accent-primary)]" aria-hidden="true" />
              {sembrando ? "Sembrando…" : "Sembrar nodos TerraBit"}
            </button>
          )}
          <button
            type="button"
            onClick={() => void handleNarrar24h()}
            disabled={narrando || estacionActivaId === null}
            className="inline-flex items-center gap-2 rounded-xl bg-[var(--accent-primary)] px-4 py-2 text-xs font-semibold text-[var(--accent-contrast)] transition-colors hover:bg-[var(--accent-primary-hover)] disabled:opacity-50"
          >
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
            {narrando ? "Analizando pulso…" : "Narrar 24h con IA"}
          </button>
          <button
            type="button"
            onClick={() => void handleNotificar24h()}
            disabled={notificando || estacionActivaId === null}
            className="inline-flex items-center gap-2 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-3.5 py-2 text-xs font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] disabled:opacity-50"
          >
            <BellRing className="h-3.5 w-3.5 text-[var(--status-info)]" aria-hidden="true" />
            {notificando ? "Enviando…" : "Despachar alerta 24h"}
          </button>
        </div>
      </div>

      {/* Banner Editorial Narrativa IA */}
      {(narrando || narrativaIA) && (
        <section
          aria-label="Narrativa agronómica generada por IA"
          className="surface-card border-l-4 border-l-[var(--accent-primary)] p-4 sm:p-5"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Sparkles
                className="h-4 w-4 text-[var(--accent-primary)]"
                aria-hidden="true"
              />
              <span className="text-xs font-semibold uppercase tracking-wider text-[var(--accent-primary)]">
                Informe Ejecutivo 24h ·{" "}
                {narrativaIA?.reporte?.estacion ??
                  estacionActiva?.nombre ??
                  `Estación #${narrativaIA?.estacionId}`}
              </span>
              {narrativaIA?.reporte && (
                <SeveridadBadge severidad={narrativaIA.reporte.severidad} />
              )}
              {narrativaIA && (
                <Badge tono="neutral">
                  {narrativaIA.reporte?.proveedor_legible ??
                    etiquetarProveedorIA(narrativaIA.proveedor)}
                </Badge>
              )}
            </div>
            {narrativaIA && (
              <button
                type="button"
                onClick={() => void handleCopiar()}
                className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-2.5 py-1 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              >
                {copiado ? (
                  <Check className="h-3.5 w-3.5 text-[var(--status-optimal)]" aria-hidden="true" />
                ) : (
                  <Copy className="h-3.5 w-3.5" aria-hidden="true" />
                )}
                {copiado ? "Copiado" : "Copiar informe"}
              </button>
            )}
          </div>

          {narrando ? (
            <div className="mt-3 space-y-2">
              <div className="skeleton h-3.5 w-11/12" />
              <div className="skeleton h-3.5 w-3/4" />
            </div>
          ) : narrativaIA?.reporte ? (
            <div className="mt-3 space-y-3">
              {narrativaIA.reporte.lecturas.length > 0 && (
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
                  {narrativaIA.reporte.lecturas.map((lec) => (
                    <div
                      key={lec.clave}
                      className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-3 py-2"
                    >
                      <div className="truncate text-[10px] font-medium text-[var(--text-muted)]">
                        {lec.nombre}
                      </div>
                      <div className="tabular-nums mt-0.5 font-mono text-sm font-semibold text-[var(--text-primary)]">
                        {formatearNumero(lec.valor, 1, lec.unidad ? ` ${lec.unidad}` : "")}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {narrativaIA.reporte.alertas.length > 0 && (
                <div className="rounded-xl border border-[color-mix(in_srgb,var(--status-warning)_35%,transparent)] bg-[var(--status-warning-soft)] px-3.5 py-2.5 text-xs text-[var(--text-primary)]">
                  <span className="font-semibold text-[var(--status-warning)]">
                    Alertas en ventana:{" "}
                  </span>
                  {narrativaIA.reporte.alertas.join(" · ")}
                </div>
              )}

              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <div className="rounded-xl bg-[var(--bg-elevated)] p-3.5">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                    Diagnóstico Técnico
                  </div>
                  <p className="mt-1.5 text-sm leading-relaxed text-[var(--text-primary)]">
                    {limpiarTextoCopiloto(narrativaIA.reporte.diagnostico)}
                  </p>
                </div>
                <div className="rounded-xl bg-[var(--bg-elevated)] p-3.5">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-[var(--accent-primary)]">
                    Recomendación Agronómica
                  </div>
                  <p className="mt-1.5 text-sm leading-relaxed text-[var(--text-primary)]">
                    {limpiarTextoCopiloto(narrativaIA.reporte.justificacion)}
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <p className="mt-2.5 whitespace-pre-wrap text-sm leading-relaxed text-[var(--text-primary)]">
              {limpiarTextoCopiloto(narrativaIA?.mensaje ?? "")}
            </p>
          )}
        </section>
      )}

      {/* 4 KPI Cards Minimalistas */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div className="surface-card p-5">
          <div className="flex items-center justify-between text-xs font-medium text-[var(--text-secondary)]">
            <span>Estaciones Monitoreadas</span>
            <Radio className="h-4 w-4 text-[var(--accent-primary)]" aria-hidden="true" />
          </div>
          <div className="tabular-nums mt-2 text-3xl font-bold tracking-tight text-[var(--text-primary)]">
            {resumenRadar?.total_estaciones ?? 0}
          </div>
          <div className="mt-2 flex items-center gap-2 text-xs text-[var(--text-secondary)]">
            <span className="text-[var(--status-optimal)]">
              {resumenRadar?.optimas ?? 0} óptimas
            </span>
            <span>·</span>
            <span>{resumenRadar?.sin_datos ?? 0} sin datos</span>
          </div>
        </div>

        <div className="surface-card p-5">
          <div className="flex items-center justify-between text-xs font-medium text-[var(--text-secondary)]">
            <span>Nodos en Alerta</span>
            <AlertTriangle
              className={`h-4 w-4 ${
                (resumenRadar?.criticas ?? 0) > 0
                  ? "text-[var(--status-critical)]"
                  : "text-[var(--status-warning)]"
              }`}
              aria-hidden="true"
            />
          </div>
          <div className="tabular-nums mt-2 text-3xl font-bold tracking-tight text-[var(--text-primary)]">
            {(resumenRadar?.criticas ?? 0) + (resumenRadar?.atenciones ?? 0)}
          </div>
          <div className="mt-2 flex items-center gap-2 text-xs">
            <span className="text-[var(--status-critical)]">
              {resumenRadar?.criticas ?? 0} críticas
            </span>
            <span className="text-[var(--text-muted)]">·</span>
            <span className="text-[var(--status-warning)]">
              {resumenRadar?.atenciones ?? 0} atención
            </span>
          </div>
        </div>

        <div className="surface-card p-5">
          <div className="flex items-center justify-between text-xs font-medium text-[var(--text-secondary)]">
            <span>Parcelas Productivas</span>
            <MapPin className="h-4 w-4 text-[var(--status-info)]" aria-hidden="true" />
          </div>
          <div className="tabular-nums mt-2 text-3xl font-bold tracking-tight text-[var(--text-primary)]">
            {resumenRadar?.parcelas_activas ?? 0}
          </div>
          <div className="mt-2">
            <button
              type="button"
              onClick={() => setVistaActiva("parcelas")}
              className="inline-flex items-center gap-1 text-xs font-medium text-[var(--accent-primary)] hover:underline"
            >
              Gestionar inventario
              <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          </div>
        </div>

        <div className="surface-card flex flex-col justify-between p-5">
          <div className="flex items-center justify-between text-xs font-medium text-[var(--text-secondary)]">
            <span>Completitud Media 24h</span>
            <Activity className="h-4 w-4 text-[var(--accent-primary)]" aria-hidden="true" />
          </div>
          <div className="mt-1 flex items-end justify-between gap-3">
            <div className="tabular-nums text-3xl font-bold tracking-tight text-[var(--text-primary)]">
              {formatearNumero(completitudMedia, 0, "%")}
            </div>
            <div className="w-28 shrink-0">
              <EChartBox
                option={sparklineOption}
                height={42}
                ariaLabel="Mini tendencia de señal focal 24 horas"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Bento Grid 12 columnas */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
        {/* Radar Priorizado (7 cols) */}
        <section className="surface-card flex flex-col xl:col-span-7">
          <div className="flex flex-col justify-between gap-3 border-b border-[var(--border-subtle)] p-4 sm:flex-row sm:items-center sm:px-5">
            <div>
              <h2 className="text-base font-semibold text-[var(--text-primary)]">
                Radar Priorizado de Estaciones
              </h2>
              <p className="text-xs text-[var(--text-secondary)]">
                Haz clic en una fila para inspeccionar su pulso y pronóstico.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search
                  className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--text-muted)]"
                  aria-hidden="true"
                />
                <input
                  type="search"
                  value={filtroTexto}
                  onChange={(e) => setFiltroTexto(e.target.value)}
                  placeholder="Filtrar estación..."
                  aria-label="Filtrar estaciones del radar"
                  className="h-8 w-40 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] pl-8 pr-2.5 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)]"
                />
              </div>

              <select
                value={filtroTipo}
                onChange={(e) => setFiltroTipo(e.target.value)}
                aria-label="Filtrar por familia TerraBit"
                className="h-8 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-2.5 text-xs text-[var(--text-primary)]"
              >
                <option value="">Todas las familias</option>
                {(
                  [
                    "terrabit_inti",
                    "inbeersa",
                    "sigatoka",
                    "conservacion",
                    "otro",
                  ] as TipoEstacion[]
                ).map((t) => (
                  <option key={t} value={t}>
                    {etiquetarTipoEstacion(t)}
                  </option>
                ))}
              </select>

              <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-2.5 py-1.5 text-xs text-[var(--text-secondary)]">
                <input
                  type="checkbox"
                  checked={soloAlertas}
                  onChange={(e) => setSoloAlertas(e.target.checked)}
                />
                Solo alertas
              </label>
            </div>
          </div>

          <div className="overflow-x-auto">
            {cargandoGlobal && entradasRadar.length === 0 ? (
              <div className="space-y-3 p-5">
                <div className="skeleton h-10 w-full" />
                <div className="skeleton h-10 w-full" />
                <div className="skeleton h-10 w-full" />
              </div>
            ) : entradasFiltradas.length === 0 ? (
              <div className="p-8 text-center text-sm text-[var(--text-secondary)]">
                No hay estaciones que coincidan con el filtro aplicado.
              </div>
            ) : (
              <table className="w-full border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b border-[var(--border-subtle)] text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                    <th scope="col" className="px-5 py-3">
                      Estación
                    </th>
                    <th scope="col" className="px-3 py-3">
                      Estado
                    </th>
                    <th scope="col" className="px-3 py-3">
                      Completitud
                    </th>
                    <th scope="col" className="px-3 py-3">
                      KPI &amp; Alertas
                    </th>
                    <th scope="col" className="px-4 py-3 text-right">
                      Pulso
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-subtle)]">
                  {entradasFiltradas.map((entry) => {
                    const sel = entry.estacion.id === estacionActivaId;
                    const pct = Math.max(
                      0,
                      Math.min(100, entry.completitud_24h_pct ?? 0)
                    );
                    const mins = minutosDesdeEpoch(entry.ultimo_ts_epoch);
                    return (
                      <tr
                        key={entry.estacion.id}
                        onClick={() => setEstacionActivaId(entry.estacion.id)}
                        className={`cursor-pointer transition-colors ${
                          sel
                            ? "bg-[var(--accent-primary-soft)]"
                            : "hover:bg-[var(--bg-elevated)]"
                        }`}
                      >
                        <td className="px-5 py-3.5">
                          <div className="font-semibold text-[var(--text-primary)]">
                            {entry.estacion.nombre}
                          </div>
                          <div className="mt-0.5 flex items-center gap-2 font-mono text-[11px] text-[var(--text-muted)]">
                            <span>{entry.estacion.codigo}</span>
                            <span>·</span>
                            <span>
                              {etiquetarTipoEstacion(entry.estacion.tipo)}
                            </span>
                          </div>
                        </td>
                        <td className="px-3 py-3.5 align-middle">
                          <SeveridadBadge severidad={entry.severidad} />
                        </td>
                        <td className="px-3 py-3.5 align-middle">
                          <div className="w-24">
                            <div className="tabular-nums text-xs font-medium text-[var(--text-primary)]">
                              {formatearNumero(pct, 0, "%")}
                            </div>
                            <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-[var(--bg-subtle)]">
                              <div
                                className="h-full rounded-full bg-[var(--accent-primary)]"
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                          </div>
                        </td>
                        <td className="max-w-[230px] px-3 py-3.5">
                          <div className="truncate font-mono text-xs text-[var(--text-primary)]">
                            {entry.diagnostico_resumen || "Sin lecturas 24h"}
                          </div>
                          <div className="mt-0.5 truncate text-[11px] text-[var(--text-secondary)]">
                            {entry.alertas_activas > 0
                              ? `${entry.alertas_activas} alerta(s) activa(s)`
                              : formatearHaceMinutos(mins)}
                          </div>
                        </td>
                        <td className="px-4 py-3.5 text-right">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setEstacionActivaId(entry.estacion.id);
                              setVistaActiva("telemetria");
                            }}
                            className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-2.5 py-1 text-xs font-medium text-[var(--text-primary)] hover:border-[var(--accent-primary)] hover:text-[var(--accent-primary)]"
                          >
                            Analizar
                            <ArrowUpRight className="h-3 w-3" aria-hidden="true" />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </section>

        {/* Columna derecha: Detalle Focal + Clima 48h (5 cols) */}
        <div className="flex flex-col gap-6 xl:col-span-5">
          {/* Detalle de variables de la estación seleccionada */}
          <section className="surface-card p-5">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="font-mono text-[11px] uppercase tracking-wider text-[var(--accent-primary)]">
                  {estacionActiva
                    ? `${estacionActiva.codigo} · ${etiquetarTipoEstacion(
                        estacionActiva.tipo
                      )}`
                    : "Estación Focal"}
                </div>
                <h2 className="mt-0.5 text-base font-semibold text-[var(--text-primary)]">
                  {estacionActiva?.nombre ?? "Selecciona una estación"}
                </h2>
              </div>
              {pulsoDetalle && (
                <SeveridadBadge severidad={pulsoDetalle.severidad} />
              )}
            </div>

            {cargandoEstacion ? (
              <div className="mt-4 space-y-2.5">
                <div className="skeleton h-9 w-full" />
                <div className="skeleton h-9 w-full" />
                <div className="skeleton h-9 w-3/4" />
              </div>
            ) : !pulsoDetalle || variablesLista.length === 0 ? (
              <div className="mt-4 rounded-xl bg-[var(--bg-elevated)] p-4 text-xs text-[var(--text-secondary)]">
                Esta estación no registra muestras en la ventana de las últimas
                24 horas. Puedes ingerir tramas USB/LoRa o importar CSV desde{" "}
                <button
                  type="button"
                  onClick={() => setVistaActiva("hardware")}
                  className="font-semibold text-[var(--accent-primary)] hover:underline"
                >
                  Hardware IoT
                </button>
                .
              </div>
            ) : (
              <>
                <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-[var(--text-secondary)]">
                  <span className="tabular-nums">
                    Completitud 24h:{" "}
                    <strong className="text-[var(--text-primary)]">
                      {formatearNumero(pulsoDetalle.completitud_global_pct, 0, "%")}
                    </strong>{" "}
                    (
                    {variablesLista.reduce((acc, v) => acc + v.muestras, 0)} pts)
                  </span>
                  <span>·</span>
                  <span>
                    Corte: {formatearFechaHora(pulsoDetalle.hasta_epoch)}
                  </span>
                </div>

                {(pulsoDetalle.alertas_detectadas?.length ?? 0) > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {pulsoDetalle.alertas_detectadas.map((a, idx) => (
                      <Badge key={idx} tono="warning">
                        {a}
                      </Badge>
                    ))}
                  </div>
                )}

                <div className="mt-4 grid grid-cols-2 gap-2.5 sm:grid-cols-3">
                  {variablesLista.slice(0, 6).map((v) => (
                    <div
                      key={v.clave}
                      className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3"
                    >
                      <div className="truncate text-[11px] text-[var(--text-secondary)]">
                        {v.nombre}
                      </div>
                      <div className="tabular-nums mt-1 font-mono text-base font-semibold text-[var(--text-primary)]">
                        {formatearNumero(v.ultimo ?? v.promedio, 1, v.unidad ? ` ${v.unidad}` : "")}
                      </div>
                      <div className="tabular-nums mt-0.5 text-[10px] text-[var(--text-muted)]">
                        {formatearNumero(v.minimo, 1)} –{" "}
                        {formatearNumero(v.maximo, 1)} ({v.muestras} pts)
                      </div>
                    </div>
                  ))}
                </div>

                {indicadoresEspecializados.length > 0 && (
                  <div className="mt-3 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-canvas)]/60 p-3">
                    <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-[var(--accent-primary)]">
                      Indicadores Agronómicos de Familia
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      {indicadoresEspecializados.slice(0, 6).map((ind) => (
                        <div
                          key={ind.clave}
                          className="flex items-center justify-between gap-2 rounded-lg bg-[var(--bg-elevated)] px-2.5 py-1.5"
                        >
                          <span className="truncate text-[11px] text-[var(--text-secondary)]">
                            {ind.nombre}
                          </span>
                          <span className="tabular-nums font-mono font-semibold text-[var(--text-primary)]">
                            {ind.valor}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </section>

          {/* Pronóstico Open-Meteo 48h */}
          <section className="surface-card p-5">
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CloudRain
                  className="h-4 w-4 text-[var(--status-info)]"
                  aria-hidden="true"
                />
                <h2 className="text-base font-semibold text-[var(--text-primary)]">
                  Pronóstico Hiperlocal 48h
                </h2>
              </div>
              <span className="font-mono text-[11px] text-[var(--text-muted)]">
                Open-Meteo caché
              </span>
            </div>

            {pronostico.length === 0 ? (
              <div className="flex flex-col items-start gap-2 rounded-xl bg-[var(--bg-elevated)] p-4 text-xs text-[var(--text-secondary)]">
                <div className="flex items-center gap-2 font-medium text-[var(--text-primary)]">
                  <Droplets className="h-4 w-4 text-[var(--status-info)]" aria-hidden="true" />
                  Sin serie horaria descargada para esta estación.
                </div>
                <p>
                  Pulsa &ldquo;Sincronizar&rdquo; en la barra superior para
                  obtener lluvia esperada (mm) y temperatura.
                </p>
              </div>
            ) : (
              <EChartBox
                option={climaOption}
                height={220}
                ariaLabel="Gráfica de lluvia y temperatura esperada en las próximas 48 horas"
              />
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
