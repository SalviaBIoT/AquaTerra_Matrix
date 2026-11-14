import { MandarinoAvatar } from "../common/MandarinoAvatar";

export function TypingIndicator() {
  return (
    <div
      className="mandarino-bubble-in mt-3 flex items-start gap-2.5"
      role="status"
      aria-live="polite"
      aria-label="Mandarino está escribiendo"
    >
      <MandarinoAvatar size="xs" pensando className="mt-1" />
      <div className="rounded-2xl rounded-tl-sm border border-[var(--mandarino-border)] bg-[var(--mandarino-soft)] px-4 py-3 shadow-sm">
        <div className="flex items-center gap-1.5" aria-hidden="true">
          <span className="mandarino-dot h-2 w-2 rounded-full bg-[#f97316]" />
          <span className="mandarino-dot h-2 w-2 rounded-full bg-[#f5b041]" />
          <span className="mandarino-dot h-2 w-2 rounded-full bg-[#fb923c]" />
        </div>
        <span className="sr-only">Mandarino está redactando su respuesta…</span>
      </div>
    </div>
  );
}
