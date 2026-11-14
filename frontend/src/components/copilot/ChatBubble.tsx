import { useState, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Check,
  CheckCircle2,
  Code2,
  Copy,
  RefreshCw,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "../common/Badge";
import { MandarinoAvatar } from "../common/MandarinoAvatar";
import {
  etiquetarProveedorIA,
  formatearFechaIso,
  formatearNumero,
  nombreLegibleVariable,
} from "../../lib/formatters";
import type { ChipAccionRapida, MensajeChat } from "./types";

interface ChatBubbleProps {
  mensaje: MensajeChat;
  primerNombre: string;
  agrupadoConAnterior: boolean;
  destacado?: boolean;
  esUltimoMandarino: boolean;
  consultandoActual: boolean;
  esAdmin: boolean;
  aplicandoId: number | null;
  onAplicarPropuesta: (interaccionId: number) => void;
  onVerCotas: () => void;
  onRegenerar: (mensaje: MensajeChat) => void;
  onQuickReply: (prompt: string) => void;
}

const COMPONENTES_MARKDOWN = {
  p: ({ children }: { children?: ReactNode }) => (
    <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>
  ),
  ul: ({ children }: { children?: ReactNode }) => (
    <ul className="mb-2 list-disc space-y-1 pl-5 last:mb-0">{children}</ul>
  ),
  ol: ({ children }: { children?: ReactNode }) => (
    <ol className="mb-2 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>
  ),
  li: ({ children }: { children?: ReactNode }) => (
    <li className="leading-relaxed">{children}</li>
  ),
  strong: ({ children }: { children?: ReactNode }) => (
    <strong className="font-semibold text-[#fb923c]">{children}</strong>
  ),
  h3: ({ children }: { children?: ReactNode }) => (
    <h3 className="mt-2 mb-1 text-xs font-bold uppercase tracking-wider text-[#f5b041]">
      {children}
    </h3>
  ),
  table: ({ children }: { children?: ReactNode }) => (
    <div className="my-2.5 overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)]">
      <table className="w-full border-collapse text-left text-xs">{children}</table>
    </div>
  ),
  thead: ({ children }: { children?: ReactNode }) => (
    <thead className="bg-[var(--bg-canvas)] text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
      {children}
    </thead>
  ),
  th: ({ children }: { children?: ReactNode }) => (
    <th className="border-b border-[var(--border-subtle)] px-2.5 py-1.5">{children}</th>
  ),
  td: ({ children }: { children?: ReactNode }) => (
    <td className="border-b border-[var(--border-subtle)]/60 px-2.5 py-1.5 font-mono text-[11px]">
      {children}
    </td>
  ),
  code: ({
    className,
    children,
  }: {
    className?: string;
    children?: ReactNode;
  }) => {
    const esBloque = Boolean(className?.includes("language-")) || String(children).includes("\n");
    if (esBloque) {
      return (
        <pre className="my-2 overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[#070b09] p-3 font-mono text-[11px] leading-relaxed text-[#2ecc71]">
          <code>{children}</code>
        </pre>
      );
    }
    return (
      <code className="rounded bg-[var(--bg-surface)] px-1.5 py-0.5 font-mono text-[11px] text-[#f5b041]">
        {children}
      </code>
    );
  },
};

export function ChatBubble({
  mensaje: m,
  primerNombre,
  agrupadoConAnterior,
  destacado = false,
  esUltimoMandarino,
  consultandoActual,
  esAdmin,
  aplicandoId,
  onAplicarPropuesta,
  onVerCotas,
  onRegenerar,
  onQuickReply,
}: ChatBubbleProps) {
  const [copiado, setCopiado] = useState(false);
  const [mostrarRaw, setMostrarRaw] = useState(false);

  const margenCluster = agrupadoConAnterior ? "mt-1" : "mt-3.5";

  const handleCopiar = async () => {
    const contenido = m.recomendacion
      ? `${m.textoPrincipal}\n\nFundamento: ${m.recomendacion}`
      : m.textoPrincipal;
    try {
      await navigator.clipboard.writeText(contenido);
      setCopiado(true);
      toast.success("Mensaje copiado al portapapeles.");
      window.setTimeout(() => setCopiado(false), 1800);
    } catch {
      toast.error("No se pudo copiar al portapapeles.");
    }
  };

  if (m.autor === "usuario") {
    return (
      <div
        id={`msg-${m.id}`}
        className={`mandarino-bubble-in ${margenCluster} flex justify-end`}
      >
        <div
          className={`max-w-[85%] space-y-1 sm:max-w-[78%] ${
            destacado ? "rounded-2xl ring-2 ring-[#f5b041] ring-offset-2 ring-offset-[var(--bg-surface)]" : ""
          }`}
        >
          {!agrupadoConAnterior && (
            <div className="flex items-center justify-end gap-1.5 text-[10px] text-[var(--text-muted)]">
              <span>{formatearFechaIso(m.tsIso)}</span>
              <span className="font-semibold text-[#f5b041]">{primerNombre}</span>
            </div>
          )}
          <div className="rounded-2xl rounded-br-sm border border-[#f5b041]/35 bg-gradient-to-br from-[#f97316]/20 to-[#f5b041]/10 px-3.5 py-2.5 text-sm leading-relaxed text-[var(--text-primary)] shadow-sm">
            {m.textoPrincipal}
          </div>
        </div>
      </div>
    );
  }

  const tieneAjustes =
    Boolean(m.ajustesSeguros) && Object.keys(m.ajustesSeguros ?? {}).length > 0;
  const quickReplies: ChipAccionRapida[] = [];
  if (esUltimoMandarino && !consultandoActual) {
    if (tieneAjustes && m.interaccionId && !m.calibracionAplicadaId) {
      quickReplies.push({
        id: "qr-apply",
        etiqueta: "Aplicar calibración ahora",
        tipo: "aplicar",
      });
      quickReplies.push({
        id: "qr-cotas",
        etiqueta: "Comparar en tabla de cotas",
        tipo: "cotas",
      });
    } else if ((m.alertas?.length ?? 0) > 0) {
      quickReplies.push({
        id: "qr-anom",
        etiqueta: "Explicar anomalía",
        tipo: "prompt",
        prompt: "Explica con detalle físico por qué ocurre esta anomalía y qué riesgo real implica.",
      });
      quickReplies.push({
        id: "qr-campo",
        etiqueta: "Pasos prácticos en campo",
        tipo: "prompt",
        prompt: "Dame una lista de verificación paso a paso para revisar físicamente el nodo.",
      });
      quickReplies.push({
        id: "qr-clima",
        etiqueta: "Clima y pronóstico 24h",
        tipo: "prompt",
        prompt:
          "¿Cómo está el clima exterior ahora y cuál es el pronóstico de lluvia y ET0 para las próximas 24 horas?",
      });
    } else {
      quickReplies.push({
        id: "qr-vars",
        etiqueta: "¿Qué variables vigilo hoy?",
        tipo: "prompt",
        prompt: "¿Qué variables clave debo vigilar hoy y dentro de qué rangos son óptimas?",
      });
      quickReplies.push({
        id: "qr-clima",
        etiqueta: "Clima y pronóstico 24h",
        tipo: "prompt",
        prompt:
          "¿Cómo está el clima exterior ahora y cuál es el pronóstico de lluvia y ET0 para las próximas 24 horas?",
      });
      quickReplies.push({
        id: "qr-sugs",
        etiqueta: "Sugerencias de mejora",
        tipo: "prompt",
        prompt: "¿Qué sugerencias concretas de optimización o mantenimiento recomiendas ahora?",
      });
    }
  }

  const jsonRawObj = m.rawJson ?? {
    interaccion_id: m.interaccionId ?? null,
    proveedor: m.proveedor ?? "desconocido",
    confianza: m.confianza ?? null,
    alertas_consideradas: m.alertas ?? [],
    ajustes_seguros: m.ajustesSeguros ?? {},
    recortes_aplicados: m.recortes ?? [],
    advertencias: m.advertencias ?? [],
    claves_rechazadas: m.clavesRechazadas ?? [],
    ts_iso: m.tsIso,
  };

  return (
    <div
      id={`msg-${m.id}`}
      className={`group mandarino-bubble-in ${margenCluster} flex items-start gap-2.5`}
    >
      {agrupadoConAnterior ? (
        <div className="w-7 shrink-0" aria-hidden="true" />
      ) : (
        <MandarinoAvatar size="xs" className="mt-4" />
      )}

      <div className="max-w-[88%] flex-1 space-y-1 sm:max-w-[84%]">
        <div className="flex items-center justify-between gap-2">
          {!agrupadoConAnterior ? (
            <div className="flex flex-wrap items-center gap-1.5 text-[10px] text-[var(--text-muted)]">
              <span className="font-semibold text-[#fb923c]">Mandarino</span>
              {m.proveedor && (
                <span className="rounded-full bg-[var(--bg-elevated)] px-2 py-0.5 text-[10px] text-[#2ecc71]">
                  {etiquetarProveedorIA(m.proveedor)}
                </span>
              )}
              {typeof m.confianza === "number" && (
                <span className="tabular-nums">
                  {formatearNumero(m.confianza * 100, 0, "%")}
                </span>
              )}
              <span>· {formatearFechaIso(m.tsIso)}</span>
            </div>
          ) : (
            <span className="text-[10px] text-[var(--text-muted)] opacity-0 transition-opacity group-hover:opacity-100">
              {formatearFechaIso(m.tsIso)}
            </span>
          )}

          {/* Action Menu por Hover */}
          <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
            <button
              type="button"
              onClick={() => void handleCopiar()}
              title="Copiar texto"
              aria-label="Copiar texto"
              className="inline-flex h-6 items-center gap-1 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-1.5 text-[10px] text-[var(--text-secondary)] hover:border-[#f5b041]/50 hover:text-[#f5b041]"
            >
              {copiado ? (
                <Check className="h-3 w-3 text-[#2ecc71]" aria-hidden="true" />
              ) : (
                <Copy className="h-3 w-3" aria-hidden="true" />
              )}
              <span className="hidden sm:inline">Copiar</span>
            </button>
            <button
              type="button"
              disabled={consultandoActual}
              onClick={() => onRegenerar(m)}
              title="Regenerar respuesta"
              aria-label="Regenerar respuesta"
              className="inline-flex h-6 items-center gap-1 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-1.5 text-[10px] text-[var(--text-secondary)] hover:border-[#f97316]/50 hover:text-[#fb923c] disabled:opacity-45"
            >
              <RefreshCw className="h-3 w-3" aria-hidden="true" />
              <span className="hidden sm:inline">Regenerar</span>
            </button>
            <button
              type="button"
              onClick={() => setMostrarRaw((prev) => !prev)}
              title="Ver JSON RAW"
              aria-label="Ver JSON RAW"
              className={`inline-flex h-6 items-center gap-1 rounded-lg border px-1.5 text-[10px] transition-colors ${
                mostrarRaw
                  ? "border-[#2ecc71]/50 bg-[#2ecc71]/15 text-[#2ecc71]"
                  : "border-[var(--border-subtle)] bg-[var(--bg-surface)] text-[var(--text-secondary)] hover:border-[#2ecc71]/40 hover:text-[#2ecc71]"
              }`}
            >
              <Code2 className="h-3 w-3" aria-hidden="true" />
              <span className="hidden sm:inline">JSON</span>
            </button>
          </div>
        </div>

        <div
          className={`rounded-2xl rounded-tl-sm border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3.5 text-sm leading-relaxed text-[var(--text-primary)] shadow-sm ${
            destacado ? "ring-2 ring-[#f5b041]" : ""
          }`}
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={COMPONENTES_MARKDOWN}
          >
            {m.textoPrincipal}
          </ReactMarkdown>

          {m.recomendacion &&
            m.recomendacion.trim().length > 0 &&
            m.recomendacion.trim() !== "Evaluación generada por modelo IA." && (
            <div className="mt-2.5 rounded-xl border-l-2 border-l-[#2ecc71] bg-[var(--bg-surface)] px-3 py-2 text-xs leading-relaxed text-[var(--text-secondary)]">
              <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-[#2ecc71]">
                Fundamento Agronómico
              </div>
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={COMPONENTES_MARKDOWN}
              >
                {m.recomendacion}
              </ReactMarkdown>
            </div>
          )}

          {(m.alertas?.length ?? 0) > 0 && (
            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {m.alertas?.map((alerta, idx) => (
                <Badge key={idx} tono="warning">
                  {alerta}
                </Badge>
              ))}
            </div>
          )}

          {tieneAjustes && m.ajustesSeguros && (
            <div className="mt-2.5 rounded-xl border border-[#f5b041]/35 bg-[#f5b041]/10 p-2.5 text-xs">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold text-[#f5b041]">
                  Calibración segura sugerida
                </span>
                {m.calibracionAplicadaId ? (
                  <Badge tono="optimal">Aplicada</Badge>
                ) : (
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={onVerCotas}
                      className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-2 py-0.5 text-[11px] text-[var(--text-secondary)] hover:text-[#f5b041]"
                    >
                      Ver cotas
                    </button>
                    {m.interaccionId && (
                      <button
                        type="button"
                        disabled={!esAdmin || aplicandoId === m.interaccionId}
                        onClick={() => onAplicarPropuesta(m.interaccionId!)}
                        className="inline-flex items-center gap-1 rounded-lg bg-[#2ecc71] px-2.5 py-1 text-[11px] font-semibold text-[#062116] hover:brightness-110 disabled:opacity-45"
                      >
                        <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
                        {aplicandoId === m.interaccionId ? "Aplicando…" : "Aplicar"}
                      </button>
                    )}
                  </div>
                )}
              </div>
              <ul className="mt-2 grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                {Object.entries(m.ajustesSeguros).map(([clave, val]) => (
                  <li
                    key={clave}
                    className="flex items-center justify-between rounded-lg bg-[var(--bg-surface)] px-2.5 py-1 font-mono text-[11px]"
                  >
                    <span className="font-sans text-[var(--text-secondary)]">
                      {nombreLegibleVariable(clave)}
                    </span>
                    <strong className="text-[#f5b041]">{val}</strong>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {((m.recortes?.length ?? 0) > 0 || (m.advertencias?.length ?? 0) > 0) && (
            <div className="mt-2.5 rounded-xl bg-[var(--status-warning-soft)] p-2 text-xs">
              <div className="flex items-center gap-1 font-semibold text-[#f5b041]">
                <ShieldAlert className="h-3.5 w-3.5" aria-hidden="true" />
                Guardarraíl físico aplicado
              </div>
              <ul className="mt-1 space-y-0.5 pl-4 text-[var(--text-secondary)]">
                {m.recortes?.map((rec, i) => (
                  <li key={i}>
                    {nombreLegibleVariable(rec.clave)}: {rec.valor_original} →{" "}
                    {rec.valor_acotado} ({rec.motivo})
                  </li>
                ))}
                {m.advertencias?.map((adv, i) => (
                  <li key={`a-${i}`}>{adv}</li>
                ))}
              </ul>
            </div>
          )}

          {mostrarRaw && (
            <pre className="mt-2.5 max-h-56 overflow-auto rounded-xl border border-[var(--border-subtle)] bg-[#070b09] p-2.5 font-mono text-[10px] leading-relaxed text-[#2ecc71]">
              {JSON.stringify(jsonRawObj, null, 2)}
            </pre>
          )}
        </div>

        {/* Píldoras de Acción Rápida contextuales al pie del último mensaje */}
        {quickReplies.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            {quickReplies.map((qr) => (
              <button
                key={qr.id}
                type="button"
                onClick={() => {
                  if (qr.tipo === "aplicar" && m.interaccionId) {
                    onAplicarPropuesta(m.interaccionId);
                  } else if (qr.tipo === "cotas") {
                    onVerCotas();
                  } else if (qr.prompt) {
                    onQuickReply(qr.prompt);
                  }
                }}
                className="inline-flex items-center gap-1 rounded-full border border-[#f5b041]/40 bg-[#f5b041]/10 px-2.5 py-1 text-[11px] font-medium text-[#f5b041] transition-colors hover:bg-[#f5b041]/20"
              >
                <Sparkles className="h-3 w-3" aria-hidden="true" />
                {qr.etiqueta}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
