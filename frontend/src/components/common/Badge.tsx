import type { ReactNode } from "react";
import type { NivelSeveridadPulso } from "../../types/aquaterra";

type TonoBadge = "optimal" | "warning" | "critical" | "info" | "neutral";

const ESTILOS_TONO: Record<TonoBadge, string> = {
  optimal:
    "bg-[var(--status-optimal-soft)] text-[var(--status-optimal)] border-[color-mix(in_srgb,var(--status-optimal)_30%,transparent)]",
  warning:
    "bg-[var(--status-warning-soft)] text-[var(--status-warning)] border-[color-mix(in_srgb,var(--status-warning)_30%,transparent)]",
  critical:
    "bg-[var(--status-critical-soft)] text-[var(--status-critical)] border-[color-mix(in_srgb,var(--status-critical)_32%,transparent)]",
  info: "bg-[var(--status-info-soft)] text-[var(--status-info)] border-[color-mix(in_srgb,var(--status-info)_30%,transparent)]",
  neutral:
    "bg-[var(--bg-subtle)] text-[var(--text-secondary)] border-[var(--border-subtle)]",
};

export function Badge({
  tono = "neutral",
  children,
  className = "",
}: {
  tono?: TonoBadge;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium tracking-tight ${ESTILOS_TONO[tono]} ${className}`}
    >
      {children}
    </span>
  );
}

export function SeveridadBadge({
  severidad,
}: {
  severidad: NivelSeveridadPulso;
}) {
  const mapa: Record<
    NivelSeveridadPulso,
    { tono: TonoBadge; texto: string; punto: string }
  > = {
    critico: {
      tono: "critical",
      texto: "Crítico",
      punto: "bg-[var(--status-critical)]",
    },
    atencion: {
      tono: "warning",
      texto: "Atención",
      punto: "bg-[var(--status-warning)]",
    },
    optimo: {
      tono: "optimal",
      texto: "Óptimo",
      punto: "bg-[var(--status-optimal)]",
    },
    sin_datos: {
      tono: "neutral",
      texto: "Sin datos",
      punto: "bg-[var(--text-muted)]",
    },
  };
  const cfg = mapa[severidad] ?? mapa.sin_datos;
  return (
    <Badge tono={cfg.tono}>
      <span className={`h-1.5 w-1.5 rounded-full ${cfg.punto}`} aria-hidden="true" />
      {cfg.texto}
    </Badge>
  );
}
