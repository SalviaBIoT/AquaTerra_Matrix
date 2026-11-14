import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Cpu, Globe2, Search } from "lucide-react";
import { SeveridadBadge } from "../common/Badge";
import { formatearNumero } from "../../lib/formatters";
import type { EntradaRadarEstacion, Estacion } from "../../types/aquaterra";
import type { CanalChatId, MensajeChat } from "./types";

interface StationSidebarProps {
  estaciones: Estacion[];
  entradasRadar: EntradaRadarEstacion[];
  canalActivo: CanalChatId;
  chatsPorCanal: Record<string, MensajeChat[]>;
  onSeleccionarCanal: (destino: CanalChatId) => void;
}

export function StationSidebar({
  estaciones,
  entradasRadar,
  canalActivo,
  chatsPorCanal,
  onSeleccionarCanal,
}: StationSidebarProps) {
  const [busqueda, setBusqueda] = useState("");
  const [abiertoGlobal, setAbiertoGlobal] = useState(true);
  const [abiertoNodos, setAbiertoNodos] = useState(true);

  const termino = busqueda.trim().toLowerCase();

  const mostrarGlobal = useMemo(() => {
    if (!termino) return true;
    return (
      "ecosistema global".includes(termino) ||
      "consulta directa".includes(termino) ||
      "finca".includes(termino)
    );
  }, [termino]);

  const estacionesFiltradas = useMemo(() => {
    if (!termino) return estaciones;
    return estaciones.filter(
      (e) =>
        e.nombre.toLowerCase().includes(termino) ||
        e.codigo.toLowerCase().includes(termino)
    );
  }, [estaciones, termino]);

  return (
    <aside
      aria-label="Estaciones disponibles para conversar con Mandarino"
      className="surface-card flex flex-col gap-3 p-3.5 xl:col-span-3 xl:h-[calc(100dvh-13rem)] xl:min-h-[540px] xl:max-h-[820px]"
    >
      <div className="flex items-center justify-between px-1">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
          Canales Modulares
        </span>
        <span className="font-mono text-[11px] text-[var(--text-muted)]">
          {estaciones.length} nodos
        </span>
      </div>

      {/* Buscador de estaciones / módulos */}
      <div className="relative">
        <Search
          className="pointer-events-none absolute top-1/2 left-2.5 h-3.5 w-3.5 -translate-y-1/2 text-[var(--text-muted)]"
          aria-hidden="true"
        />
        <input
          type="text"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          placeholder="Filtrar nodo o módulo…"
          aria-label="Filtrar canales de Mandarino"
          className="h-8 w-full rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-canvas)] pr-2.5 pl-8 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[#f5b041] focus:outline-none"
        />
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto pr-0.5">
        {/* Sección Acordeón 1: Ecosistema Global */}
        {mostrarGlobal && (
          <div className="space-y-1.5">
            <button
              type="button"
              onClick={() => setAbiertoGlobal((prev) => !prev)}
              className="flex w-full items-center justify-between px-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] hover:text-[#f5b041]"
            >
              <span>🌎 Ecosistema Global</span>
              {abiertoGlobal ? (
                <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
              )}
            </button>

            {abiertoGlobal && (
              <button
                type="button"
                onClick={() => onSeleccionarCanal("general")}
                className={`w-full rounded-xl border p-3 text-left transition-all ${
                  canalActivo === "general"
                    ? "border-[#f97316] bg-[var(--mandarino-soft)] shadow-sm"
                    : "border-[var(--border-subtle)] bg-[var(--bg-elevated)] hover:border-[#f5b041]/50"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--text-primary)]">
                    <Globe2
                      className="h-3.5 w-3.5 text-[#f5b041]"
                      aria-hidden="true"
                    />
                    Asistente Global TerraBit
                  </span>
                  {(chatsPorCanal.general?.length ?? 0) > 0 && (
                    <span className="rounded-full bg-[#f97316] px-1.5 py-0.5 font-mono text-[10px] font-semibold text-white">
                      {chatsPorCanal.general?.length}
                    </span>
                  )}
                </div>
                <p className="mt-1 text-[11px] text-[var(--text-secondary)]">
                  Panorama multi-finca · hilo aislado propio
                </p>
              </button>
            )}
          </div>
        )}

        {/* Sección Acordeón 2: Nodos Físicos */}
        <div className="space-y-1.5">
          <button
            type="button"
            onClick={() => setAbiertoNodos((prev) => !prev)}
            className="flex w-full items-center justify-between px-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] hover:text-[#2ecc71]"
          >
            <span>📍 Nodos Físicos ({estacionesFiltradas.length})</span>
            {abiertoNodos ? (
              <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
            )}
          </button>

          {abiertoNodos && (
            <div className="space-y-2">
              {estacionesFiltradas.length === 0 ? (
                <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-xs text-[var(--text-muted)]">
                  Ningún nodo coincide con «{busqueda}».
                </div>
              ) : (
                estacionesFiltradas.map((est) => {
                  const radar = entradasRadar.find(
                    (e) => e.estacion.id === est.id
                  );
                  const activo = canalActivo === est.id;
                  const msgsCount = chatsPorCanal[`est-${est.id}`]?.length ?? 0;
                  const tieneAlerta =
                    Boolean(radar) &&
                    ((radar?.alertas_activas ?? 0) > 0 ||
                      radar?.severidad === "critico" ||
                      radar?.severidad === "atencion");
                  const colorPulso =
                    radar?.severidad === "critico"
                      ? "bg-[#ef4444]"
                      : tieneAlerta
                      ? "bg-[#f5b041]"
                      : radar?.severidad === "sin_datos"
                      ? "bg-[var(--text-muted)]"
                      : "bg-[#2ecc71]";

                  return (
                    <button
                      key={est.id}
                      type="button"
                      onClick={() => onSeleccionarCanal(est.id)}
                      className={`w-full rounded-xl border p-3 text-left transition-all ${
                        activo
                          ? "border-[#f97316] bg-[var(--mandarino-soft)] shadow-sm"
                          : "border-[var(--border-subtle)] bg-[var(--bg-elevated)] hover:border-[#2ecc71]/45"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span
                              className={`h-2 w-2 shrink-0 rounded-full ${colorPulso} ${
                                tieneAlerta ? "animate-pulse" : ""
                              }`}
                              aria-hidden="true"
                            />
                            <Cpu
                              className={`h-3.5 w-3.5 shrink-0 ${
                                activo
                                  ? "text-[#fb923c]"
                                  : "text-[var(--text-muted)]"
                              }`}
                              aria-hidden="true"
                            />
                            <span className="truncate text-xs font-semibold text-[var(--text-primary)]">
                              {est.nombre}
                            </span>
                          </div>
                          <span className="mt-0.5 block truncate font-mono text-[10px] text-[var(--text-muted)]">
                            {est.codigo}
                          </span>
                        </div>
                        {msgsCount > 0 && (
                          <span className="rounded-full bg-[#f97316] px-1.5 py-0.5 font-mono text-[10px] font-semibold text-white">
                            {msgsCount}
                          </span>
                        )}
                      </div>

                      {radar && (
                        <div className="mt-2 flex items-center justify-between gap-2">
                          <SeveridadBadge severidad={radar.severidad} />
                          {radar.alertas_activas > 0 ? (
                            <span className="text-[10px] font-semibold text-[#f5b041]">
                              {radar.alertas_activas} alerta(s)
                            </span>
                          ) : (
                            <span className="text-[10px] text-[#2ecc71]">
                              {formatearNumero(radar.completitud_24h_pct, 0, "%")}
                            </span>
                          )}
                        </div>
                      )}
                    </button>
                  );
                })
              )}
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
