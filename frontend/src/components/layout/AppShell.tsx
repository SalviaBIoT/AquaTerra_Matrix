import { useEffect, useState, type ReactNode } from "react";
import {
  Activity,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Cpu,
  Droplets,
  LogOut,
  MapPin,
  Menu,
  Moon,
  Radar,
  RefreshCw,
  Search,
  Settings,
  Sprout,
  Sun,
  Wifi,
  X,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { useApp } from "../../context/AppContext";
import type { VistaId } from "../../types/aquaterra";
import { CommandPalette } from "../common/CommandPalette";
import mandarinoIcon from "../../assets/mandarino-avatar.png";

interface NavItem {
  id: VistaId;
  etiqueta: string;
  grupo: "MONITOREO" | "OPERACIÓN" | "INFRAESTRUCTURA";
  icono: ReactNode;
}

const NAV_ITEMS: NavItem[] = [
  {
    id: "radar",
    etiqueta: "Radar General",
    grupo: "MONITOREO",
    icono: <Radar className="h-4 w-4 shrink-0" aria-hidden="true" />,
  },
  {
    id: "telemetria",
    etiqueta: "Telemetría",
    grupo: "MONITOREO",
    icono: <Activity className="h-4 w-4 shrink-0" aria-hidden="true" />,
  },
  {
    id: "parcelas",
    etiqueta: "Parcelas",
    grupo: "OPERACIÓN",
    icono: <MapPin className="h-4 w-4 shrink-0" aria-hidden="true" />,
  },
  {
    id: "riego",
    etiqueta: "Control de Riego",
    grupo: "OPERACIÓN",
    icono: <Droplets className="h-4 w-4 shrink-0" aria-hidden="true" />,
  },
  {
    id: "copiloto",
    etiqueta: "Mandarino IA",
    grupo: "OPERACIÓN",
    icono: (
      <img
        src={mandarinoIcon}
        alt=""
        className="h-4 w-4 shrink-0 object-contain"
        aria-hidden="true"
      />
    ),
  },
  {
    id: "hardware",
    etiqueta: "Hardware IoT",
    grupo: "INFRAESTRUCTURA",
    icono: <Cpu className="h-4 w-4 shrink-0" aria-hidden="true" />,
  },
  {
    id: "config",
    etiqueta: "Configuración",
    grupo: "INFRAESTRUCTURA",
    icono: <Settings className="h-4 w-4 shrink-0" aria-hidden="true" />,
  },
];

const GRUPOS: NavItem["grupo"][] = [
  "MONITOREO",
  "OPERACIÓN",
  "INFRAESTRUCTURA",
];

function StatusDotRow({
  etiqueta,
  activo,
  detalle,
}: {
  etiqueta: string;
  activo: boolean;
  detalle?: string;
}) {
  return (
    <li className="flex items-center justify-between gap-3 py-1.5 text-xs">
      <div className="flex items-center gap-2 text-[var(--text-primary)]">
        {activo ? (
          <CheckCircle2
            className="h-3.5 w-3.5 shrink-0 text-[var(--status-optimal)]"
            aria-hidden="true"
          />
        ) : (
          <XCircle
            className="h-3.5 w-3.5 shrink-0 text-[var(--text-muted)]"
            aria-hidden="true"
          />
        )}
        <span>{etiqueta}</span>
      </div>
      <span className="font-mono text-[11px] text-[var(--text-secondary)]">
        {detalle ?? (activo ? "Activo" : "Inactivo")}
      </span>
    </li>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const {
    usuario,
    logout,
    vistaActiva,
    setVistaActiva,
    temaEfectivo,
    alternarTemaRapido,
    estaciones,
    estacionActivaId,
    setEstacionActivaId,
    estadoSistema,
    resumenRadar,
    sincronizarAhora,
    sincronizando,
  } = useApp();

  const [colapsado, setColapsado] = useState(false);
  const [menuMovil, setMenuMovil] = useState(false);
  const [cmdAbierto, setCmdAbierto] = useState(false);
  const [conectividadAbierta, setConectividadAbierta] = useState(false);

  // Atajo global Ctrl+K / Cmd+K
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCmdAbierto((prev) => !prev);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const itemActual = NAV_ITEMS.find((i) => i.id === vistaActiva) ?? NAV_ITEMS[0];

  const handleSync = async () => {
    try {
      const msg = await sincronizarAhora();
      toast.success(msg);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Error al sincronizar el sistema."
      );
    }
  };

  const renderSidebarContenido = (modoMovil: boolean) => (
    <div className="flex h-full flex-col justify-between">
      <div>
        {/* Cabecera Marca */}
        <div
          className={`flex h-14 items-center border-b border-[var(--border-subtle)] px-3.5 ${
            !modoMovil && colapsado ? "justify-center" : "justify-between"
          }`}
        >
          <button
            type="button"
            onClick={() => {
              setVistaActiva("radar");
              setMenuMovil(false);
            }}
            className="flex items-center gap-2.5 text-left"
          >
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-[var(--accent-primary-soft)] text-[var(--accent-primary)]">
              <Sprout className="h-4 w-4" aria-hidden="true" />
            </span>
            {(modoMovil || !colapsado) && (
              <div className="min-w-0">
                <div className="truncate text-sm font-extrabold tracking-tight text-[var(--text-primary)]">
                  Salvia<span className="text-[var(--accent-primary)]">BIoT</span>
                </div>
                <div className="font-mono text-[10px] text-[var(--text-muted)]">
                  Bio-IoT v{estadoSistema?.version_app ?? "6.0.0"}
                </div>
              </div>
            )}
          </button>

          {modoMovil ? (
            <button
              type="button"
              onClick={() => setMenuMovil(false)}
              aria-label="Cerrar menú lateral"
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          ) : (
            <button
              type="button"
              onClick={() => setColapsado((c) => !c)}
              aria-label={
                colapsado ? "Expandir barra lateral" : "Contraer barra lateral"
              }
              className="hidden h-7 w-7 items-center justify-center rounded-lg text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] lg:inline-flex"
            >
              {colapsado ? (
                <ChevronRight className="h-4 w-4" aria-hidden="true" />
              ) : (
                <ChevronLeft className="h-4 w-4" aria-hidden="true" />
              )}
            </button>
          )}
        </div>

        {/* Navegación por secciones */}
        <nav aria-label="Navegación principal" className="space-y-5 px-2.5 py-4">
          {GRUPOS.map((grupo) => {
            const items = NAV_ITEMS.filter((i) => i.grupo === grupo);
            return (
              <div key={grupo}>
                {(modoMovil || !colapsado) && (
                  <div className="mb-1.5 px-2.5 text-[10px] font-semibold uppercase tracking-[0.09em] text-[var(--text-muted)]">
                    {grupo}
                  </div>
                )}
                <ul className="space-y-1">
                  {items.map((item) => {
                    const activo = vistaActiva === item.id;
                    return (
                      <li key={item.id}>
                        <button
                          type="button"
                          onClick={() => {
                            setVistaActiva(item.id);
                            setMenuMovil(false);
                          }}
                          aria-current={activo ? "page" : undefined}
                          title={!modoMovil && colapsado ? item.etiqueta : undefined}
                          className={`flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-sm font-medium transition-colors ${
                            !modoMovil && colapsado ? "justify-center" : ""
                          } ${
                            activo
                              ? "bg-[var(--accent-primary-soft)] text-[var(--accent-primary)]"
                              : "text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
                          }`}
                        >
                          {item.icono}
                          {(modoMovil || !colapsado) && (
                            <span className="truncate">{item.etiqueta}</span>
                          )}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            );
          })}
        </nav>
      </div>

      {/* Footer de usuario */}
      <div className="border-t border-[var(--border-subtle)] p-2.5">
        <div
          className={`flex items-center gap-2.5 rounded-xl bg-[var(--bg-elevated)] p-2 ${
            !modoMovil && colapsado ? "justify-center" : "justify-between"
          }`}
        >
          {(modoMovil || !colapsado) && (
            <div className="min-w-0 pl-1">
              <div className="truncate text-xs font-semibold text-[var(--text-primary)]">
                {usuario?.nombre ?? usuario?.usuario}
              </div>
              <div className="font-mono text-[10px] uppercase tracking-wider text-[var(--accent-primary)]">
                {usuario?.rol}
              </div>
            </div>
          )}
          <button
            type="button"
            onClick={() => void logout()}
            title="Cerrar sesión"
            aria-label="Cerrar sesión"
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[var(--text-secondary)] hover:bg-[var(--status-critical-soft)] hover:text-[var(--status-critical)]"
          >
            <LogOut className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex h-dvh w-full overflow-hidden bg-[var(--bg-canvas)] text-[var(--text-primary)]">
      <a href="#main-content" className="visually-hidden skip-link">
        Saltar al contenido principal
      </a>

      {/* Sidebar Escritorio */}
      <aside
        className={`hidden shrink-0 border-r border-[var(--border-subtle)] bg-[var(--bg-surface)] transition-[width] duration-200 lg:block ${
          colapsado ? "w-[68px]" : "w-[232px]"
        }`}
      >
        {renderSidebarContenido(false)}
      </aside>

      {/* Drawer Móvil */}
      {menuMovil && (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          <div
            className="fixed inset-0 bg-black/50 backdrop-blur-xs"
            onClick={() => setMenuMovil(false)}
            aria-hidden="true"
          />
          <aside className="relative z-10 h-full w-[256px] border-r border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-2xl">
            {renderSidebarContenido(true)}
          </aside>
        </div>
      )}

      {/* Columna Principal */}
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {/* Topbar 56px */}
        <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-[var(--border-subtle)] bg-[var(--bg-surface)] px-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              onClick={() => setMenuMovil(true)}
              aria-label="Abrir menú de navegación"
              className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] lg:hidden"
            >
              <Menu className="h-4 w-4" aria-hidden="true" />
            </button>

            <div className="min-w-0">
              <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
                <span className="hidden sm:inline">{itemActual.grupo}</span>
                <span className="hidden sm:inline">/</span>
                <span className="truncate font-semibold text-[var(--text-primary)]">
                  {itemActual.etiqueta}
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Selector global de estación activa */}
            <div className="hidden items-center gap-2 md:flex">
              <label
                htmlFor="topbar-station-select"
                className="text-xs text-[var(--text-muted)]"
              >
                Estación:
              </label>
              <select
                id="topbar-station-select"
                value={estacionActivaId ?? ""}
                onChange={(e) =>
                  setEstacionActivaId(
                    e.target.value ? Number(e.target.value) : null
                  )
                }
                className="h-8 max-w-[220px] rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-2.5 text-xs font-medium text-[var(--text-primary)]"
              >
                {estaciones.length === 0 ? (
                  <option value="">Sin estaciones</option>
                ) : (
                  estaciones.map((est) => (
                    <option key={est.id} value={est.id}>
                      {est.codigo} · {est.nombre}
                    </option>
                  ))
                )}
              </select>
            </div>

            {/* Buscador Ctrl+K */}
            <button
              type="button"
              onClick={() => setCmdAbierto(true)}
              aria-label="Abrir buscador global Ctrl+K"
              className="inline-flex h-8 items-center gap-2 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-2.5 text-xs text-[var(--text-secondary)] transition-colors hover:border-[var(--border-strong)] hover:text-[var(--text-primary)]"
            >
              <Search className="h-3.5 w-3.5" aria-hidden="true" />
              <span className="hidden sm:inline">Buscar…</span>
              <kbd className="hidden rounded border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--text-muted)] sm:inline">
                Ctrl+K
              </kbd>
            </button>

            {/* Botón Sincronizar */}
            <button
              type="button"
              onClick={() => void handleSync()}
              disabled={sincronizando}
              aria-label="Sincronizar Open-Meteo y Ubidots"
              className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-2.5 text-xs font-medium text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-elevated)] disabled:opacity-50"
            >
              <RefreshCw
                className={`h-3.5 w-3.5 text-[var(--accent-primary)] ${
                  sincronizando ? "animate-spin" : ""
                }`}
                aria-hidden="true"
              />
              <span className="hidden xl:inline">
                {sincronizando ? "Sincronizando…" : "Sincronizar"}
              </span>
            </button>

            {/* Popover Conectividad */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setConectividadAbierta((v) => !v)}
                aria-expanded={conectividadAbierta}
                aria-controls="conectividad-panel"
                className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-2.5 text-xs font-medium text-[var(--text-primary)] hover:bg-[var(--bg-elevated)]"
              >
                <span
                  className={`h-2 w-2 rounded-full ${
                    (resumenRadar?.criticas ?? 0) > 0
                      ? "bg-[var(--status-critical)]"
                      : "bg-[var(--status-optimal)]"
                  }`}
                  aria-hidden="true"
                />
                <Wifi className="h-3.5 w-3.5 text-[var(--text-secondary)]" aria-hidden="true" />
                <span className="hidden sm:inline">Estado</span>
              </button>

              {conectividadAbierta && (
                <>
                  <div
                    className="fixed inset-0 z-30"
                    onClick={() => setConectividadAbierta(false)}
                    aria-hidden="true"
                  />
                  <div
                    id="conectividad-panel"
                    className="surface-card absolute right-0 top-10 z-40 w-72 p-4 shadow-xl"
                  >
                    <div className="mb-2 flex items-center justify-between">
                      <span className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                        Salud del Ecosistema
                      </span>
                      <span className="font-mono text-[11px] text-[var(--accent-primary)]">
                        {resumenRadar?.total_estaciones ?? 0} nodos
                      </span>
                    </div>
                    <ul className="divide-y divide-[var(--border-subtle)]">
                      <StatusDotRow
                        etiqueta="Base SQLite WAL"
                        activo={Boolean(estadoSistema?.sqlite_wal)}
                        detalle={estadoSistema?.sqlite_wal ? "Concurrente" : "Normal"}
                      />
                      <StatusDotRow
                        etiqueta="Cloud Ubidots"
                        activo={Boolean(estadoSistema?.ubidots_configurado)}
                        detalle={
                          estadoSistema?.ubidots_configurado
                            ? "Configurado"
                            : "Offline"
                        }
                      />
                      <StatusDotRow
                        etiqueta="Proveedor IA"
                        activo={
                          Boolean(estadoSistema?.ia_gemini_configurado) ||
                          Boolean(estadoSistema?.ia_ollama_disponible) ||
                          Boolean(estadoSistema?.ollama_disponible) ||
                          estadoSistema?.ia_proveedor === "auto" ||
                          estadoSistema?.ia_proveedor === "ollama" ||
                          estadoSistema?.ia_proveedor === "gemini" ||
                          estadoSistema?.ia_proveedor === "hibrido"
                        }
                        detalle={
                          estadoSistema?.ia_proveedor === "auto"
                            ? estadoSistema.ia_gemini_configurado
                              ? "auto · Gemini/Local"
                              : "auto · Resiliente"
                            : estadoSistema?.ia_proveedor ?? "local_reglas"
                        }
                      />
                      <StatusDotRow
                        etiqueta="Worker Segundo Plano"
                        activo={Boolean(estadoSistema?.worker_activo)}
                      />
                      <StatusDotRow
                        etiqueta="Puertos Serial COM"
                        activo={(estadoSistema?.puertos_serial?.length ?? 0) > 0}
                        detalle={`${estadoSistema?.puertos_serial?.length ?? 0} disp.`}
                      />
                      <StatusDotRow
                        etiqueta="n8n / Telegram"
                        activo={
                          Boolean(estadoSistema?.webhook_configurado) ||
                          Boolean(estadoSistema?.telegram_configurado)
                        }
                      />
                    </ul>
                  </div>
                </>
              )}
            </div>

            {/* Toggle rápido de tema */}
            <button
              type="button"
              onClick={alternarTemaRapido}
              aria-label={
                temaEfectivo === "dark"
                  ? "Cambiar a modo claro Field Daylight"
                  : "Cambiar a modo oscuro Obsidian Canopy"
              }
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
            >
              {temaEfectivo === "dark" ? (
                <Sun className="h-4 w-4" aria-hidden="true" />
              ) : (
                <Moon className="h-4 w-4" aria-hidden="true" />
              )}
            </button>
          </div>
        </header>

        {/* Área de contenido principal */}
        <main
          id="main-content"
          tabIndex={-1}
          className="flex-1 overflow-y-auto px-4 py-5 sm:px-6 sm:py-6"
        >
          <div className="mx-auto max-w-[1440px]">{children}</div>
        </main>
      </div>

      <CommandPalette abierto={cmdAbierto} onCerrar={() => setCmdAbierto(false)} />
    </div>
  );
}
