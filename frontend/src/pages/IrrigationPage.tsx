import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  Activity,
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  Droplets,
  Gauge,
  Loader2,
  ShieldAlert,
  ShieldCheck,
  Waves,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "../components/common/Badge";
import { useApp } from "../context/AppContext";
import { api, ApiError } from "../lib/api";
import {
  formatearFechaHora,
  formatearFechaIso,
  formatearNumero,
  nombreLegibleVariable,
} from "../lib/formatters";
import type { ContextoRiegoResponse, Parcela } from "../types/aquaterra";

type TabRiego = "programados" | "historial" | "incidencias";

export function IrrigationPage() {
  const { usuario, recargarGlobal } = useApp();
  const puedeOperar = usuario?.rol === "admin" || usuario?.rol === "operador";

  const [parcelas, setParcelas] = useState<Parcela[]>([]);
  const [parcelaId, setParcelaId] = useState<number | null>(null);
  const [umbral, setUmbral] = useState<number>(45);
  const [contexto, setContexto] = useState<ContextoRiegoResponse | null>(null);
  const [cargando, setCargando] = useState(true);

  const hoyIso = new Date().toISOString().slice(0, 10);
  const [litrosAplicar, setLitrosAplicar] = useState("120");
  const [fechaIso, setFechaIso] = useState(hoyIso);
  const [hora, setHora] = useState("06:30");
  const [aperturaPct, setAperturaPct] = useState("100");
  const [modoVerif, setModoVerif] = useState("sin_sensor_actuador");
  const [mantConfirmado, setMantConfirmado] = useState(false);
  const [enviandoRiego, setEnviandoRiego] = useState(false);

  // Formulario incidencia ΔθA / ΔθB
  const [eventoSelId, setEventoSelId] = useState<string>("");
  const [humAAntes, setHumAAntes] = useState("38");
  const [humADespues, setHumADespues] = useState("54");
  const [humBAntes, setHumBAntes] = useState("");
  const [humBDespues, setHumBDespues] = useState("");
  const [caudalLpm, setCaudalLpm] = useState("");
  const [corrienteA, setCorrienteA] = useState("");
  const [enviandoIncidencia, setEnviandoIncidencia] = useState(false);

  const [tab, setTab] = useState<TabRiego>("programados");

  const cargarParcelas = useCallback(async () => {
    try {
      const resp = await api.get<{ parcelas: Parcela[] }>("/api/parcelas");
      const list = resp.parcelas ?? [];
      setParcelas(list);
      setParcelaId((prev) =>
        prev && list.some((p) => p.id === prev) ? prev : list[0]?.id ?? null
      );
    } catch {
      setParcelas([]);
    }
  }, []);

  const cargarContexto = useCallback(
    async (id: number, umbralPct: number) => {
      setCargando(true);
      try {
        const resp = await api.get<ContextoRiegoResponse>(
          `/api/parcelas/${id}/riego/contexto?umbral_pct=${umbralPct}`
        );
        setContexto(resp);
        if (resp.modos_verificacion?.length) {
          setModoVerif((prev) =>
            resp.modos_verificacion.includes(prev)
              ? prev
              : resp.modos_verificacion[0]
          );
        }
        if (resp.historial?.length) {
          setEventoSelId((prev) =>
            prev && resp.historial.some((h) => String(h.id) === prev)
              ? prev
              : String(resp.historial[0].id)
          );
        } else {
          setEventoSelId("");
        }
        if (resp.recomendacion.litros_sugeridos > 0) {
          setLitrosAplicar(String(Math.round(resp.recomendacion.litros_sugeridos)));
        }
      } catch (err) {
        toast.error(
          err instanceof Error
            ? err.message
            : "Error cargando contexto de riego."
        );
      } finally {
        setCargando(false);
      }
    },
    []
  );

  useEffect(() => {
    void cargarParcelas();
  }, [cargarParcelas]);

  useEffect(() => {
    if (parcelaId !== null) {
      void cargarContexto(parcelaId, umbral);
    } else {
      setCargando(false);
    }
  }, [parcelaId, umbral, cargarContexto]);

  const handleAplicarRiego = async (e: FormEvent) => {
    e.preventDefault();
    if (parcelaId === null) return;
    setEnviandoRiego(true);
    try {
      await api.post(`/api/parcelas/${parcelaId}/riego/aplicar`, {
        umbral_pct: umbral,
        litros: Number(litrosAplicar),
        fecha_iso: fechaIso,
        hora,
      });
      toast.success("Riego aplicado y registrado en historial hidráulico.");
      await Promise.all([cargarContexto(parcelaId, umbral), recargarGlobal()]);
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "No se pudo aplicar el riego."
      );
    } finally {
      setEnviandoRiego(false);
    }
  };

  const handleProgramarRiego = async () => {
    if (parcelaId === null) return;
    setEnviandoRiego(true);
    try {
      const resp = await api.post<{
        veredicto: {
          autorizado: boolean;
          litros_autorizados: number;
          motivos_bloqueo: string[];
          advertencias_recorte: string[];
        };
      }>(`/api/parcelas/${parcelaId}/riego/programar`, {
        fecha_iso: fechaIso,
        hora,
        litros_solicitados: Number(litrosAplicar),
        apertura_solicitada_pct: Number(aperturaPct),
        origen: "manual_ui",
        modo_verificacion: modoVerif,
        mantenimiento_confirmado: mantConfirmado,
      });
      if (resp.veredicto?.autorizado) {
        toast.success(
          `Riego programado: ${resp.veredicto.litros_autorizados} L autorizados.`
        );
      } else {
        toast.warning(
          `Bloqueado por enclavamiento: ${
            resp.veredicto?.motivos_bloqueo?.[0] ?? "Seguridad hidráulica activa"
          }`
        );
      }
      await cargarContexto(parcelaId, umbral);
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.detail : "No se pudo programar el riego."
      );
    } finally {
      setEnviandoRiego(false);
    }
  };

  const handleRegistrarIncidencia = async (e: FormEvent) => {
    e.preventDefault();
    if (!eventoSelId) {
      toast.error("Selecciona un evento de riego previo para evaluar.");
      return;
    }
    setEnviandoIncidencia(true);
    try {
      const resp = await api.post<{
        salud_actuador: { diagnostico_mecanico: string };
        incidencia: { efectividad: string };
      }>("/api/riego/incidencia", {
        evento_riego_id: Number(eventoSelId),
        humedad_a_antes: Number(humAAntes),
        humedad_a_despues: Number(humADespues),
        humedad_b_antes: humBAntes ? Number(humBAntes) : null,
        humedad_b_despues: humBDespues ? Number(humBDespues) : null,
        modo_verificacion: modoVerif,
        apertura_max_pct: Number(aperturaPct),
        caudal_lpm: caudalLpm ? Number(caudalLpm) : null,
        corriente_a: corrienteA ? Number(corrienteA) : null,
      });
      toast.success(
        `Evaluación registrada: ${resp.salud_actuador.diagnostico_mecanico} (${resp.incidencia.efectividad})`
      );
      if (parcelaId !== null) {
        await cargarContexto(parcelaId, umbral);
      }
    } catch (err) {
      toast.error(
        err instanceof ApiError
          ? err.detail
          : "Error registrando evaluación post-riego."
      );
    } finally {
      setEnviandoIncidencia(false);
    }
  };

  const candados =
    contexto?.recomendacion.veredicto_seguridad?.candados ?? [];
  const aprobadoGlobal =
    contexto?.recomendacion.veredicto_seguridad?.autorizado ?? true;

  return (
    <div className="space-y-6">
      {/* Cabecera & selector */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)]">
            Control de Riego e Interlocks Físicos
          </h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            Evaluación secuencial de 5 candados hidráulicos, recomendación
            proactiva y auditoría de bomba post-riego (ΔθA / ΔθB).
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <label
              htmlFor="riego-parcela-select"
              className="text-xs font-medium text-[var(--text-secondary)]"
            >
              Parcela:
            </label>
            <select
              id="riego-parcela-select"
              value={parcelaId ?? ""}
              onChange={(e) =>
                setParcelaId(e.target.value ? Number(e.target.value) : null)
              }
              className="h-9 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-3 text-xs font-semibold text-[var(--text-primary)]"
            >
              {parcelas.length === 0 ? (
                <option value="">Sin parcelas activas</option>
              ) : (
                parcelas.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nombre} ({p.cultivo} · {formatearNumero(p.humedad_pct, 0, "%")})
                  </option>
                ))
              )}
            </select>
          </div>
        </div>
      </div>

      {cargando && !contexto ? (
        <div className="surface-card space-y-3 p-6">
          <div className="skeleton h-8 w-56" />
          <div className="skeleton h-28 w-full" />
        </div>
      ) : !contexto ? (
        <section className="surface-card p-8 text-center text-sm text-[var(--text-secondary)]">
          Registra al menos una parcela en el inventario para habilitar el
          control hidráulico y los 5 candados de seguridad.
        </section>
      ) : (
        <>
          {/* Stepper Horizontal 5 Candados */}
          <section className="surface-card p-5">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                {aprobadoGlobal ? (
                  <ShieldCheck
                    className="h-5 w-5 text-[var(--status-optimal)]"
                    aria-hidden="true"
                  />
                ) : (
                  <ShieldAlert
                    className="h-5 w-5 text-[var(--status-critical)]"
                    aria-hidden="true"
                  />
                )}
                <div>
                  <h2 className="text-base font-semibold text-[var(--text-primary)]">
                    Cadena de Seguridad de 5 Candados Físicos
                  </h2>
                  <p className="text-xs text-[var(--text-secondary)]">
                    {contexto.recomendacion.veredicto_seguridad?.motivos_bloqueo?.[0] ??
                      contexto.recomendacion.veredicto_seguridad?.advertencias_recorte?.[0] ??
                      "Verificación continua de condiciones de campo"}
                  </p>
                </div>
              </div>
              <Badge tono={aprobadoGlobal ? "optimal" : "critical"}>
                {aprobadoGlobal ? "Vía libre para operar" : "Enclavamiento activo"}
              </Badge>
            </div>

            {candados.length === 0 ? (
              <p className="rounded-xl bg-[var(--bg-elevated)] p-3 text-xs text-[var(--text-secondary)]">
                Evaluando candados físicos contra la estación vinculada.
              </p>
            ) : (
              <ol className="grid grid-cols-1 gap-3 md:grid-cols-3 xl:grid-cols-5">
                {candados.map((c, idx) => {
                  const tonoEstilo = !c.superado
                    ? "border-[color-mix(in_srgb,var(--status-critical)_35%,transparent)] bg-[var(--status-critical-soft)]"
                    : c.recorte_aplicado
                    ? "border-[color-mix(in_srgb,var(--status-warning)_35%,transparent)] bg-[var(--status-warning-soft)]"
                    : "border-[color-mix(in_srgb,var(--status-optimal)_30%,transparent)] bg-[var(--status-optimal-soft)]";
                  return (
                    <li
                      key={`${c.codigo}-${idx}`}
                      className={`flex flex-col justify-between rounded-xl border p-3.5 ${tonoEstilo}`}
                    >
                      <div>
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                            Candado {idx + 1}
                          </span>
                          {c.superado ? (
                            <CheckCircle2
                              className={`h-4 w-4 ${
                                c.recorte_aplicado
                                  ? "text-[var(--status-warning)]"
                                  : "text-[var(--status-optimal)]"
                              }`}
                              aria-hidden="true"
                            />
                          ) : (
                            <AlertTriangle
                              className="h-4 w-4 text-[var(--status-critical)]"
                              aria-hidden="true"
                            />
                          )}
                        </div>
                        <div className="mt-1 text-xs font-bold text-[var(--text-primary)]">
                          {nombreLegibleVariable(c.codigo)}
                        </div>
                        <p className="mt-1 text-[11px] leading-snug text-[var(--text-secondary)]">
                          {c.detalle}
                        </p>
                      </div>
                    </li>
                  );
                })}
              </ol>
            )}
          </section>

          {/* Recomendación Proactiva + Formularios Operativos */}
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
            {/* Recomendación & Ejecución (7 cols) */}
            <section className="surface-card flex flex-col justify-between gap-5 p-5 xl:col-span-7">
              <div>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Droplets
                      className="h-4 w-4 text-[var(--accent-primary)]"
                      aria-hidden="true"
                    />
                    <h2 className="text-base font-semibold text-[var(--text-primary)]">
                      Recomendación Proactiva &amp; Despacho
                    </h2>
                  </div>
                  <Badge
                    tono={
                      contexto.recomendacion.regar ? "warning" : "optimal"
                    }
                  >
                    Acción: {contexto.recomendacion.accion}
                  </Badge>
                </div>

                <p className="mt-2 rounded-xl bg-[var(--bg-elevated)] p-3.5 text-xs leading-relaxed text-[var(--text-primary)]">
                  {contexto.recomendacion.justificacion}
                </p>

                <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <div className="surface-elevated p-3">
                    <div className="text-[11px] text-[var(--text-secondary)]">
                      Humedad Actual
                    </div>
                    <div className="tabular-nums mt-1 font-mono text-base font-bold text-[var(--text-primary)]">
                      {formatearNumero(
                        contexto.recomendacion.humedad_actual_pct ??
                          contexto.parcela.humedad_pct,
                        1,
                        "%"
                      )}
                    </div>
                  </div>
                  <div className="surface-elevated p-3">
                    <div className="text-[11px] text-[var(--text-secondary)]">
                      Sugerido / Apertura
                    </div>
                    <div className="tabular-nums mt-1 font-mono text-base font-bold text-[var(--text-primary)]">
                      {formatearNumero(
                        contexto.recomendacion.litros_sugeridos,
                        0,
                        " L"
                      )}
                    </div>
                    <div className="tabular-nums text-[10px] text-[var(--status-info)]">
                      Apertura:{" "}
                      {formatearNumero(
                        contexto.recomendacion.apertura_sugerida_pct,
                        0,
                        "%"
                      )}{" "}
                      · Umbral {contexto.recomendacion.umbral_disparo_pct}%
                    </div>
                  </div>
                  <div className="surface-elevated p-3">
                    <div className="text-[11px] text-[var(--text-secondary)]">
                      Tasa Secado
                    </div>
                    <div className="tabular-nums mt-1 font-mono text-base font-bold text-[var(--text-primary)]">
                      {formatearNumero(
                        contexto.recomendacion.tasa_secado_pct_h,
                        2,
                        " %/h"
                      )}
                    </div>
                  </div>
                  <div className="surface-elevated p-3">
                    <div className="text-[11px] text-[var(--text-secondary)]">
                      Horas hasta estrés
                    </div>
                    <div className="tabular-nums mt-1 font-mono text-base font-bold text-[var(--text-primary)]">
                      {formatearNumero(
                        contexto.recomendacion.horas_hasta_estres,
                        1,
                        " h"
                      )}
                    </div>
                  </div>
                </div>
              </div>

              <form onSubmit={handleAplicarRiego} className="space-y-4 border-t border-[var(--border-subtle)] pt-4">
                <div>
                  <div className="flex items-center justify-between text-xs">
                    <label
                      htmlFor="slider-umbral"
                      className="font-semibold text-[var(--text-primary)]"
                    >
                      Umbral de disparo hídrico (%)
                    </label>
                    <span className="tabular-nums font-mono font-bold text-[var(--accent-primary)]">
                      {umbral}%
                    </span>
                  </div>
                  <input
                    id="slider-umbral"
                    type="range"
                    min={15}
                    max={85}
                    step={1}
                    value={umbral}
                    onChange={(e) => setUmbral(Number(e.target.value))}
                    className="mt-1.5 w-full"
                  />
                </div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
                  <div className="flex flex-col gap-1">
                    <label
                      htmlFor="riego-litros"
                      className="text-xs font-medium text-[var(--text-secondary)]"
                    >
                      Volumen (L)
                    </label>
                    <input
                      id="riego-litros"
                      type="number"
                      min={1}
                      max={5000}
                      step="1"
                      required
                      value={litrosAplicar}
                      onChange={(e) => setLitrosAplicar(e.target.value)}
                      className="tabular-nums h-9 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-3 font-mono text-xs text-[var(--text-primary)]"
                    />
                  </div>

                  <div className="flex flex-col gap-1">
                    <label
                      htmlFor="riego-fecha"
                      className="text-xs font-medium text-[var(--text-secondary)]"
                    >
                      Fecha
                    </label>
                    <input
                      id="riego-fecha"
                      type="date"
                      required
                      value={fechaIso}
                      onChange={(e) => setFechaIso(e.target.value)}
                      className="h-9 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-2.5 text-xs text-[var(--text-primary)]"
                    />
                  </div>

                  <div className="flex flex-col gap-1">
                    <label
                      htmlFor="riego-hora"
                      className="text-xs font-medium text-[var(--text-secondary)]"
                    >
                      Hora
                    </label>
                    <input
                      id="riego-hora"
                      type="time"
                      required
                      value={hora}
                      onChange={(e) => setHora(e.target.value)}
                      className="h-9 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-2.5 text-xs text-[var(--text-primary)]"
                    />
                  </div>

                  <div className="flex flex-col gap-1">
                    <label
                      htmlFor="riego-apertura"
                      className="text-xs font-medium text-[var(--text-secondary)]"
                    >
                      Válvula (%)
                    </label>
                    <input
                      id="riego-apertura"
                      type="number"
                      min={10}
                      max={100}
                      value={aperturaPct}
                      onChange={(e) => setAperturaPct(e.target.value)}
                      className="tabular-nums h-9 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-3 font-mono text-xs text-[var(--text-primary)]"
                    />
                  </div>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-3">
                  <label className="inline-flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                    <input
                      type="checkbox"
                      checked={mantConfirmado}
                      onChange={(e) => setMantConfirmado(e.target.checked)}
                    />
                    Confirmar revisión física de bomba (enclavamiento 5)
                  </label>

                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={!puedeOperar || enviandoRiego}
                      onClick={() => void handleProgramarRiego()}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-elevated)] px-3.5 py-2 text-xs font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-subtle)] disabled:opacity-45"
                    >
                      <CalendarClock className="h-3.5 w-3.5" aria-hidden="true" />
                      Programar validado
                    </button>
                    <button
                      type="submit"
                      disabled={!puedeOperar || enviandoRiego}
                      className="inline-flex items-center gap-1.5 rounded-xl bg-[var(--accent-primary)] px-4 py-2 text-xs font-semibold text-[var(--accent-contrast)] hover:bg-[var(--accent-primary-hover)] disabled:opacity-45"
                    >
                      {enviandoRiego && (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                      )}
                      Aplicar riego ahora
                    </button>
                  </div>
                </div>
              </form>
            </section>

            {/* Salud de Bomba & Auditoría ΔθA / ΔθB (5 cols) */}
            <section className="surface-card flex flex-col justify-between gap-4 p-5 xl:col-span-5">
              <div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Gauge
                      className="h-4 w-4 text-[var(--status-info)]"
                      aria-hidden="true"
                    />
                    <h2 className="text-base font-semibold text-[var(--text-primary)]">
                      Salud de Bomba &amp; ΔθA / ΔθB
                    </h2>
                  </div>
                  {contexto.salud_bomba && (
                    <Badge
                      tono={
                        contexto.salud_bomba.diagnostico_mecanico
                          .toLowerCase()
                          .includes("falla") ||
                        contexto.salud_bomba.diagnostico_mecanico
                          .toLowerCase()
                          .includes("bloqueo")
                          ? "critical"
                          : "optimal"
                      }
                    >
                      {contexto.salud_bomba.diagnostico_mecanico}
                    </Badge>
                  )}
                </div>

                {contexto.salud_bomba ? (
                  <div className="mt-3 rounded-xl bg-[var(--bg-elevated)] p-3.5 text-xs">
                    <div className="flex flex-wrap items-center gap-3 font-mono">
                      <span>
                        Modo:{" "}
                        <strong>{contexto.salud_bomba.modo_verificacion}</strong>
                      </span>
                      <span>·</span>
                      <span className="tabular-nums">
                        Apertura: {contexto.salud_bomba.apertura_max_pct}%
                      </span>
                      {contexto.salud_bomba.caudal_lpm !== null &&
                        contexto.salud_bomba.caudal_lpm !== undefined && (
                          <>
                            <span>·</span>
                            <span className="tabular-nums">
                              Caudal:{" "}
                              {formatearNumero(
                                contexto.salud_bomba.caudal_lpm,
                                1,
                                " L/min"
                              )}
                            </span>
                          </>
                        )}
                      {contexto.salud_bomba.corriente_a !== null &&
                        contexto.salud_bomba.corriente_a !== undefined && (
                          <>
                            <span>·</span>
                            <span className="tabular-nums">
                              Corriente:{" "}
                              {formatearNumero(
                                contexto.salud_bomba.corriente_a,
                                1,
                                " A"
                              )}
                            </span>
                          </>
                        )}
                    </div>
                    <p className="mt-1.5 text-[var(--text-secondary)]">
                      Evento #{contexto.salud_bomba.evento_riego_id} ·{" "}
                      {formatearFechaIso(contexto.salud_bomba.registrado_en)}
                      {contexto.incidencias[0]
                        ? ` · Último ΔθA: ${formatearNumero(
                            contexto.incidencias[0].delta_a_pct,
                            1,
                            "%"
                          )}`
                        : ""}
                    </p>
                  </div>
                ) : (
                  <p className="mt-3 rounded-xl bg-[var(--bg-elevated)] p-3 text-xs text-[var(--text-secondary)]">
                    Sin evaluaciones mecánicas previas en esta parcela.
                  </p>
                )}
              </div>

              <form
                onSubmit={handleRegistrarIncidencia}
                className="space-y-3 border-t border-[var(--border-subtle)] pt-4"
              >
                <div className="flex items-center gap-2 text-xs font-semibold text-[var(--text-primary)]">
                  <Waves className="h-3.5 w-3.5 text-[var(--accent-primary)]" aria-hidden="true" />
                  Registrar verificación post-riego
                </div>

                <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                  <div className="flex flex-col gap-1">
                    <label
                      htmlFor="inc-evento"
                      className="text-[11px] font-medium text-[var(--text-secondary)]"
                    >
                      Evento de riego
                    </label>
                    <select
                      id="inc-evento"
                      value={eventoSelId}
                      onChange={(e) => setEventoSelId(e.target.value)}
                      className="h-9 rounded-lg border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-2.5 text-xs text-[var(--text-primary)]"
                    >
                      {contexto.historial.length === 0 ? (
                        <option value="">Sin eventos previos</option>
                      ) : (
                        contexto.historial.slice(0, 12).map((h) => (
                          <option key={h.id} value={h.id}>
                            #{h.id} · {formatearNumero(h.agua_litros, 0, " L")} (
                            {formatearFechaHora(h.ts_epoch)})
                          </option>
                        ))
                      )}
                    </select>
                  </div>

                  <div className="flex flex-col gap-1">
                    <label
                      htmlFor="inc-modo"
                      className="text-[11px] font-medium text-[var(--text-secondary)]"
                    >
                      Modo verificación
                    </label>
                    <select
                      id="inc-modo"
                      value={modoVerif}
                      onChange={(e) => setModoVerif(e.target.value)}
                      className="h-9 rounded-lg border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-2.5 text-xs text-[var(--text-primary)]"
                    >
                      {contexto.modos_verificacion.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
                  <div className="flex flex-col gap-1">
                    <label htmlFor="ha-antes" className="text-[11px] text-[var(--text-secondary)]">
                      θA Antes (%)
                    </label>
                    <input
                      id="ha-antes"
                      type="number"
                      step="0.1"
                      required
                      value={humAAntes}
                      onChange={(e) => setHumAAntes(e.target.value)}
                      className="tabular-nums h-9 rounded-lg border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-2.5 font-mono text-xs"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label htmlFor="ha-despues" className="text-[11px] text-[var(--text-secondary)]">
                      θA Después (%)
                    </label>
                    <input
                      id="ha-despues"
                      type="number"
                      step="0.1"
                      required
                      value={humADespues}
                      onChange={(e) => setHumADespues(e.target.value)}
                      className="tabular-nums h-9 rounded-lg border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-2.5 font-mono text-xs"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label htmlFor="hb-antes" className="text-[11px] text-[var(--text-secondary)]">
                      θB Antes (%)
                    </label>
                    <input
                      id="hb-antes"
                      type="number"
                      step="0.1"
                      placeholder="Opc."
                      value={humBAntes}
                      onChange={(e) => setHumBAntes(e.target.value)}
                      className="tabular-nums h-9 rounded-lg border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-2.5 font-mono text-xs"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label htmlFor="hb-despues" className="text-[11px] text-[var(--text-secondary)]">
                      θB Después (%)
                    </label>
                    <input
                      id="hb-despues"
                      type="number"
                      step="0.1"
                      placeholder="Opc."
                      value={humBDespues}
                      onChange={(e) => setHumBDespues(e.target.value)}
                      className="tabular-nums h-9 rounded-lg border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-2.5 font-mono text-xs"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2.5">
                  <input
                    type="number"
                    step="0.1"
                    placeholder="Caudal L/min (opcional)"
                    aria-label="Caudal en litros por minuto"
                    value={caudalLpm}
                    onChange={(e) => setCaudalLpm(e.target.value)}
                    className="tabular-nums h-9 rounded-lg border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-2.5 font-mono text-xs"
                  />
                  <input
                    type="number"
                    step="0.1"
                    placeholder="Corriente A (opcional)"
                    aria-label="Corriente eléctrica de bomba en amperios"
                    value={corrienteA}
                    onChange={(e) => setCorrienteA(e.target.value)}
                    className="tabular-nums h-9 rounded-lg border border-[var(--border-strong)] bg-[var(--bg-canvas)] px-2.5 font-mono text-xs"
                  />
                </div>

                <button
                  type="submit"
                  disabled={!eventoSelId || enviandoIncidencia}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-[var(--border-strong)] bg-[var(--bg-elevated)] px-4 py-2 text-xs font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-subtle)] disabled:opacity-45"
                >
                  {enviandoIncidencia ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                  ) : (
                    <Activity className="h-3.5 w-3.5 text-[var(--accent-primary)]" aria-hidden="true" />
                  )}
                  Evaluar efectividad e incidencia mecánica
                </button>
              </form>
            </section>
          </div>

          {/* Bitácora inferior con pestañas */}
          <section className="surface-card overflow-hidden">
            <div className="flex flex-wrap items-center gap-1 border-b border-[var(--border-subtle)] px-4 pt-3">
              {(
                [
                  { id: "programados", etiqueta: `Programados (${contexto.programados.length})` },
                  { id: "historial", etiqueta: `Historial de riegos (${contexto.historial.length})` },
                  { id: "incidencias", etiqueta: `Incidencias de actuador (${contexto.incidencias.length})` },
                ] as { id: TabRiego; etiqueta: string }[]
              ).map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setTab(t.id)}
                  className={`border-b-2 px-3.5 py-2.5 text-xs font-semibold transition-colors ${
                    tab === t.id
                      ? "border-[var(--accent-primary)] text-[var(--accent-primary)]"
                      : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                  }`}
                >
                  {t.etiqueta}
                </button>
              ))}
            </div>

            <div className="overflow-x-auto p-4">
              {tab === "programados" && (
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-[var(--border-subtle)] text-[var(--text-muted)]">
                      <th scope="col" className="py-2 pr-4">Fecha programada</th>
                      <th scope="col" className="py-2 pr-4">Litros / Apertura</th>
                      <th scope="col" className="py-2 pr-4">Estado</th>
                      <th scope="col" className="py-2">Observación</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-subtle)]">
                    {contexto.programados.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="py-4 text-center text-[var(--text-secondary)]">
                          Sin riegos programados registrados.
                        </td>
                      </tr>
                    ) : (
                      contexto.programados.map((p) => (
                        <tr key={p.id}>
                          <td className="py-2.5 pr-4 font-mono">
                            {formatearFechaHora(p.ts_programado_epoch)}
                          </td>
                          <td className="tabular-nums py-2.5 pr-4 font-mono">
                            {p.litros_propuestos} L ({p.apertura_max_pct}%)
                          </td>
                          <td className="py-2.5 pr-4">
                            <Badge tono={p.estado === "bloqueado" ? "critical" : "optimal"}>
                              {p.estado}
                            </Badge>
                          </td>
                          <td className="py-2.5 text-[var(--text-secondary)]">
                            {p.motivo_bloqueo ?? p.origen}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              )}

              {tab === "historial" && (
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-[var(--border-subtle)] text-[var(--text-muted)]">
                      <th scope="col" className="py-2 pr-4">ID</th>
                      <th scope="col" className="py-2 pr-4">Fecha</th>
                      <th scope="col" className="py-2 pr-4">Volumen</th>
                      <th scope="col" className="py-2 pr-4">Origen</th>
                      <th scope="col" className="py-2">Humedad</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-subtle)]">
                    {contexto.historial.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="py-4 text-center text-[var(--text-secondary)]">
                          No hay riegos ejecutados aún.
                        </td>
                      </tr>
                    ) : (
                      contexto.historial.map((h) => (
                        <tr key={h.id}>
                          <td className="py-2.5 pr-4 font-mono">#{h.id}</td>
                          <td className="py-2.5 pr-4 font-mono">
                            {formatearFechaHora(h.ts_epoch)}
                          </td>
                          <td className="tabular-nums py-2.5 pr-4 font-mono font-semibold text-[var(--accent-primary)]">
                            {h.agua_litros} L
                          </td>
                          <td className="py-2.5 pr-4">{h.origen}</td>
                          <td className="tabular-nums py-2.5 font-mono text-[var(--text-secondary)]">
                            {formatearNumero(h.humedad_inicial_pct, 1, "%")} →{" "}
                            {formatearNumero(h.humedad_final_pct, 1, "%")}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              )}

              {tab === "incidencias" && (
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-[var(--border-subtle)] text-[var(--text-muted)]">
                      <th scope="col" className="py-2 pr-4">Fecha</th>
                      <th scope="col" className="py-2 pr-4">Evento</th>
                      <th scope="col" className="py-2 pr-4">Efectividad</th>
                      <th scope="col" className="py-2 pr-4">ΔθA / ΔθB</th>
                      <th scope="col" className="py-2">Observaciones</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-subtle)]">
                    {contexto.incidencias.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="py-4 text-center text-[var(--text-secondary)]">
                          Sin incidencias registradas en esta parcela.
                        </td>
                      </tr>
                    ) : (
                      contexto.incidencias.map((inc) => (
                        <tr key={inc.id}>
                          <td className="py-2.5 pr-4 font-mono">
                            {formatearFechaIso(inc.evaluado_en)}
                          </td>
                          <td className="py-2.5 pr-4 font-mono font-semibold">
                            #{inc.evento_riego_id}
                          </td>
                          <td className="py-2.5 pr-4">{inc.efectividad}</td>
                          <td className="tabular-nums py-2.5 pr-4 font-mono">
                            {formatearNumero(inc.delta_a_pct, 1, "%")} /{" "}
                            {formatearNumero(inc.delta_b_pct, 1, "%")}
                          </td>
                          <td className="py-2.5 text-[var(--text-secondary)]">
                            {inc.observaciones ?? "—"}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
