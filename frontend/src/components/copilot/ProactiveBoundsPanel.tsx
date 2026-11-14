import { useMemo, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Download,
  FolderKanban,
  RotateCcw,
  Wrench,
} from "lucide-react";
import { toast } from "sonner";
import { SeveridadBadge } from "../common/Badge";
import { descargarArchivo } from "../../lib/api";
import {
  formatearFechaIso,
  limpiarTextoCopiloto,
  nombreLegibleVariable,
} from "../../lib/formatters";
import type {
  CotaCalibracion,
  EntradaRadarEstacion,
  InteraccionCopiloto,
  RecorteParametro,
  VersionCalibracion,
} from "../../types/aquaterra";
import type { CanalChatId, TabDerecha } from "./types";

interface ProactiveBoundsPanelProps {
  tabDerecha: TabDerecha;
  onCambiarTab: (tab: TabDerecha) => void;
  alertasEcosistema: EntradaRadarEstacion[];
  solucionesVersiones: VersionCalibracion[];
  solucionesCountFallback: number;
  historialGlobalReciente: InteraccionCopiloto[];
  nombrePorEstacion: Map<number, string>;
  cargandoEstado: boolean;
  cotas: CotaCalibracion[];
  parametrosActuales: Record<string, number>;
  ajustesSegurosInspector: Record<string, number>;
  recortesMap: Map<string, RecorteParametro>;
  esAdmin: boolean;
  revirtiendo: boolean;
  totalVersionesCanal: number;
  onResolverAlerta: (prompt: string, estacionId: number) => void;
  onAbrirHistorialItem: (item: InteraccionCopiloto) => void;
  onRollback: () => void;
}

interface SeccionHistorial {
  clave: string;
  titulo: string;
  canal: CanalChatId;
  items: InteraccionCopiloto[];
}

export function ProactiveBoundsPanel({
  tabDerecha,
  onCambiarTab,
  alertasEcosistema,
  solucionesVersiones,
  solucionesCountFallback,
  historialGlobalReciente,
  nombrePorEstacion,
  cargandoEstado,
  cotas,
  parametrosActuales,
  ajustesSegurosInspector,
  recortesMap,
  esAdmin,
  revirtiendo,
  totalVersionesCanal,
  onResolverAlerta,
  onAbrirHistorialItem,
  onRollback,
}: ProactiveBoundsPanelProps) {
  const [seccionesColapsadas, setSeccionesColapsadas] = useState<
    Record<string, boolean>
  >({});

  const ajustesSegurosCount = Object.keys(ajustesSegurosInspector).length;

  // Agrupación modular de chats recientes por nodo/sección (cero mezcla desordenada)
  const seccionesHistorial = useMemo<SeccionHistorial[]>(() => {
    const mapa = new Map<string, SeccionHistorial>();
    for (const item of historialGlobalReciente) {
      const esGlobal = item.estacion_id === null;
      const clave = esGlobal ? "global" : `est-${item.estacion_id}`;
      const titulo = esGlobal
        ? "Asistente Global TerraBit"
        : nombrePorEstacion.get(item.estacion_id!) ??
          `Estación #${item.estacion_id}`;
      const canal: CanalChatId = esGlobal ? "general" : item.estacion_id!;

      let seccion = mapa.get(clave);
      if (!seccion) {
        seccion = { clave, titulo, canal, items: [] };
        mapa.set(clave, seccion);
      }
      seccion.items.push(item);
    }
    return Array.from(mapa.values());
  }, [historialGlobalReciente, nombrePorEstacion]);

  const alternarSeccion = (clave: string) => {
    setSeccionesColapsadas((prev) => ({
      ...prev,
      [clave]: !prev[clave],
    }));
  };

  return (
    <aside
      aria-label="Panel proactivo de mejoras, soluciones e historial por estación"
      className="surface-card flex flex-col overflow-hidden xl:col-span-3 xl:h-[calc(100dvh-13rem)] xl:min-h-[540px] xl:max-h-[820px]"
    >
      <div className="flex shrink-0 items-center justify-between gap-1 border-b border-[var(--border-subtle)] p-2">
        <div
          role="tablist"
          className="grid w-full grid-cols-2 gap-1 rounded-xl bg-[var(--bg-canvas)] p-1"
        >
          <button
            type="button"
            role="tab"
            aria-selected={tabDerecha === "proactivo"}
            onClick={() => onCambiarTab("proactivo")}
            className={`rounded-lg px-2.5 py-1.5 text-xs font-semibold transition-colors ${
              tabDerecha === "proactivo"
                ? "bg-[#f97316] text-white"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            Proactivo e Historial
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tabDerecha === "cotas"}
            onClick={() => onCambiarTab("cotas")}
            className={`inline-flex items-center justify-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-semibold transition-colors ${
              tabDerecha === "cotas"
                ? "bg-[#f97316] text-white"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            Cotas &amp; SFT
            {ajustesSegurosCount > 0 && (
              <span className="rounded-full bg-white/25 px-1.5 text-[10px]">
                {ajustesSegurosCount}
              </span>
            )}
          </button>
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto p-3.5">
        {tabDerecha === "proactivo" ? (
          <div className="space-y-5">
            {/* 1. Sugerencias Proactivas */}
            <div>
              <div className="mb-2 flex items-center justify-between">
                <h2 className="text-[11px] font-semibold uppercase tracking-wider text-[#f5b041]">
                  Sugerencias Proactivas
                </h2>
                <span className="font-mono text-[10px] text-[var(--text-muted)]">
                  {alertasEcosistema.length} alertas
                </span>
              </div>

              {alertasEcosistema.length === 0 ? (
                <div className="rounded-xl border border-[#2ecc71]/30 bg-[#2ecc71]/10 p-3 text-xs text-[var(--text-secondary)]">
                  Sin alertas críticas activas. Todos los nodos operan en rango seguro.
                </div>
              ) : (
                <div className="space-y-2">
                  {alertasEcosistema.map((entry) => (
                    <button
                      key={`sug-${entry.estacion.id}`}
                      type="button"
                      onClick={() =>
                        onResolverAlerta(
                          `Analiza y propón solución para la novedad en ${entry.estacion.nombre}: ${limpiarTextoCopiloto(
                            entry.diagnostico_resumen
                          )}`,
                          entry.estacion.id
                        )
                      }
                      className="w-full rounded-xl border border-[#f5b041]/40 bg-[#f5b041]/10 p-2.5 text-left transition-colors hover:border-[#f97316]"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-xs font-semibold text-[var(--text-primary)]">
                          {entry.estacion.nombre}
                        </span>
                        <SeveridadBadge severidad={entry.severidad} />
                      </div>
                      <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-[var(--text-secondary)]">
                        {limpiarTextoCopiloto(entry.diagnostico_resumen)}
                      </p>
                      <span className="mt-1.5 inline-block text-[10px] font-semibold text-[#fb923c]">
                        Resolver con Mandarino →
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* 2. Soluciones y Calibraciones */}
            <div>
              <h2 className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                <Wrench className="h-3.5 w-3.5 text-[#2ecc71]" aria-hidden="true" />
                Soluciones y Calibraciones
              </h2>

              {solucionesVersiones.length === 0 &&
              solucionesCountFallback === 0 ? (
                <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-xs text-[var(--text-secondary)]">
                  Aún no se han aplicado recalibraciones en este entorno.
                </div>
              ) : (
                <ul className="space-y-2">
                  {solucionesVersiones.slice(0, 5).map((v) => {
                    const nomEst =
                      v.estacion_id !== null
                        ? nombrePorEstacion.get(v.estacion_id) ??
                          `Estación #${v.estacion_id}`
                        : "Global";
                    return (
                      <li
                        key={`sol-${v.id}`}
                        className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-2.5 text-xs"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-mono font-semibold text-[#2ecc71]">
                            v{v.version} · {nomEst}
                          </span>
                          <span className="text-[10px] text-[var(--text-muted)]">
                            {formatearFechaIso(v.creado_en)}
                          </span>
                        </div>
                        <p className="mt-1 line-clamp-2 text-[11px] text-[var(--text-secondary)]">
                          {v.motivo}
                        </p>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            {/* 3. Historial Reciente Agrupado por Secciones / Estación */}
            <div>
              <h2 className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                <FolderKanban className="h-3.5 w-3.5 text-[#f5b041]" aria-hidden="true" />
                Historial Reciente por Sección
              </h2>

              {cargandoEstado && historialGlobalReciente.length === 0 ? (
                <div className="space-y-2">
                  <div className="skeleton h-12 w-full" />
                  <div className="skeleton h-12 w-full" />
                </div>
              ) : seccionesHistorial.length === 0 ? (
                <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-xs text-[var(--text-secondary)]">
                  Sin consultas guardadas aún.
                </div>
              ) : (
                <div className="space-y-2.5">
                  {seccionesHistorial.map((sec) => {
                    const colapsada = Boolean(seccionesColapsadas[sec.clave]);
                    return (
                      <div
                        key={sec.clave}
                        className="overflow-hidden rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)]"
                      >
                        <button
                          type="button"
                          onClick={() => alternarSeccion(sec.clave)}
                          className="flex w-full items-center justify-between gap-2 bg-[var(--bg-surface)] px-2.5 py-2 text-left text-[11px] font-semibold text-[var(--text-primary)] hover:text-[#fb923c]"
                        >
                          <span className="flex items-center gap-1.5 truncate">
                            {colapsada ? (
                              <ChevronRight className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                            ) : (
                              <ChevronDown className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                            )}
                            <span className="truncate">{sec.titulo}</span>
                          </span>
                          <span className="rounded-full bg-[var(--mandarino-soft)] px-1.5 py-0.5 font-mono text-[10px] text-[#fb923c]">
                            {sec.items.length}
                          </span>
                        </button>

                        {!colapsada && (
                          <div className="divide-y divide-[var(--border-subtle)]/70">
                            {sec.items.slice(0, 4).map((item) => (
                              <button
                                key={`hist-sec-${item.id}`}
                                type="button"
                                onClick={() => onAbrirHistorialItem(item)}
                                className="w-full px-2.5 py-2 text-left transition-colors hover:bg-[var(--bg-subtle)]"
                              >
                                <p className="line-clamp-1 text-xs font-medium text-[var(--text-primary)]">
                                  {item.mensaje_usuario}
                                </p>
                                <span className="mt-0.5 block text-[10px] text-[var(--text-muted)]">
                                  {formatearFechaIso(item.ts_iso)}
                                </span>
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        ) : (
          /* Tab Cotas & SFT: Tabla Comparativa Estilizada con Barras de Zona Segura/Peligro */
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <button
                type="button"
                disabled={!esAdmin || revirtiendo || totalVersionesCanal < 2}
                onClick={onRollback}
                className="inline-flex items-center gap-1 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-2.5 py-1.5 text-[11px] font-semibold text-[var(--text-primary)] hover:bg-[var(--bg-subtle)] disabled:opacity-45"
              >
                <RotateCcw className="h-3 w-3" aria-hidden="true" />
                {revirtiendo ? "Revirtiendo…" : "Rollback"}
              </button>

              <button
                type="button"
                onClick={() =>
                  void descargarArchivo(
                    "/api/copiloto/dataset.jsonl",
                    "aquaterra_mandarino_sft.jsonl"
                  ).then(() => toast.success("Dataset SFT .jsonl exportado."))
                }
                className="inline-flex items-center gap-1 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-2.5 py-1.5 text-[11px] font-semibold text-[var(--text-primary)] hover:border-[#f5b041]/60"
              >
                <Download className="h-3 w-3 text-[#f5b041]" aria-hidden="true" />
                Dataset .jsonl
              </button>
            </div>

            <div className="overflow-hidden rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)]">
              <table className="w-full border-collapse text-left text-[11px]">
                <thead className="bg-[var(--bg-canvas)] text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                  <tr>
                    <th className="px-2.5 py-2">Parámetro</th>
                    <th className="px-2 py-2 text-right">Actual</th>
                    <th className="px-2.5 py-2 text-right">Recomendado</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-subtle)]/70">
                  {cotas.map((cota) => {
                    const actual =
                      parametrosActuales[cota.clave] ?? cota.valor_por_defecto;
                    const valorPropuesto = ajustesSegurosInspector[cota.clave];
                    const objetivo = valorPropuesto ?? cota.valor_por_defecto;
                    const recorteInfo = recortesMap.get(cota.clave);
                    const span = Math.max(1e-6, cota.maximo - cota.minimo);
                    const pctActual = Math.max(
                      0,
                      Math.min(100, ((actual - cota.minimo) / span) * 100)
                    );
                    const pctProp =
                      valorPropuesto !== undefined
                        ? Math.max(
                            0,
                            Math.min(
                              100,
                              ((valorPropuesto - cota.minimo) / span) * 100
                            )
                          )
                        : null;
                    const cercaDelBorde = pctActual >= 85 || pctActual <= 15;

                    return (
                      <tr key={cota.clave} className="align-top">
                        <td colSpan={3} className="p-2.5">
                          <div className="grid grid-cols-[1fr_auto_auto] items-center gap-2">
                            <span className="truncate font-semibold text-[var(--text-primary)]">
                              {nombreLegibleVariable(cota.clave)}
                            </span>
                            <span className="tabular-nums font-mono text-[var(--text-secondary)]">
                              {actual} {cota.unidad}
                            </span>
                            <span
                              className={`tabular-nums rounded px-1.5 py-0.5 font-mono font-semibold ${
                                valorPropuesto !== undefined
                                  ? "bg-[#f5b041]/20 text-[#f5b041]"
                                  : "bg-[var(--bg-surface)] text-[#2ecc71]"
                              }`}
                              title={recorteInfo ? recorteInfo.motivo : "Valor objetivo"}
                            >
                              {objetivo}
                            </span>
                          </div>

                          {/* Barra de proximidad a límite físico */}
                          <div className="relative mt-1.5 h-1.5 w-full rounded-full bg-[var(--bg-subtle)]">
                            <div
                              className={`h-full rounded-full transition-all ${
                                cercaDelBorde ? "bg-[#f5b041]" : "bg-[#2ecc71]"
                              }`}
                              style={{ width: `${pctActual}%` }}
                            />
                            {pctProp !== null && (
                              <div
                                className="absolute top-1/2 h-3 w-1.5 -translate-y-1/2 rounded-full bg-[#f97316] shadow"
                                style={{ left: `calc(${pctProp}% - 3px)` }}
                              />
                            )}
                          </div>

                          <div className="tabular-nums mt-1 flex justify-between font-mono text-[10px] text-[var(--text-muted)]">
                            <span>Mín {cota.minimo}</span>
                            <span>Máx {cota.maximo} {cota.unidad}</span>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
