import { useEffect, useRef, useState } from "react";
import {
  Activity,
  Bot,
  Cpu,
  Droplets,
  MapPin,
  Radar,
  Search,
  Settings,
  Sparkles,
  X,
} from "lucide-react";
import { useApp } from "../../context/AppContext";
import { api } from "../../lib/api";
import type {
  ItemBusquedaGlobal,
  ResultadoBusquedaGlobal,
  VistaId,
} from "../../types/aquaterra";

const VISTAS_RAPIDAS: { id: VistaId; titulo: string; subtitulo: string }[] = [
  { id: "radar", titulo: "Radar General", subtitulo: "Pulso de estaciones, alertas y clima 48h" },
  { id: "telemetria", titulo: "Telemetría y Analítica", subtitulo: "Series multipanel ECharts, correlación OLS y comparativas" },
  { id: "parcelas", titulo: "Parcelas y Cultivos", subtitulo: "Inventario agrícola, humedad y vinculación IoT" },
  { id: "riego", titulo: "Control de Riego", subtitulo: "5 Candados hidráulicos, recomendación proactiva y salud de bomba" },
  { id: "copiloto", titulo: "Copiloto IA", subtitulo: "Auditoría de calibración físico-agronómica y dataset SFT" },
  { id: "hardware", titulo: "Hardware de Campo", subtitulo: "Serial USB nRF24L01+/LoRa, MicroSD y reparación RTC" },
  { id: "config", titulo: "Configuración del Sistema", subtitulo: "Conectores, IA híbrida Ollama/Gemini, GPS y usuarios RBAC" },
];

const MAPA_VISTAS: Record<string, VistaId> = {
  radar: "radar",
  dashboard: "radar",
  telemetria: "telemetria",
  monitor: "telemetria",
  parcelas: "parcelas",
  riego: "riego",
  riegos: "riego",
  copiloto: "copiloto",
  hardware: "hardware",
  config: "config",
  configuracion: "config",
};

function iconoParaVista(vista: VistaId) {
  switch (vista) {
    case "radar":
      return <Radar className="h-4 w-4" aria-hidden="true" />;
    case "telemetria":
      return <Activity className="h-4 w-4" aria-hidden="true" />;
    case "parcelas":
      return <MapPin className="h-4 w-4" aria-hidden="true" />;
    case "riego":
      return <Droplets className="h-4 w-4" aria-hidden="true" />;
    case "copiloto":
      return <Bot className="h-4 w-4" aria-hidden="true" />;
    case "hardware":
      return <Cpu className="h-4 w-4" aria-hidden="true" />;
    case "config":
      return <Settings className="h-4 w-4" aria-hidden="true" />;
  }
}

export function CommandPalette({
  abierto,
  onCerrar,
}: {
  abierto: boolean;
  onCerrar: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const { setVistaActiva, setEstacionActivaId, estaciones } = useApp();

  const [consulta, setConsulta] = useState("");
  const [buscando, setBuscando] = useState(false);
  const [resultados, setResultados] = useState<ItemBusquedaGlobal[]>([]);

  // Control nativo showModal() / close()
  useEffect(() => {
    const dlg = dialogRef.current;
    if (!dlg) return;
    if (abierto && !dlg.open) {
      dlg.showModal();
      window.setTimeout(() => inputRef.current?.focus(), 20);
    } else if (!abierto && dlg.open) {
      dlg.close();
    }
  }, [abierto]);

  // Fallback ligero de clic fuera solo si el navegador no soporta closedby="any"
  useEffect(() => {
    const dlg = dialogRef.current;
    if (!dlg || "closedBy" in HTMLDialogElement.prototype) return;
    let pressedOutside = false;
    const outside = (e: PointerEvent) => {
      const r = dlg.getBoundingClientRect();
      return (
        e.clientX < r.left ||
        e.clientX > r.right ||
        e.clientY < r.top ||
        e.clientY > r.bottom
      );
    };
    const onDown = (e: PointerEvent) => {
      pressedOutside = outside(e);
    };
    const onUp = (e: PointerEvent) => {
      if (pressedOutside && outside(e)) dlg.close();
    };
    dlg.addEventListener("pointerdown", onDown);
    dlg.addEventListener("pointerup", onUp);
    return () => {
      dlg.removeEventListener("pointerdown", onDown);
      dlg.removeEventListener("pointerup", onUp);
    };
  }, []);

  // Búsqueda debounced en /api/sistema/buscar
  useEffect(() => {
    if (!abierto) return;
    const q = consulta.trim();
    if (q.length < 2) {
      setResultados([]);
      setBuscando(false);
      return;
    }
    let cancelado = false;
    setBuscando(true);
    const timer = window.setTimeout(async () => {
      try {
        const resp = await api.get<{ resultado: ResultadoBusquedaGlobal }>(
          `/api/sistema/buscar?q=${encodeURIComponent(q)}&limite=15`
        );
        if (!cancelado) {
          setResultados(resp.resultado?.items ?? []);
        }
      } catch {
        if (!cancelado) setResultados([]);
      } finally {
        if (!cancelado) setBuscando(false);
      }
    }, 180);
    return () => {
      cancelado = true;
      window.clearTimeout(timer);
    };
  }, [consulta, abierto]);

  const navegarVista = (vista: VistaId, estacionId?: number | null) => {
    if (estacionId) {
      setEstacionActivaId(estacionId);
    }
    setVistaActiva(vista);
    setConsulta("");
    onCerrar();
  };

  const abrirItemBackend = (item: ItemBusquedaGlobal) => {
    const cat = (item.categoria ?? "").toLowerCase();
    const destino =
      MAPA_VISTAS[cat] ??
      (cat === "estacion"
        ? "telemetria"
        : cat === "parcela"
          ? "parcelas"
          : cat === "evento"
            ? "hardware"
            : "radar");
    navegarVista(
      destino,
      cat === "estacion" ? (item.referencia_id ?? undefined) : undefined
    );
  };

  const qLower = consulta.trim().toLowerCase();
  const vistasFiltradas = VISTAS_RAPIDAS.filter(
    (v) =>
      !qLower ||
      v.titulo.toLowerCase().includes(qLower) ||
      v.subtitulo.toLowerCase().includes(qLower)
  );
  const estacionesFiltradas = estaciones.filter(
    (e) =>
      !qLower ||
      e.codigo.toLowerCase().includes(qLower) ||
      e.nombre.toLowerCase().includes(qLower) ||
      e.tipo.toLowerCase().includes(qLower)
  );

  return (
    <dialog
      ref={dialogRef}
      closedby="any"
      aria-labelledby="cmd-palette-title"
      onClose={() => {
        if (dialogRef.current) dialogRef.current.returnValue = "";
        onCerrar();
      }}
      className="m-auto w-[min(94vw,640px)] overflow-hidden rounded-2xl p-0"
    >
      <div className="flex flex-col">
        <h2 id="cmd-palette-title" className="visually-hidden">
          Paleta de comandos y búsqueda global
        </h2>

        <div className="flex items-center gap-3 border-b border-[var(--border-subtle)] px-4 py-3.5">
          <Search
            className="h-4 w-4 shrink-0 text-[var(--accent-primary)]"
            aria-hidden="true"
          />
          <label htmlFor="cmd-search-input" className="visually-hidden">
            Buscar vistas, estaciones, parcelas o bitácora
          </label>
          <input
            ref={inputRef}
            id="cmd-search-input"
            type="search"
            value={consulta}
            onChange={(e) => setConsulta(e.target.value)}
            placeholder="Ir a vista, estación IoT, parcela o buscar en bitácora..."
            autoCorrect="off"
            autoCapitalize="none"
            spellCheck={false}
            className="w-full bg-transparent text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none"
          />
          <button
            type="button"
            onClick={onCerrar}
            aria-label="Cerrar paleta de comandos"
            className="inline-flex h-7 w-7 items-center justify-center rounded-md text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <div className="max-h-[min(65vh,460px)] overflow-y-auto p-3 space-y-4">
          {consulta.trim().length >= 2 && (
            <section aria-label="Hallazgos en bitácora y sistema">
              <div className="mb-1.5 flex items-center justify-between px-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                <span>Resultados en AquaTerra</span>
                {buscando && <span>Buscando…</span>}
              </div>
              {!buscando && resultados.length === 0 ? (
                <p className="rounded-xl bg-[var(--bg-elevated)] px-3 py-2.5 text-xs text-[var(--text-secondary)]">
                  No se encontraron registros en bitácora para &ldquo;{consulta}&rdquo;.
                </p>
              ) : (
                <ul className="space-y-1">
                  {resultados.map((item, idx) => (
                    <li key={`${item.categoria}-${idx}`}>
                      <button
                        type="button"
                        onClick={() => abrirItemBackend(item)}
                        className="flex w-full items-start justify-between gap-3 rounded-xl px-3 py-2 text-left transition-colors hover:bg-[var(--bg-elevated)]"
                      >
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium text-[var(--text-primary)]">
                            {item.titulo}
                          </div>
                          <div className="truncate text-xs text-[var(--text-secondary)]">
                            {item.detalle ?? item.subtitulo ?? ""}
                          </div>
                        </div>
                        <span className="shrink-0 rounded-full bg-[var(--bg-subtle)] px-2 py-0.5 text-[11px] font-medium text-[var(--text-secondary)]">
                          {item.categoria}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {estacionesFiltradas.length > 0 && (
            <section aria-label="Estaciones IoT disponibles">
              <div className="mb-1.5 px-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                Estaciones IoT (enfocar telemetría)
              </div>
              <ul className="space-y-1">
                {estacionesFiltradas.slice(0, 6).map((est) => (
                  <li key={est.id}>
                    <button
                      type="button"
                      onClick={() => navegarVista("telemetria", est.id)}
                      className="flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2 text-left transition-colors hover:bg-[var(--bg-elevated)]"
                    >
                      <div className="flex min-w-0 items-center gap-2.5">
                        <Sparkles
                          className="h-4 w-4 shrink-0 text-[var(--accent-primary)]"
                          aria-hidden="true"
                        />
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium text-[var(--text-primary)]">
                            {est.nombre}
                          </div>
                          <div className="font-mono text-xs text-[var(--text-muted)]">
                            {est.codigo} · {est.tipo}
                          </div>
                        </div>
                      </div>
                      <span className="text-xs text-[var(--accent-primary)]">
                        Abrir
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {vistasFiltradas.length > 0 && (
            <section aria-label="Navegación rápida de vistas">
              <div className="mb-1.5 px-2 text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                Navegación rápida
              </div>
              <ul className="space-y-1">
                {vistasFiltradas.map((v) => (
                  <li key={v.id}>
                    <button
                      type="button"
                      onClick={() => navegarVista(v.id)}
                      className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left transition-colors hover:bg-[var(--bg-elevated)]"
                    >
                      <span className="text-[var(--text-secondary)]">
                        {iconoParaVista(v.id)}
                      </span>
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-[var(--text-primary)]">
                          {v.titulo}
                        </div>
                        <div className="truncate text-xs text-[var(--text-secondary)]">
                          {v.subtitulo}
                        </div>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>

        <div className="flex items-center justify-between border-t border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-4 py-2 text-[11px] text-[var(--text-muted)]">
          <span>Usa Ctrl+K en cualquier vista para abrir este buscador</span>
          <kbd className="rounded border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-1.5 py-0.5 font-mono text-[10px]">
            Esc
          </kbd>
        </div>
      </div>
    </dialog>
  );
}
