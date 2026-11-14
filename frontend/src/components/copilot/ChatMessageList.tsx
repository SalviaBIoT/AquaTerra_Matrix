import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type RefObject,
} from "react";
import { format, isToday, isYesterday, parseISO } from "date-fns";
import { es } from "date-fns/locale";
import { ArrowDown, ChevronUp } from "lucide-react";
import { ChatBubble } from "./ChatBubble";
import { TypingIndicator } from "./TypingIndicator";
import type { MensajeChat } from "./types";

interface ChatMessageListProps {
  mensajesVentana: MensajeChat[];
  cantidadOcultaArriba: number;
  primerNombre: string;
  consultandoActual: boolean;
  esAdmin: boolean;
  aplicandoId: number | null;
  claveActiva: string;
  scrollTriggerToken: number;
  mensajeDestacadoId: string | null;
  contenedorRef: RefObject<HTMLDivElement | null>;
  onCargarAnteriores: () => void;
  onAplicarPropuesta: (interaccionId: number) => void;
  onVerCotas: () => void;
  onRegenerar: (mensaje: MensajeChat) => void;
  onQuickReply: (prompt: string) => void;
}

interface GrupoDia {
  claveDia: string;
  etiquetaDia: string;
  items: { mensaje: MensajeChat; agrupado: boolean }[];
}

function formatearEtiquetaDia(tsIso: string): {
  clave: string;
  etiqueta: string;
} {
  try {
    const fecha = parseISO(tsIso);
    if (Number.isNaN(fecha.getTime())) {
      return { clave: "reciente", etiqueta: "Reciente" };
    }
    const clave = format(fecha, "yyyy-MM-dd");
    if (isToday(fecha)) return { clave, etiqueta: "Hoy" };
    if (isYesterday(fecha)) return { clave, etiqueta: "Ayer" };
    const texto = format(fecha, "d 'de' MMMM", { locale: es });
    return {
      clave,
      etiqueta: texto.charAt(0).toUpperCase() + texto.slice(1),
    };
  } catch {
    return { clave: "reciente", etiqueta: "Reciente" };
  }
}

export function ChatMessageList({
  mensajesVentana,
  cantidadOcultaArriba,
  primerNombre,
  consultandoActual,
  esAdmin,
  aplicandoId,
  claveActiva,
  scrollTriggerToken,
  mensajeDestacadoId,
  contenedorRef,
  onCargarAnteriores,
  onAplicarPropuesta,
  onVerCotas,
  onRegenerar,
  onQuickReply,
}: ChatMessageListProps) {
  const cercaDelFondoRef = useRef(true);
  const [mostrarBotonBajar, setMostrarBotonBajar] = useState(false);

  const irAlFondoInstantaneo = useCallback(() => {
    const el = contenedorRef.current;
    if (!el) return;
    requestAnimationFrame(() => {
      el.scrollTop = el.scrollHeight;
      cercaDelFondoRef.current = true;
      setMostrarBotonBajar(false);
    });
  }, [contenedorRef]);

  // Salto instantáneo cuando cambia el hilo, se carga historial o llega mensaje nuevo cerca del fondo
  useEffect(() => {
    if (mensajeDestacadoId) {
      const target = document.getElementById(`msg-${mensajeDestacadoId}`);
      if (target) {
        target.scrollIntoView({ behavior: "auto", block: "center" });
        return;
      }
    }
    if (cercaDelFondoRef.current) {
      irAlFondoInstantaneo();
    }
  }, [
    mensajesVentana.length,
    consultandoActual,
    claveActiva,
    scrollTriggerToken,
    mensajeDestacadoId,
    irAlFondoInstantaneo,
  ]);

  const handleScroll = () => {
    const el = contenedorRef.current;
    if (!el) return;
    const distancia = el.scrollHeight - el.scrollTop - el.clientHeight;
    const cerca = distancia < 90;
    cercaDelFondoRef.current = cerca;
    setMostrarBotonBajar(!cerca && mensajesVentana.length > 0);
  };

  const ultimoMandarinoId = useMemo(() => {
    for (let i = mensajesVentana.length - 1; i >= 0; i -= 1) {
      if (mensajesVentana[i].autor === "mandarino") {
        return mensajesVentana[i].id;
      }
    }
    return null;
  }, [mensajesVentana]);

  const gruposPorDia = useMemo<GrupoDia[]>(() => {
    const grupos: GrupoDia[] = [];
    for (const msg of mensajesVentana) {
      const { clave, etiqueta } = formatearEtiquetaDia(msg.tsIso);
      let grupoActual = grupos[grupos.length - 1];
      if (!grupoActual || grupoActual.claveDia !== clave) {
        grupoActual = { claveDia: clave, etiquetaDia: etiqueta, items: [] };
        grupos.push(grupoActual);
      }
      const previoEnDia =
        grupoActual.items[grupoActual.items.length - 1]?.mensaje ?? null;
      const agrupado =
        previoEnDia !== null && previoEnDia.autor === msg.autor;
      grupoActual.items.push({ mensaje: msg, agrupado });
    }
    return grupos;
  }, [mensajesVentana]);

  return (
    <div
      ref={contenedorRef}
      onScroll={handleScroll}
      aria-label="Hilo de conversación con Mandarino"
      className="relative z-10 flex-1 min-h-0 overflow-y-auto px-4 py-4 sm:px-6"
    >
      {cantidadOcultaArriba > 0 && (
        <div className="mb-3 flex justify-center">
          <button
            type="button"
            onClick={onCargarAnteriores}
            className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-3 py-1 text-[11px] font-medium text-[var(--text-secondary)] hover:border-[#f5b041]/50 hover:text-[#f5b041]"
          >
            <ChevronUp className="h-3.5 w-3.5" aria-hidden="true" />
            Ver mensajes anteriores ({cantidadOcultaArriba} más)
          </button>
        </div>
      )}

      <div className="flex flex-col">
        {gruposPorDia.map((grupo) => (
          <div key={grupo.claveDia} className="relative">
            {/* Sticky Date Header estilo mensajería industrial con margen limpio */}
            <div className="sticky top-1 z-20 mb-2.5 flex justify-center py-0.5 pointer-events-none">
              <span className="rounded-full border border-[var(--border-subtle)] bg-[var(--bg-surface)]/95 px-3.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)] shadow-sm backdrop-blur-md">
                {grupo.etiquetaDia}
              </span>
            </div>

            {grupo.items.map(({ mensaje, agrupado }) => (
              <ChatBubble
                key={mensaje.id}
                mensaje={mensaje}
                primerNombre={primerNombre}
                agrupadoConAnterior={agrupado}
                destacado={mensajeDestacadoId === mensaje.id}
                esUltimoMandarino={mensaje.id === ultimoMandarinoId}
                consultandoActual={consultandoActual}
                esAdmin={esAdmin}
                aplicandoId={aplicandoId}
                onAplicarPropuesta={onAplicarPropuesta}
                onVerCotas={onVerCotas}
                onRegenerar={onRegenerar}
                onQuickReply={onQuickReply}
              />
            ))}
          </div>
        ))}

        {consultandoActual && <TypingIndicator />}
      </div>

      {mostrarBotonBajar && (
        <div className="sticky bottom-2 mt-3 flex justify-center">
          <button
            type="button"
            onClick={irAlFondoInstantaneo}
            className="inline-flex items-center gap-1 rounded-full bg-[#f97316] px-3 py-1.5 text-[11px] font-semibold text-white shadow-lg hover:bg-[#ea580c]"
          >
            <ArrowDown className="h-3.5 w-3.5" aria-hidden="true" />
            Mensajes recientes
          </button>
        </div>
      )}
    </div>
  );
}
